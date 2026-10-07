"""三级判定的档位矩阵（plan/04 §四 闸门表，口径 K5）。

矩阵是**唯一**决定 finding 等级的地方，规则文件里没有 `level_rules` 字段：

- 规则自带等级 ⇒ "依据只是 located 的规则"可以自称 abnormal，K5 就形同虚设；
- 有效档位 = min(规则自身 status, 各依据条款 status)：规则不得声称比自己的依据更已核对。

`pending` 档的 limit/construct 规则是**不启用**（不出结论），而不是降级成 suspicious：
这类规则的阈值本身还没核对（阈值一律写 null），如果每次文档出现该参数都报一句
"无法判定"，真实缺陷会被噪声淹没，`误报 = 0` 的硬门也就守不住了（登记进 HANDOFF-M4 口径）。
"""

from typing import Any, Dict, List, Optional, Tuple

from ..kb.schema import STATUS_RANK

# check_type → 闸门表的列（cross_param 依赖规范参数之间的关系，与 limit 同列）
COLUMN = {
    "consistency": "consistency",
    "presence": "presence",
    "limit": "limit",
    "construct": "limit",
    "cross_param": "limit",
}

# (列, 有效档位) → 等级；None 表示规则不启用（不出结论）
LEVEL_MATRIX = {
    ("consistency", "verified"): "abnormal",
    ("consistency", "located"): "abnormal",   # 证据是文档两处原文自相矛盾本身，不需要规范数值
    ("consistency", "pending"): "suspicious",
    ("presence", "verified"): "abnormal",
    ("presence", "located"): "suspicious",
    ("presence", "pending"): "suspicious",
    ("limit", "verified"): "abnormal",
    ("limit", "located"): "suspicious",       # 数值未核对，不得硬判不符合
    ("limit", "pending"): None,
}

AMBIGUOUS_LEVEL = "suspicious"   # 多值/歧义/需人工确认，任何档位都不升 abnormal


def status_rank(status: Optional[str]) -> int:
    return STATUS_RANK.get(status or "pending", 0)


def effective_status(kb, rule: Dict[str, Any]) -> Tuple[str, List[str]]:
    """规则档位与依据条款档位取 min；返回 (有效档位, 依据明细)。"""
    index = kb.by_id("clause")
    status = rule.get("status") or "pending"
    details = []  # type: List[str]
    for entry in rule.get("basis") or []:
        if not isinstance(entry, dict):
            continue
        clause_id = entry.get("clause_id")
        clause = index.get(clause_id)
        clause_status = clause.get("status") if isinstance(clause, dict) else None
        details.append("%s=%s" % (clause_id, clause_status or "missing"))
        if status_rank(clause_status) < status_rank(status):
            status = clause_status if clause_status in STATUS_RANK else "pending"
    return status, details


def level_for(check_type: str, outcome: str, status: str) -> Optional[str]:
    """闸门表查表；`ambiguous` 一律 suspicious。"""
    if outcome == "none":
        return None
    column = COLUMN.get(check_type)
    if column is None:
        return None
    if outcome == "ambiguous":
        return AMBIGUOUS_LEVEL
    return LEVEL_MATRIX.get((column, status))
