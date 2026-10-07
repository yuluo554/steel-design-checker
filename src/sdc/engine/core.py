"""验算引擎编排：参数卡 → status 门控 → 查表/式体交错求解 → Result。

引擎是**数据解释器**，不是规范知识载体：

- 式体（`expr`）与数值（表 `values`）全部来自知识库，代码里没有任何规范系数；
- 只有 `status=verified` 的公式、条款、数值表、符号能进入计算（口径 K2/K15），
  任一依赖是 `located` 或 `pending` 就整模块 `blocked` 并且**不产生任何数值**；
- 查表轴值可能来自参数卡，也可能来自派生式（如 A5 的 λ=l0/i 决定 φ 表位置），
  所以「查表」与「派生式」在同一个不动点循环里求解，直到没有新符号可解为止；
- 判定的容差与结论口径集中在本文件的 `RATIO_TOL` / `NEED_ADJUST_FLOOR`（口径 K2/K3）。

Result 结构见 plan/04 §一；`notes` 与 `basis[].mandatory` 是 M2 的增补位（登记
"某张表本算例的轴取不到所以没查"这类必须留痕但没有专门字段的事）。
"""

import math
from typing import Any, Dict, List, Optional, Tuple

from .. import __version__
from ..kb.fingerprint import data_fingerprint
from ..kb.gate import module_gate
from .errors import EngineError, ExprError, InputError
from .expr import build_plan, evaluate, parse_expression
from .params import Card, normalize_card
from .tables import lookup

# 口径 K2：ratio ≤ 1.0 满足；0.95 < ratio ≤ 1.0 判 need_adjust；> 1.0 不符合
NEED_ADJUST_FLOOR = 0.95
# 口径 K3：内部比较容差 1e-3（与真值比对容差分离，后者逐算例登记）
RATIO_TOL = 1e-3

DISCLAIMER = "辅助验算工具，不替代正式设计文件与施工图审查"

_KIND_REASON = {
    "pending": "status=pending（条号未确认），不进计算",
    "located": "status=located（条号/表号已定位，式体与数值未核对），不进计算",
    "missing": "依赖项未入库，不进计算",
}


def _satisfies(op: str, actual: float, bound: float) -> bool:
    """带 K3 容差的比对；只接受这几种比较符，不做表达式。"""
    tol = RATIO_TOL * max(1.0, abs(bound))
    close = math.isclose(actual, bound, rel_tol=0.0, abs_tol=tol)
    if op == ">=":
        return actual > bound or close
    if op == "<=":
        return actual < bound or close
    if op == ">":
        return actual > bound
    if op == "<":
        return actual < bound
    if op == "==":
        return close
    raise EngineError("构造限值比较符 %r 不被支持" % op)


def _blocked_result(card: Card, gate: Dict[str, Any], kb) -> Dict[str, Any]:
    """门控未通过：只报缺什么，绝不产出数值。"""
    blocked = []
    for item in gate["unready"]:
        status = item.get("status")
        blocked.append({
            "kind": item["kind"],
            "id": item["id"],
            "status": status,
            "reason": _KIND_REASON.get(status, "status=%s，不进计算" % status),
        })
    return {
        "case_id": card.case_id,
        "module": card.module,
        "conclusion": "blocked",
        "ratio": None,
        "steps": [],
        "basis": [],
        "limits": [],
        "warnings": [],
        "blocked": blocked,
        "notes": [gate["reason"]],
        "meta": {"engine_version": __version__,
                 "data_fingerprint": data_fingerprint(kb.data_dir)},
    }


def _symbol_field(kb, name: str, field: str, fallback: str = "") -> str:
    rec = kb.by_id("symbol").get(name)
    if isinstance(rec, dict) and isinstance(rec.get(field), str) and rec[field]:
        return rec[field]
    return fallback


def _resolve(
    kb, card: Card, requirements: Dict[str, List[str]],
    formulas: List[Dict[str, Any]], env: Dict[str, float],
    steps: List[Dict[str, Any]], notes: List[str],
) -> List[Tuple[str, Dict[str, Any], Any]]:
    """不动点求解：派生式与查表互相喂符号，直到再无进展。返回待判定的验算式。"""
    remaining = list(formulas)
    pending_tables = sorted(requirements["table"])
    checks = []  # type: List[Tuple[str, Dict[str, Any], Any]]

    while True:
        progressed = False

        for rec in list(remaining):
            formula_id = str(rec.get("id", ""))
            plan = build_plan(rec.get("expr"), formula_id)
            if plan.kind != "derivation":
                continue
            if any(name not in env for name in plan.names):
                continue
            if plan.target in env:
                raise EngineError("派生式 %s 的目标 %s 已有值，式体与参数卡/查表结果冲突" % (
                    formula_id, plan.target))
            value = evaluate(plan.left, env, formula_id)
            env[plan.target] = value
            steps.append({
                "no": len(steps) + 1,
                "formula_id": formula_id,
                "clause_id": rec.get("clause_id", ""),
                "expr": rec.get("expr", ""),
                "substituted": dict((name, env[name]) for name in sorted(plan.names)),
                "value": value,
                "unit": _symbol_field(kb, plan.target, "unit"),
                "symbol_zh": _symbol_field(kb, plan.target, "name_zh", plan.target),
                "output": plan.target,
            })
            remaining.remove(rec)
            progressed = True

        for table_id in list(pending_tables):
            values = lookup(kb, table_id, card.table_axes, env)
            if values is None:
                continue
            for key in sorted(values):
                if key in env:
                    raise EngineError("数值表 %s 输出的符号 %s 与已有量同名，"
                                      "数据侧量不允许由输入提供" % (table_id, key))
                env[key] = values[key]
            pending_tables.remove(table_id)
            progressed = True

        if not progressed:
            break

    for table_id in pending_tables:
        notes.append("数值表 %s 的轴值本算例取不到（参数卡未提供且派生式未产出），未查表" % table_id)

    for rec in remaining:
        plan = build_plan(rec.get("expr"), str(rec.get("id", "")))
        if plan.kind == "derivation":
            missing = sorted(set(name for name in plan.names if name not in env))
            raise EngineError("派生式 %s 无法求解，缺少符号：%s" % (
                rec.get("id"), ", ".join(missing)))

    for rec in remaining:
        formula_id = str(rec.get("id", ""))
        plan = build_plan(rec.get("expr"), formula_id)
        checks.append((formula_id, rec, plan))
    return sorted(checks, key=lambda item: item[0])


def _evaluate_checks(
    kb, checks: List[Tuple[str, Dict[str, Any], Any]], env: Dict[str, float],
    steps: List[Dict[str, Any]],
) -> List[float]:
    if not checks:
        raise EngineError("没有 <=/>= 验算式，无法给出结论")
    ratios = []
    for formula_id, rec, plan in checks:
        for name in plan.names:
            if name not in env:
                raise EngineError("验算式 %s 缺少符号 %s（式体、查表或参数卡的对应关系未闭合）" % (
                    formula_id, name))
        demand = evaluate(plan.left, env, formula_id)
        capacity = evaluate(plan.right, env, formula_id)
        if capacity == 0.0:
            raise ExprError("验算式 %s 的抗力端为 0，比值无意义" % formula_id)
        ratio = demand / capacity
        if not math.isfinite(ratio):
            raise ExprError("验算式 %s 的比值不是有限值" % formula_id)
        ratios.append(ratio)
        steps.append({
            "no": len(steps) + 1,
            "formula_id": formula_id,
            "clause_id": rec.get("clause_id", ""),
            "expr": rec.get("expr", ""),
            "substituted": dict((name, env[name]) for name in sorted(plan.names)),
            "value": ratio,
            "unit": "无量纲",
            "symbol_zh": "作用效应/抗力（%s）" % plan.op,
            "output": "ratio",
        })
    return ratios


def _run_limits(kb, clause_ids: List[str], env: Dict[str, float]) -> List[Dict[str, Any]]:
    """构造/限值检查：来自条款记录的 `limits`，只吃 verified 条款（门控已保证）。"""
    index = kb.by_id("clause")
    out = []
    for clause_id in sorted(set(clause_ids)):
        clause = index.get(clause_id)
        if not isinstance(clause, dict):
            continue
        for item in clause.get("limits") or []:
            if not isinstance(item, dict):
                raise EngineError("条款 %s 的 limits 项不是对象" % clause_id)
            param = item.get("param")
            if not isinstance(param, str) or param not in env:
                raise EngineError("条款 %s 的限值「%s」需要参数 %s，参数卡与式体都没提供" % (
                    clause_id, item.get("desc", ""), param))
            actual = env[param]
            if "bound_expr" in item:
                node, _names = parse_expression(
                    item["bound_expr"], "%s:limits.bound_expr" % clause_id)
                bound = evaluate(node, env, "%s:limits.bound_expr" % clause_id)
            elif isinstance(item.get("bound"), (int, float)) and not isinstance(item.get("bound"), bool):
                bound = float(item["bound"])
            else:
                raise EngineError("条款 %s 的限值项需要 bound 或 bound_expr" % clause_id)
            out.append({
                "param": param,
                "actual": actual,
                "bound": bound,
                "op": item.get("op", ""),
                "clause_id": clause_id,
                "desc": item.get("desc", ""),
                "ok": _satisfies(str(item.get("op", "")), actual, bound),
            })
    return out


def _basis(kb, clause_ids: List[str]) -> List[Dict[str, Any]]:
    index = kb.by_id("clause")
    basis = []
    for clause_id in sorted(set(clause_ids)):
        rec = index.get(clause_id)
        if not isinstance(rec, dict):
            continue
        basis.append({
            "clause_id": clause_id,
            "title": rec.get("title", "") or rec.get("standard", ""),
            "kind": rec.get("kind", ""),
            "status": rec.get("status", ""),
            "mandatory": rec.get("mandatory") is True,
        })
    return basis


def _warnings(basis: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """强制性条文联动提示（口径 K16 的 7 条清单由数据侧 mandatory 标记驱动，不在代码里写死）。"""
    out = []
    for item in basis:
        if item.get("mandatory") is True and item.get("status") == "verified":
            out.append({
                "type": "mandatory_clause",
                "clause_id": item["clause_id"],
                "message": "本计算路径引用强制性条文，请同步核对 %s（%s）" % (
                    item["clause_id"], item["title"]),
            })
    return out


def run_case(kb, raw_card: Any) -> Dict[str, Any]:
    """执行一条参数卡。输入不合法抛 `InputError`；数据不自洽抛 `EngineError`/`ExprError`。"""
    card = normalize_card(raw_card)
    gate = module_gate(card.module, kb)
    if gate["status"] != "ready":
        return _blocked_result(card, gate, kb)

    requirements = gate["requirements"]
    index = kb.by_id("formula")
    formulas = []
    for formula_id in sorted(requirements["formula"]):
        rec = index.get(formula_id)
        if not isinstance(rec, dict):
            raise EngineError("公式 %s 在门控与执行之间消失了（数据被改？）" % formula_id)
        formulas.append(rec)

    notes = []  # type: List[str]
    steps = []  # type: List[Dict[str, Any]]
    env = card.numeric_env()

    checks = _resolve(kb, card, requirements, formulas, env, steps, notes)
    ratios = _evaluate_checks(kb, checks, env, steps)
    limits = _run_limits(kb, requirements["clause"], env)
    basis = _basis(kb, requirements["clause"])

    ratio = max(ratios)
    if ratio > 1.0 + RATIO_TOL:
        conclusion = "unsatisfied"
    elif not all(item["ok"] for item in limits):
        conclusion = "unsatisfied"
    elif ratio > NEED_ADJUST_FLOOR:
        conclusion = "need_adjust"
    else:
        conclusion = "satisfied"

    return {
        "case_id": card.case_id,
        "module": card.module,
        "conclusion": conclusion,
        "ratio": ratio,
        "steps": steps,
        "basis": basis,
        "limits": limits,
        "warnings": _warnings(basis),
        "blocked": [],
        "notes": notes,
        "meta": {"engine_version": __version__,
                 "data_fingerprint": data_fingerprint(kb.data_dir)},
    }


def result_exit_code(result: Dict[str, Any]) -> int:
    """口径 K9：blocked = 降级完成（1）；出结论 = 完成（0）；输入不可用由调用方给 2。"""
    return 1 if result.get("conclusion") == "blocked" else 0


__all__ = ["run_case", "result_exit_code", "DISCLAIMER", "InputError",
           "EngineError", "ExprError"]
