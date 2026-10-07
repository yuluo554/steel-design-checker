"""参数卡校验与入口归一化（plan/04 §二）。

三条纪律：

1. **未知槽位一律拒绝**。参数卡是多出来的键要么是拼写错误，要么是想塞一个引擎不认的量，
   两种都必须失败，不能"忽略掉继续算"。
2. **枚举白名单只是输入词表，不是规范事实**。牌号清单（Q345/Q355 之争见 plan/07 §四 V5）、
   焊缝质量等级、性能等级等都还没与正式文本核对，所以这里放行**不代表**该值可用——
   真正能不能出数值由 status 门控决定（牌号的强度设计值仍来自未核对的表 4.4.1）。
3. **数据侧的量不作为输入槽位**：β_f、μ、P、φ 等必须由知识库提供，参数卡里出现即失败，
   否则用户可以绕过整个核对体系直接喂系数。
"""

from typing import Any, Dict, List, Optional, Tuple

from ..kb.schema import MODULES
from .errors import InputError
from .units import convert, number, resolve_units

# 只用于输入词表校验，取值范围尚未与正式文本核对（V5/V8）
STEEL_GRADES = ("Q235", "Q275", "Q345", "Q355", "Q390", "Q420")
QUALITY_CLASSES = ("A", "B", "C", "D", "E")
WELD_QUALITY = ("一级", "二级", "三级")
BOLT_GRADES = ("4.6", "4.8", "5.6", "6.8", "8.8", "10.9")
LOAD_DIRECTIONS = ("侧面", "正面", "混合")
LOAD_STATES = ("受剪", "受拉", "剪拉联合")
WELD_TYPES = ("直缝", "斜缝", "T形对接")
GROOVE_FORMS = ("全熔透", "部分熔透")
BOLT_TYPES = ("C级", "A、B级")
HOLE_TYPES = ("标准孔", "大孔")
SECTION_CLASSES = ("a", "b", "c", "d")
SURFACE_TREATMENTS = ("喷砂", "涂富锌漆后喷砂", "手工钢丝刷清除浮锈", "不处理")

ENUM_SLOTS = {
    "steel_grade": STEEL_GRADES,
    "quality_class": QUALITY_CLASSES,
    "weld_quality_class": WELD_QUALITY,
    "bolt_grade": BOLT_GRADES,
    "load_direction": LOAD_DIRECTIONS,
    "load_state": LOAD_STATES,
    "weld_type": WELD_TYPES,
    "groove_form": GROOVE_FORMS,
    "bolt_type": BOLT_TYPES,
    "hole_type": HOLE_TYPES,
    "section_class": SECTION_CLASSES,
    "surface_treatment": SURFACE_TREATMENTS,
    "connection_type": ("摩擦型",),
}

# 范围纪律（plan/04 A4）：承压型高强螺栓（11.4.3）属扩展项 E，显式请求就拒绝，
# 而不是笼统报「枚举越界」——这条要能在退出码 2 的信息里自证是被范围拦下，不是拼错。
SCOPE_REJECTIONS = {
    "承压型": "承压型高强螺栓（GB 50017-2017:11.4.3）属扩展项 E，首期只做摩擦型",
}

# 数值槽位所属量纲族；未列出的数值槽位按「无量纲」处理
SLOT_FAMILY = {
    "b": "length", "t": "length", "h_f": "length", "l_w": "length", "d": "length",
    "d_0": "length", "t_min": "length", "t_max": "length", "a": "length",
    "l": "length", "l_0x": "length", "l_0y": "length",
    "e": "length", "sum_t": "length", "spacing": "length", "pitch": "length",
    "edge": "length", "end_distance": "length", "bearing_parts_min_thickness": "length",
    "A": "area", "A_e": "area",
    "I_x": "second_moment", "I_y": "second_moment", "i_x": "length", "i_y": "length",
    "angle_deg": "angle", "theta": "angle",
}
POSITIVE_INT_SLOTS = ("n_welds", "n_f", "n_v", "bolt_count")

FORCE_SLOTS = ("N", "V", "T")
MOMENT_SLOTS = ("M",)

# 数据侧量：出现在参数卡里即失败（见模块 docstring 第 3 条）
FORBIDDEN_SLOTS = ("beta_f", "slip_factor_mu", "mu", "preload_P", "P", "phi",
                   "f_f_w", "f_t_w", "f_c_w", "f_v_w", "f_t_b", "f_v_b", "f_c_b", "f")

HEAD_SLOTS = ("case_id", "module", "forces", "units")

MODULE_SLOTS = {
    "butt_weld": {
        "required": ["steel_grade", "thickness_group", "weld_quality_class", "weld_type",
                     "groove_form", "b", "t", "l_w"],
        "optional": ["quality_class", "has_opening_gap", "angle_deg", "t_min"],
    },
    "fillet_weld": {
        "required": ["steel_grade", "thickness_group", "h_f", "l_w", "n_welds",
                     "load_direction"],
        "optional": ["quality_class", "weld_quality_class", "t_min", "t_max", "angle_deg"],
    },
    "bolt_normal": {
        "required": ["steel_grade", "thickness_group", "bolt_grade", "bolt_type", "d",
                     "d_0", "load_state", "group"],
        "optional": ["quality_class", "weld_quality_class", "hole_type",
                     "bearing_parts_min_thickness", "n_v", "t_min",
                     "bolt_count", "sum_t"],
    },
    "bolt_hsb_friction": {
        "required": ["steel_grade", "thickness_group", "bolt_grade", "surface_treatment",
                     "n_f", "bolt_count", "hole_type", "load_state", "group"],
        "optional": ["quality_class", "connection_type", "d", "d_0", "t_min"],
    },
    "column_buckling": {
        "required": ["steel_grade", "thickness_group", "section", "section_class",
                     "l_0x", "l_0y", "A"],
        "optional": ["quality_class", "thickness_group_y", "I_x", "I_y", "i_x", "i_y",
                     "b", "t"],
    },
}

GROUP_KEYS = ("n_x", "n_y", "pitch", "edge", "coordinates")


class Card(object):
    """归一化后的参数卡：值已全部换成内部单位（N、mm、MPa）。"""

    def __init__(self, case_id: str, module: str, values: Dict[str, Any],
                 units: Dict[str, str], table_axes: Dict[str, Any]):
        self.case_id = case_id
        self.module = module
        self.values = values
        self.units = units
        self.table_axes = table_axes

    def numeric_env(self) -> Dict[str, float]:
        env = {}
        for name, value in sorted(self.values.items()):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            env[name] = float(value)
        return env


def _check_enum(slot: str, value: Any) -> None:
    allowed = ENUM_SLOTS[slot]
    if not isinstance(value, str) or value not in allowed:
        raise InputError("槽位 %s 取值 %r 不在输入词表 %s 内" % (slot, value, list(allowed)))


def _validate_group(value: Any, units: Dict[str, str]) -> Dict[str, Any]:
    if not isinstance(value, dict) or not value:
        raise InputError("group 必须是排列信息对象（可用键：%s）" % list(GROUP_KEYS))
    unknown = sorted(set(value) - set(GROUP_KEYS))
    if unknown:
        raise InputError("group 存在未知键：%s" % ", ".join(unknown))
    out = {}  # type: Dict[str, Any]
    for key in GROUP_KEYS:
        if key not in value:
            continue
        if key == "coordinates":
            coords = value[key]
            if not isinstance(coords, list) or not coords:
                raise InputError("group.coordinates 必须是非空 [[x, y], …] 列表")
            pairs = []
            for index, pair in enumerate(coords):
                if (not isinstance(pair, (list, tuple)) or len(pair) != 2
                        or any(isinstance(p, bool) or not isinstance(p, (int, float))
                               for p in pair)):
                    raise InputError("group.coordinates[%d] 必须是两个数值" % index)
                pairs.append([convert(float(pair[0]), units["length"], "length",
                                      "group.coordinates[%d].x" % index),
                              convert(float(pair[1]), units["length"], "length",
                                      "group.coordinates[%d].y" % index)])
            out[key] = pairs
            continue
        family = "length"
        out[key] = convert(number(value[key], "group.%s" % key, allow_zero=False),
                           units[family], family, "group.%s" % key)
    return out


def normalize_card(raw: Any) -> Card:
    """算例 JSON → Card；任何不合规输入抛 `InputError`（CLI 退出码 2）。"""
    if not isinstance(raw, dict):
        raise InputError("参数卡必须是 JSON 对象，实际 %s" % type(raw).__name__)

    case_id = raw.get("case_id")
    if not isinstance(case_id, str) or not case_id.strip():
        raise InputError("参数卡缺少非空 case_id")

    module = raw.get("module")
    if not isinstance(module, str) or not module:
        raise InputError("参数卡缺少 module")
    if module not in MODULES:
        raise InputError("module 取值 %r 不在 5 个验算模块枚举 %s 内" % (module, list(MODULES)))

    spec = MODULE_SLOTS[module]
    allowed = list(HEAD_SLOTS) + spec["required"] + spec["optional"]
    unknown = sorted(set(raw) - set(allowed))
    if unknown:
        hints = [name for name in unknown if name in FORBIDDEN_SLOTS]
        if hints:
            raise InputError("槽位 %s 属数据侧量（由知识库提供，未核对即 blocked），"
                             "不允许由参数卡传入" % ", ".join(hints))
        raise InputError("参数卡存在 %s 模块未定义的槽位：%s" % (module, ", ".join(unknown)))

    missing = [name for name in spec["required"] if raw.get(name) is None]
    if missing:
        raise InputError("参数卡缺少必填槽位：%s" % ", ".join(missing))

    units = resolve_units(raw.get("units"))
    values = {}  # type: Dict[str, Any]

    for slot in spec["required"] + spec["optional"]:
        if raw.get(slot) is None:
            continue
        value = raw[slot]
        if slot in ENUM_SLOTS:
            if slot == "connection_type" and value in SCOPE_REJECTIONS:
                raise InputError("%s 槽位越界：%s" % (slot, SCOPE_REJECTIONS[value]))
            _check_enum(slot, value)
            values[slot] = value
            continue
        if slot == "group":
            values[slot] = _validate_group(value, units)
            continue
        if slot == "section":
            if not isinstance(value, str) or not value.strip():
                raise InputError("section 必须是非空截面名称字符串")
            values[slot] = value
            continue
        if slot == "has_opening_gap":
            if not isinstance(value, bool):
                raise InputError("has_opening_gap 必须是布尔值（有无引弧板）")
            values[slot] = value
            continue
        if slot in POSITIVE_INT_SLOTS:
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise InputError("槽位 %s 必须是正整数，实际 %r" % (slot, value))
            values[slot] = float(value)
            continue
        family = SLOT_FAMILY.get(slot)
        if family is None:
            # thickness_group 这类分组键是字符串，数值键按无量纲处理
            if isinstance(value, str):
                values[slot] = value
                continue
            values[slot] = number(value, slot, allow_zero=False)
            continue
        if isinstance(value, str):
            raise InputError("槽位 %s 应为 %s 量纲的数值，实际是字符串 %r" % (slot, family, value))
        converted = convert(number(value, slot, allow_zero=False),
                            units[family], family, slot)
        values[slot] = converted

    forces = raw.get("forces")
    if not isinstance(forces, dict) or not forces:
        raise InputError("参数卡缺少 forces（设计内力，荷载组合由外部给定）")
    unknown_forces = sorted(set(forces) - set(FORCE_SLOTS + MOMENT_SLOTS))
    if unknown_forces:
        raise InputError("forces 出现未知分量：%s（可用：%s）" % (
            ", ".join(unknown_forces), list(FORCE_SLOTS + MOMENT_SLOTS)))
    for name in sorted(forces):
        family = "moment" if name in MOMENT_SLOTS else "force"
        values[name] = convert(number(forces[name], "forces.%s" % name, allow_zero=True),
                               units[family], family, "forces.%s" % name)

    axes = {}  # type: Dict[str, Any]
    for axis_slot in ("steel_grade", "thickness_group", "weld_quality_class", "bolt_grade",
                      "surface_treatment", "hole_type", "section_class", "load_direction",
                      "groove_form", "bolt_type", "quality_class"):
        if axis_slot in values:
            axes[axis_slot] = values[axis_slot]

    return Card(case_id.strip(), module, values, units, axes)
