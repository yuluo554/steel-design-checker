"""status 门控：未核对的数据不得进入计算路径（plan/03 §三.2、口径 K2）。

模块依赖关系不硬编码 id 清单，而是从数据本身推导：
公式（applies_to=模块或 general）→ 公式所属条款 + 公式符号 → 条款引用的数值表。
这样 M1 只入库 `pending` 数据时，全部模块天然 `blocked`，无需额外开关。
"""

from typing import Any, Dict, List, Optional

from .schema import MODULES

_MISSING = "missing"


def module_requirements(module: str, kb) -> Dict[str, List[str]]:
    """该模块计算路径需要引用的数据 id（按 kind 分组，已排序）。"""
    formulas = []  # type: List[str]
    clauses = []  # type: List[str]
    symbols = []  # type: List[str]
    tables = []  # type: List[str]

    clause_index = kb.by_id("clause")

    for rec in kb.records.get("formula", []):
        if not isinstance(rec, dict):
            continue
        if rec.get("applies_to") not in (module, "general"):
            continue
        formulas.append(str(rec.get("id", "")))
        clause_id = rec.get("clause_id")
        if isinstance(clause_id, str) and clause_id:
            clauses.append(clause_id)
        for symbol in rec.get("symbols") or []:
            if isinstance(symbol, str):
                symbols.append(symbol)

    for clause_id in list(clauses):
        clause = clause_index.get(clause_id)
        if not isinstance(clause, dict):
            continue
        for table_id in clause.get("tables") or []:
            if isinstance(table_id, str):
                tables.append(table_id)

    return {
        "formula": sorted(set(formulas)),
        "clause": sorted(set(clauses)),
        "symbol": sorted(set(symbols)),
        "table": sorted(set(tables)),
    }


def _status_or_missing(kb, kind: str, item_id: str) -> Optional[str]:
    status = kb.status_of(kind, item_id)
    return _MISSING if status is None else status


def module_gate(module: str, kb) -> Dict[str, Any]:
    """返回 ready/blocked 与造成 blocked 的待核对项（pending 或缺失）。"""
    requirements = module_requirements(module, kb)
    unready = []  # type: List[Dict[str, str]]

    for kind in ("formula", "clause", "symbol", "table"):
        for item_id in requirements[kind]:
            status = _status_or_missing(kb, kind, item_id)
            if status != "verified":
                unready.append({"kind": kind, "id": item_id, "status": status or _MISSING})

    if not requirements["formula"]:
        return {
            "module": module,
            "status": "blocked",
            "reason": "该模块尚无已入库公式（applies_to=%s）" % module,
            "requirements": requirements,
            "unready": unready,
        }

    if unready:
        return {
            "module": module,
            "status": "blocked",
            "reason": "依赖数据未核对或未入库，拒绝出数值",
            "requirements": requirements,
            "unready": unready,
        }

    return {
        "module": module,
        "status": "ready",
        "reason": "",
        "requirements": requirements,
        "unready": [],
    }


def all_module_gates(kb) -> List[Dict[str, Any]]:
    return [module_gate(module, kb) for module in MODULES]
