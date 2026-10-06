"""`sdc selfcheck`：数据完整性审计 + 三档 status 看板 + 门控视图 + 数据指纹。

输出不含时间戳，保持同一数据目录下逐字节一致（口径 K8）。

三档 status（plan/05 §二、06 D15）：`pending` 条号未确认 / `located` 条号+主题+表号已定位
但式体与表体数值未取到 / `verified` 式体与数值已与正式文本核对。只有 `verified` 能进计算，
所以 located 与 pending 一样让模块 `blocked`，区别在于 located 可以对外展示条号与主题。
"""

from typing import Any, Dict, List

from .kb import all_module_gates, data_fingerprint, load_kb
from .kb.loader import KINDS
from .kb.schema import SPEC, VERIFIED_BY_REQUIRED

_KB_KINDS = ("clause", "table", "formula", "symbol")


def _counts(kb) -> Dict[str, Dict[str, int]]:
    out = {}
    for kind in KINDS:
        records = [r for r in kb.records.get(kind, []) if isinstance(r, dict)]
        status = [r.get("status") for r in records]
        out[kind] = {
            "total": len(records),
            "verified": status.count("verified"),
            "located": status.count("located"),
            "pending": status.count("pending"),
            "selfcheck_only": status.count("selfcheck"),
            "no_status": sum(1 for s in status if s not in
                             ("verified", "located", "pending", "selfcheck")),
        }
    return out


def _traceability(kb) -> Dict[str, int]:
    """已挂核对档（located/verified）的记录中，渠道+日期+URL 齐全的比例。"""
    checked = 0
    complete = 0
    for kind in _KB_KINDS:
        for rec in kb.records.get(kind, []):
            if not isinstance(rec, dict) or rec.get("status") not in ("located", "verified"):
                continue
            checked += 1
            verified_by = rec.get("verified_by")
            if isinstance(verified_by, dict) and all(
                verified_by.get(f) and verified_by[f] != "待补" for f in VERIFIED_BY_REQUIRED
            ):
                complete += 1
    return {"checked_total": checked, "checked_with_channel": complete}


def _status_board(kb) -> Dict[str, Dict[str, List[str]]]:
    board = {}
    for kind in _KB_KINDS:
        buckets = {"pending": [], "located": [], "verified": []}
        for rec in kb.records.get(kind, []):
            if not isinstance(rec, dict):
                continue
            status = rec.get("status")
            if status in buckets:
                buckets[status].append(kb.id_of(kind, rec))
        board[kind] = dict((k, sorted(v)) for k, v in buckets.items())

    cases = {"pending": [], "selfcheck": [], "verified": []}
    for rec in kb.records.get("case", []):
        if isinstance(rec, dict) and rec.get("status") in cases:
            cases[rec["status"]].append(str(rec.get("case_id", "")))
    board["case"] = dict((k, sorted(v)) for k, v in cases.items())
    return board


def build_report(data_dir: str) -> Dict[str, Any]:
    kb = load_kb(data_dir)
    return {
        "data_dir": data_dir,
        "counts": _counts(kb),
        "traceability": _traceability(kb),
        "problems": kb.problems,
        "modules": all_module_gates(kb),
        "status_board": _status_board(kb),
        "data_fingerprint": data_fingerprint(data_dir),
        "ok": not kb.problems,
    }


def _rule(char: str = "-") -> str:
    return char * 72


def render_text(report: Dict[str, Any]) -> str:
    out = [_rule("="), "sdc selfcheck（数据完整性与三档 status 看板）", _rule("=")]
    out.append("数据目录：%s" % report["data_dir"])
    out.append("data_fingerprint：%s" % report["data_fingerprint"])
    out.append("")

    out.append("[1] 记录计数（口径见 plan/05 §一/§二）")
    out.append("%-9s %5s %8s %7s %7s %7s %7s" % (
        "kind", "total", "verified", "located", "pending", "selfchk", "无档"))
    for kind in KINDS:
        c = report["counts"][kind]
        out.append("%-9s %5d %8d %7d %7d %7d %7d" % (
            kind, c["total"], c["verified"], c["located"], c["pending"],
            c["selfcheck_only"], c["no_status"]))
    trace = report["traceability"]
    out.append("已挂核对档的渠道完整率：%d / %d" % (
        trace["checked_with_channel"], trace["checked_total"]))
    out.append("")

    out.append("[2] 结构与引用问题：%d 项" % len(report["problems"]))
    if report["problems"]:
        for p in report["problems"][:40]:
            out.append("  - [%s] %s %s.%s：%s" % (
                p.get("type", ""), p["file"], p["id"] or "(无 id)", p["field"], p["problem"]))
        if len(report["problems"]) > 40:
            out.append("  …（其余 %d 项见 --json）" % (len(report["problems"]) - 40))
    else:
        out.append("  无")
    out.append("")

    out.append("[3] 模块门控（只有 verified 能进计算）")
    for gate in report["modules"]:
        out.append("  %-20s %-8s %s" % (gate["module"], gate["status"], gate["reason"]))
        for item in gate["unready"][:8]:
            out.append("      · %s %s → %s" % (item["kind"], item["id"], item["status"]))
        if len(gate["unready"]) > 8:
            out.append("      · …（其余 %d 项见 --json）" % (len(gate["unready"]) - 8))
    out.append("")

    out.append("[4] 三档看板（pending=条号未确认，located=条号已定位、数值未取到）")
    for kind in sorted(report["status_board"]):
        buckets = report["status_board"][kind]
        listed = [(name, ids) for name, ids in sorted(buckets.items()) if ids]
        if not listed:
            continue
        out.append("  %s：%s" % (kind, "，".join(
            "%s %d 项" % (name, len(ids)) for name, ids in listed)))
        for name, ids in listed:
            if name == "verified":
                continue
            out.append("      [%s] %s" % (name, ", ".join(ids[:15])))
            if len(ids) > 15:
                out.append("             …（其余 %d 项见 --json）" % (len(ids) - 15))
    out.append("")

    out.append("[5] 各 kind 的目录与 id 字段（schema 见 src/sdc/kb/schema.py）")
    for kind in KINDS:
        spec = SPEC[kind]
        out.append("  %-9s data/%s/*.json  id=%s" % (kind, spec["dir"], spec["id_field"]))

    return "\n".join(out)
