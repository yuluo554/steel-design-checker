"""`sdc run` 的人类可读输出（同一份 Result，不另起第二套判定逻辑，口径 D08）。"""

from typing import Any, Dict

from .core import DISCLAIMER

_CONCLUSION_ZH = {
    "satisfied": "满足",
    "unsatisfied": "不满足",
    "need_adjust": "需调整/宜复核（接近限值）",
    "blocked": "拒算（数据未核对）",
}


def _rule(char: str = "-") -> str:
    return char * 72


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return repr(round(value, 6))
    return str(value)


def render_result(result: Dict[str, Any]) -> str:
    lines = [_rule("=")]
    lines.append("验算结果  %s  ·  %s" % (result["case_id"], result["module"]))
    lines.append(_rule("="))
    conclusion = result["conclusion"]
    lines.append("结论：%s（%s）" % (conclusion, _CONCLUSION_ZH.get(conclusion, "")))
    lines.append("比值（作用效应/抗力）：%s" % (
        "不出数值（blocked）" if conclusion == "blocked" else _fmt(result["ratio"])))
    lines.append("数据指纹：%s" % result["meta"]["data_fingerprint"])
    lines.append("")

    if result["blocked"]:
        lines.append("[拒算依据] 引用了未核对的数据，按口径 K2/K15 不产生数值：")
        for item in result["blocked"]:
            lines.append("  - %-8s %-28s %s" % (item["kind"], item["id"], item["reason"]))
        lines.append("")

    if result["steps"]:
        lines.append("[计算过程] 逐步可核（式体与数值均来自知识库）：")
        for step in result["steps"]:
            lines.append("  %d. %s  %s" % (step["no"], step["formula_id"], step["expr"]))
            substituted = step.get("substituted") or {}
            if substituted:
                lines.append("     代入：%s" % ", ".join(
                    "%s=%s" % (name, _fmt(substituted[name])) for name in sorted(substituted)))
            lines.append("     结果：%s%s%s" % (
                _fmt(step["value"]),
                " %s" % step["unit"] if step.get("unit") else "",
                "（%s）" % step["symbol_zh"] if step.get("symbol_zh") else ""))
        lines.append("")

    if result["limits"]:
        lines.append("[构造与限值检查]")
        for item in result["limits"]:
            lines.append("  %-22s %s %s = %s  实测 %s  %s" % (
                item["param"], item["op"], item.get("desc", ""), _fmt(item["bound"]),
                _fmt(item["actual"]), "通过" if item["ok"] else "不通过"))
        lines.append("")

    if result["warnings"]:
        lines.append("[强制性条文联动提示]")
        for item in result["warnings"]:
            lines.append("  - %s" % item["message"])
        lines.append("")

    lines.append("[依据条款]")
    if result["basis"]:
        for item in result["basis"]:
            lines.append("  - %s  %s  [%s]%s" % (
                item["clause_id"], item["title"], item["status"],
                "（强条）" if item.get("mandatory") else ""))
    else:
        lines.append("  （无：全部依赖未核对，未进入计算）")
    lines.append("")

    if result["notes"]:
        lines.append("[留痕]")
        for note in result["notes"]:
            lines.append("  · %s" % note)
        lines.append("")

    lines.append(_rule())
    lines.append("免责声明：%s" % DISCLAIMER)
    return "\n".join(lines)


__all__ = ["render_result"]
