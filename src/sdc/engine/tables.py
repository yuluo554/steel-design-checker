"""数值表查表：只有 `status=verified` 的表能把值交给计算路径。

`values` 记录形态（M2 定稿，plan/04 §三）：

```json
{"axes": {"steel_grade": "Q235", "thickness_group": "t<=16"},
 "outputs": {"f": 215.0, "fv": 125.0}}
```

- `axes` 的键必须是参数卡槽位名，`outputs` 的键必须是式体里出现的符号名（ASCII 形式），
  这样"查表 → 代入住"不需要任何硬编码映射；
- `interpolation=group` 走精确匹配（分组查表不插值）；`linear` 允许**一个数值轴 + 若干分组轴**，
  数值轴的行形如 `{"x": 30.0, "outputs": {"phi": 0.958}}`（可再带 `"axes": {"section_class": "b"}`
  做分类过滤，M3 落地附录 D 时需要：φ 表本体就是「截面分类 × λ/εk」的二维表），超界直接失败而不是外推；
- 表的 `unit` 字段声明数值本体单位，换算同样只发生在入口层（`units.py`）。
"""

from typing import Any, Dict, List, Optional, Tuple

from .errors import EngineError
from .units import table_unit_to_internal

_NUMERIC_AXES = ("lambda", "lambda_n", "x", "slenderness")


def _table_record(kb, table_id: str) -> Dict[str, Any]:
    rec = kb.by_id("table").get(table_id)
    if not isinstance(rec, dict):
        raise EngineError("数值表 %s 未入库，无法查表" % table_id)
    if rec.get("status") != "verified":
        # 门控本应在调用前挡住这条路；这里是"就算调用方漏了也取不到值"的第二道闸
        raise EngineError("数值表 %s 的 status=%s，未核对不进计算（口径 K2/K15）" % (
            table_id, rec.get("status")))
    return rec


def _entries(rec: Dict[str, Any], table_id: str) -> List[Dict[str, Any]]:
    entries = rec.get("values")
    if not isinstance(entries, list) or not entries:
        raise EngineError("数值表 %s 已声称 verified 但 values 为空" % table_id)
    return entries


def _outputs(entry: Dict[str, Any], table_id: str, unit: Any) -> Dict[str, float]:
    outputs = entry.get("outputs")
    if not isinstance(outputs, dict) or not outputs:
        raise EngineError("数值表 %s 存在没有 outputs 的行" % table_id)
    out = {}
    for key in sorted(outputs):
        value = outputs[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise EngineError("数值表 %s 的 outputs.%s 不是数值（%r）" % (table_id, key, value))
        out[key] = table_unit_to_internal(float(value), unit,
                                         "数值表 %s outputs.%s" % (table_id, key))
    return out


def _group_lookup(rec: Dict[str, Any], table_id: str, axes: Dict[str, Any]) -> Optional[Dict[str, float]]:
    declared = [str(a) for a in rec.get("axes") or []]
    if not declared:
        raise EngineError("数值表 %s 未声明 axes" % table_id)
    missing = [name for name in declared if name not in axes]
    if missing:
        return None  # 参数卡没给这条查表路径所需的轴 → 交由调用方记录并跳过
    unit = rec.get("unit")
    matches = []  # type: List[Dict[str, float]]
    for entry in _entries(rec, table_id):
        if not isinstance(entry, dict):
            raise EngineError("数值表 %s 的行不是对象" % table_id)
        row_axes = entry.get("axes")
        if not isinstance(row_axes, dict):
            raise EngineError("数值表 %s 的行缺少 axes 匹配键" % table_id)
        if all(row_axes.get(name) == axes[name] for name in declared):
            matches.append(_outputs(entry, table_id, unit))
    if not matches:
        raise EngineError("数值表 %s 中找不到分组 %s（分组边界与取值待正式文本核对）" % (
            table_id, ", ".join("%s=%s" % (name, axes[name]) for name in declared)))
    if len(matches) > 1 and any(m != matches[0] for m in matches[1:]):
        raise EngineError("数值表 %s 的分组 %s 命中多行且取值不一致，属数据冲突" % (
            table_id, tuple(axes[name] for name in declared)))
    return matches[0]


def _linear_lookup(rec: Dict[str, Any], table_id: str, axes: Dict[str, Any],
                   numeric_env: Dict[str, float]) -> Optional[Dict[str, float]]:
    declared = [str(a) for a in rec.get("axes") or []]
    if not declared:
        raise EngineError("数值表 %s 未声明 axes" % table_id)
    # 数值轴 = 出现在数值环境里的那个声明轴；其余声明轴必须由参数卡给出分组值。
    # 两边都取不到的轴＝这条查表路径没闭合，返回 None 交给编排层记"未查表"，
    # 绝不能退化成"忽略分组轴、把所有分类的行混在一起插值"（附录 D 那种二维表会直接出错值）。
    numeric_axes = [name for name in declared if name in numeric_env]
    if not numeric_axes:
        return None      # 数值轴还没被派生式算出来（不动点循环里正常发生），本轮跳过这张表
    if len(numeric_axes) > 1:
        raise EngineError("数值表 %s 的 linear 数值轴不唯一（声明 %s，环境里命中 %s）" % (
            table_id, declared, numeric_axes))
    axis = numeric_axes[0]
    group_axes = [name for name in declared if name != axis]
    missing = [name for name in group_axes if name not in axes]
    if missing:
        return None
    position = numeric_env[axis]

    unit = rec.get("unit")
    points = []  # type: List[Tuple[float, Dict[str, float]]]
    for entry in _entries(rec, table_id):
        if not isinstance(entry, dict) or not isinstance(entry.get("x"), (int, float)):
            raise EngineError("数值表 %s 的 linear 行需要数值键 x" % table_id)
        if group_axes:
            row_axes = entry.get("axes")
            if not isinstance(row_axes, dict):
                raise EngineError("数值表 %s 的 linear 行缺少分组过滤键 axes（声明了 %s）" % (
                    table_id, group_axes))
            if not all(row_axes.get(name) == axes[name] for name in group_axes):
                continue
        points.append((float(entry["x"]), _outputs(entry, table_id, unit)))
    if not points:
        raise EngineError("数值表 %s：分组 %s 在本表没有任何行（分类归属与表体不一致？）" % (
            table_id, ", ".join("%s=%s" % (name, axes[name]) for name in group_axes)))
    points.sort(key=lambda p: p[0])

    if position < points[0][0] or position > points[-1][0]:
        raise EngineError("数值表 %s：轴 %s=%s 超出表界 [%s, %s]，"
                          "禁止外推（插值口径必须与原文一致，见 plan/04 A5 易错点）" % (
                              table_id, axis, position, points[0][0], points[-1][0]))

    low = 0
    for index in range(1, len(points)):
        if points[index][0] >= position:
            low = index - 1
            break
    x0, y0 = points[low]
    x1, y1 = points[low + 1] if low + 1 < len(points) else (x0, y0)
    if x1 == x0 or position == x0:
        return dict(y0)
    weight = (position - x0) / (x1 - x0)
    keys = set(y0) | set(y1)
    if set(y0) != set(y1):
        raise EngineError("数值表 %s 相邻两行的 outputs 键不一致" % table_id)
    return dict((key, y0[key] + weight * (y1[key] - y0[key])) for key in sorted(keys))


def lookup(kb, table_id: str, axes: Dict[str, Any], numeric_env: Dict[str, float]) -> Optional[Dict[str, float]]:
    """按参数卡轴值查表；轴不齐时返回 None（调用方记录"这张表本算例用不上"）。"""
    rec = _table_record(kb, table_id)
    mode = rec.get("interpolation")
    if mode in ("group", "none"):
        return _group_lookup(rec, table_id, axes)
    if mode == "linear":
        return _linear_lookup(rec, table_id, axes, numeric_env)
    raise EngineError("数值表 %s 的 interpolation=%r 不被支持" % (table_id, mode))
