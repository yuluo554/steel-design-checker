"""单位入口适配（口径 K1）。

内部计算一律 力 N、长度 mm、应力 MPa=N/mm²，比值无量纲；换算**只**发生在这一层与查表层，
模块代码与式体里不出现任何单位换算系数。算例的 kN 输入与 N 输入必须得到完全相同的 ratio，
这条不变性由 `tests/test_engine_units.py` 守门。
"""

from typing import Any, Dict, Tuple

from .errors import InputError

FAMILIES = ("force", "moment", "length", "area", "second_moment", "stress", "angle")

UNIT_TABLE = {
    "force": {"N": 1.0, "kN": 1000.0},
    "moment": {"N·mm": 1.0, "N·m": 1000.0, "kN·mm": 1000.0, "kN·m": 1000000.0},
    "length": {"mm": 1.0, "cm": 10.0, "m": 1000.0},
    "area": {"mm2": 1.0, "mm²": 1.0, "cm2": 100.0, "cm²": 100.0, "m2": 1000000.0,
             "m²": 1000000.0},
    "second_moment": {"mm4": 1.0, "mm⁴": 1.0, "cm4": 10000.0, "cm⁴": 10000.0,
                      "m4": 1000000000.0, "m⁴": 1000000000.0},
    "stress": {"MPa": 1.0, "N/mm2": 1.0, "N/mm²": 1.0},
    "angle": {"deg": 1.0, "°": 1.0},
}

# 数值表记录的 `unit` 字段 → 内部量纲族（查表结果同样在本层换算）
TABLE_UNIT_FAMILY = {
    "MPa": "stress",
    "N/mm2": "stress",
    "N/mm²": "stress",
    "kN": "force",
    "N": "force",
    "mm": "length",
    "无量纲": None,
    "": None,
}

DEFAULT_UNITS = {
    "force": "N",
    "moment": "N·mm",
    "length": "mm",
    "area": "mm2",
    "second_moment": "mm4",
    "stress": "MPa",
    "angle": "deg",
}


def resolve_units(raw_units: Any) -> Dict[str, str]:
    """算例声明的单位 → 每个量纲族采用的单位；未知单位或不匹配量纲族直接判输入不可用。"""
    units = dict(DEFAULT_UNITS)
    if raw_units is None:
        return units
    if not isinstance(raw_units, dict):
        raise InputError("units 必须是对象，实际 %s" % type(raw_units).__name__)
    for family, unit in sorted(raw_units.items()):
        if family not in FAMILIES:
            raise InputError("units 出现未知量纲族 %s（可用：%s）" % (family, list(FAMILIES)))
        if not isinstance(unit, str) or unit not in UNIT_TABLE[family]:
            raise InputError("单位 %r 不属于量纲族 %s（可用：%s）" % (
                unit, family, sorted(UNIT_TABLE[family])))
        units[str(family)] = unit
    return units


def convert(value: float, unit: str, family: str, where: str) -> float:
    try:
        factor = UNIT_TABLE[family][unit]
    except KeyError:
        raise InputError("%s：单位 %r 不在量纲族 %s 内" % (where, unit, family))
    return float(value) * factor


def table_unit_to_internal(value: float, unit: Any, where: str) -> float:
    """数值表记录的 `unit` → 内部单位。未知单位视为数据问题（不猜）。"""
    if unit is None:
        return float(value)
    family = TABLE_UNIT_FAMILY.get(unit)
    if family is None:
        if unit in ("", "无量纲"):
            return float(value)
        raise InputError("%s：数值表单位 %r 无法归入内部量纲体系" % (where, unit))
    return float(value) * UNIT_TABLE[family][unit]


def number(value: Any, where: str, allow_zero: bool = True) -> float:
    """把输入值收成有限浮点数；bool、非数、非有限、负值都在这里拒绝。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError("%s：期望数值，实际 %r" % (where, value))
    out = float(value)
    if out != out or out in (float("inf"), float("-inf")):
        raise InputError("%s：数值非有限（%r）" % (where, value))
    if out < 0.0:
        raise InputError("%s：不允许负值（%r）" % (where, value))
    if out == 0.0 and not allow_zero:
        raise InputError("%s：不允许为 0" % where)
    return out
