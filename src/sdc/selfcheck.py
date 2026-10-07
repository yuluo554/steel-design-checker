"""`sdc selfcheck`：数据完整性审计 + 三档 status 看板 + 门控视图 + 推进队列 + 数据指纹。

输出不含时间戳，保持同一数据目录下逐字节一致（口径 K8）。

三档 status（plan/05 §二、06 D15）：`pending` 条号未确认 / `located` 条号+主题+表号已定位
但式体与表体数值未取到 / `verified` 式体与数值已与正式文本核对。只有 `verified` 能进计算，
所以 located 与 pending 一样让模块 `blocked`，区别在于 located 可以对外展示条号与主题。

M4 加的两档看板（口径 K44）把"未核对"从一句状态变成一份工单：
`[6] 推进看板` 逐条说明规则/检查单条目**为什么还不能启用**、启用还差哪条条款核对；
`[7] 核对队列` 反过来按条款聚合——核对完这一条能解锁哪些规则与条目，按解锁数排序。
未启用原因分四类，其中 `slot_unsupported` 与数据核对无关（解析层还没有那个槽位），
把它混进"等核对"的队列里会让人白跑一趟正式文本。
"""

from typing import Any, Dict, List

from .kb import all_module_gates, data_fingerprint, load_kb
from .kb.loader import KINDS
from .kb.schema import SPEC, THRESHOLD_FIELDS, THRESHOLD_KINDS, VERIFIED_BY_REQUIRED
from .parse.slots import SLOT_NAMES
from .rules.gate import effective_status, level_for

_KB_KINDS = ("clause", "table", "formula", "symbol")

# 未启用原因的四分类，按"先解决哪个"的优先级排（口径 K44）
REASON_LABEL = {
    "slot_unsupported": "解析层没有这个槽位（与核对无关，先补抽取）",
    "threshold_unverified": "阈值未核对（一律写 null，判定层不启用）",
    "matrix_silent": "闸门表在该档位不出结论（plan/04 §四）",
    "active": "已启用（依据档位内的结论可判）",
}
REASON_ORDER = ("slot_unsupported", "threshold_unverified", "matrix_silent", "active")
_PROGRESS_KINDS = ("clause", "table", "formula", "symbol", "rule", "checklist")


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


def _condition_slots(condition, out):
    """条件语言里引用的槽位名（与 `rules/engine.condition_ok` 同一套算子，不另发明）。"""
    if not isinstance(condition, dict) or len(condition) != 1:
        return out
    op, value = list(condition.items())[0]
    if op in ("slot_present", "slot_absent"):
        if isinstance(value, str) and value:
            out.append(value)
    elif op == "slot_in":
        if isinstance(value, dict) and value.get("slot"):
            out.append(value["slot"])
    elif op in ("all_of", "any_of"):
        for sub in value or []:
            _condition_slots(sub, out)
    elif op == "not":
        _condition_slots(value, out)
    return out


def _assert_slots(assert_spec):
    out = []  # type: List[str]
    if not isinstance(assert_spec, dict):
        return out
    for field in ("slot",):
        if assert_spec.get(field):
            out.append(str(assert_spec[field]))
    for field in ("slots", "require_any_slots"):
        out.extend(str(name) for name in (assert_spec.get(field) or []))
    return out


def _unverified_basis(kb, basis):
    """依据条款里尚未升 verified 的那些（含悬空引用）：这就是"还差哪条核对"。"""
    index = kb.by_id("clause")
    blockers = []  # type: List[str]
    for entry in basis or []:
        if not isinstance(entry, dict):
            continue
        clause_id = str(entry.get("clause_id") or "")
        if not clause_id:
            continue
        clause = index.get(clause_id)
        status = clause.get("status") if isinstance(clause, dict) else "missing"
        if status != "verified":
            blockers.append(clause_id)
    return sorted(set(blockers))


def _rule_board(kb) -> Dict[str, Any]:
    """每条核查规则现在能不能启用、启用还差哪条核对（口径 K44）。"""
    rows = []  # type: List[Dict[str, Any]]
    for rec in sorted(kb.records.get("rule", []), key=lambda r: str(r.get("id", ""))):
        if not isinstance(rec, dict):
            continue
        rule_id = str(rec.get("id", ""))
        status, basis_detail = effective_status(kb, rec)
        assert_spec = rec.get("assert") or {}
        slots = sorted(set(_assert_slots(assert_spec)
                           + _condition_slots(rec.get("when"), [])))
        unsupported = sorted(slot for slot in slots if slot not in SLOT_NAMES)
        threshold_null = []  # type: List[str]
        if assert_spec.get("kind") in THRESHOLD_KINDS:
            threshold_null = sorted(field for field in THRESHOLD_FIELDS
                                    if field in assert_spec and assert_spec[field] is None)
        check_type = rec.get("check_type", "")
        silent = any(level_for(check_type, outcome, status) is None
                     for outcome in ("missing", "mismatch", "ambiguous"))
        if unsupported:
            reason = "slot_unsupported"
        elif threshold_null:
            reason = "threshold_unverified"
        elif silent:
            reason = "matrix_silent"
        else:
            reason = "active"
        rows.append({
            "id": rule_id, "name": rec.get("name", ""), "check_type": check_type,
            "status": rec.get("status", ""), "effective_status": status,
            "basis": basis_detail, "slots": slots, "unsupported_slots": unsupported,
            "threshold_null": threshold_null, "reason": reason,
            "blockers": _unverified_basis(kb, rec.get("basis")),
        })
    counts = dict((reason, sum(1 for row in rows if row["reason"] == reason))
                  for reason in REASON_ORDER)
    return {"rules": rows, "counts": counts}


def _checklist_board(kb) -> Dict[str, Any]:
    """检查单条目的自动初判能力与还差的核对（107 条里只有 9 条挂得上判据，这是事实）。"""
    rows = []  # type: List[Dict[str, Any]]
    for rec in sorted(kb.records.get("checklist", []), key=lambda r: str(r.get("id", ""))):
        if not isinstance(rec, dict):
            continue
        check = rec.get("check") if isinstance(rec.get("check"), dict) else None
        assert_spec = (check or {}).get("assert") or {}
        threshold_null = []  # type: List[str]
        if assert_spec.get("kind") in THRESHOLD_KINDS:
            threshold_null = sorted(field for field in THRESHOLD_FIELDS
                                    if field in assert_spec and assert_spec[field] is None)
        clause_id = str(rec.get("clause_id") or "")
        rows.append({
            "id": str(rec.get("id", "")),
            "chapter": rec.get("chapter", ""),
            "status": rec.get("status", ""),
            "auto": check is not None and "assert" in check,
            "threshold_null": threshold_null,
            "blockers": _unverified_basis(kb, [{"clause_id": clause_id, "gist": ""}]
                                          if clause_id else []),
        })
    return {
        "total": len(rows),
        "auto_judgeable": sum(1 for row in rows if row["auto"]),
        "manual_only": sum(1 for row in rows if not row["auto"]),
        "threshold_null": sum(1 for row in rows if row["threshold_null"]),
        "entries": rows,
    }


def _verify_queue(rule_board, checklist_board, kb) -> List[Dict[str, Any]]:
    """反过来按条款聚合：核对完这一条能解锁什么，按解锁数从多到少排（工单顺序）。"""
    index = kb.by_id("clause")
    buckets = {}  # type: Dict[str, Dict[str, Any]]
    for row in rule_board["rules"]:
        for clause_id in row["blockers"]:
            bucket = buckets.setdefault(clause_id, {"clause_id": clause_id,
                                                    "rules": [], "entries": []})
            bucket["rules"].append(row["id"])
    for row in checklist_board["entries"]:
        for clause_id in row["blockers"]:
            bucket = buckets.setdefault(clause_id, {"clause_id": clause_id,
                                                    "rules": [], "entries": []})
            bucket["entries"].append(row["id"])
    out = []  # type: List[Dict[str, Any]]
    for clause_id, bucket in buckets.items():
        rec = index.get(clause_id)
        out.append({
            "clause_id": clause_id,
            "status": (rec.get("status") if isinstance(rec, dict) else "missing") or "missing",
            "standard": rec.get("standard", "") if isinstance(rec, dict) else "",
            "clause_no": rec.get("clause_no", "") if isinstance(rec, dict) else "",
            "gist": (rec.get("gist", "") or rec.get("title", "")) if isinstance(rec, dict) else "",
            "rules": sorted(set(bucket["rules"])),
            "entries": sorted(set(bucket["entries"])),
            "unlock_count": len(set(bucket["rules"])) + len(set(bucket["entries"])),
        })
    out.sort(key=lambda item: (-item["unlock_count"], item["clause_id"]))
    return out


def _progress(kb) -> Dict[str, Dict[str, Any]]:
    """各 kind 的 located→verified 进度（plan/05 §二 的生命周期现在是几比几）。"""
    out = {}
    for kind in _PROGRESS_KINDS:
        records = [r for r in kb.records.get(kind, []) if isinstance(r, dict)]
        statuses = [r.get("status") for r in records]
        total = len(records)
        verified = statuses.count("verified")
        out[kind] = {
            "total": total,
            "verified": verified,
            "located": statuses.count("located"),
            "pending": statuses.count("pending"),
            "percent_verified": (float(verified) / total * 100.0) if total else 0.0,
        }
    return out


def build_report(data_dir: str) -> Dict[str, Any]:
    kb = load_kb(data_dir)
    rule_board = _rule_board(kb)
    checklist_board = _checklist_board(kb)
    return {
        "data_dir": data_dir,
        "counts": _counts(kb),
        "traceability": _traceability(kb),
        "problems": kb.problems,
        "modules": all_module_gates(kb),
        "status_board": _status_board(kb),
        "progress": _progress(kb),
        "rules": rule_board,
        "checklist": checklist_board,
        "verify_queue": _verify_queue(rule_board, checklist_board, kb),
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
    out.append("")

    out.extend(_render_progress(report))
    out.append("")
    out.extend(_render_queue(report))
    return "\n".join(out)


def _render_progress(report: Dict[str, Any]) -> List[str]:
    out = ["[6] 推进看板：located→verified 进度与未启用原因（口径 K44）"]
    for kind in _PROGRESS_KINDS:
        row = report["progress"][kind]
        if not row["total"]:
            continue
        out.append("  %-9s %3d 条，verified %d（%.1f%%），located %d，pending %d" % (
            kind, row["total"], row["verified"], row["percent_verified"],
            row["located"], row["pending"]))

    rules = report["rules"]["rules"]
    counts = report["rules"]["counts"]
    out.append("")
    out.append("  核查规则 %d 条：" % len(rules))
    for reason in REASON_ORDER:
        if counts.get(reason):
            out.append("    %-20s %2d 条 —— %s" % (reason, counts[reason], REASON_LABEL[reason]))
    for row in rules:
        if row["reason"] == "active":
            continue
        extra = []
        if row["unsupported_slots"]:
            extra.append("解析未支持 %s" % ", ".join(row["unsupported_slots"]))
        if row["threshold_null"]:
            extra.append("阈值 null：%s" % ", ".join(row["threshold_null"]))
        if row["reason"] == "matrix_silent":
            extra.append("闸门表 %s/%s 不出结论" % (row["check_type"], row["effective_status"]))
        out.append("    - %-28s [%s] 有效档位 %s｜%s" % (
            row["id"], row["check_type"], row["effective_status"],
            "；".join(extra) or "无"))
        if row["blockers"]:
            out.append("      还差核对：%s" % ", ".join(row["blockers"]))

    checklist = report["checklist"]
    out.append("")
    out.append("  检查单条目 %d 条：挂自动初判 %d，其余 %d 条只能人工确认；"
               "条目阈值未核对 %d" % (
                   checklist["total"], checklist["auto_judgeable"],
                   checklist["manual_only"], checklist["threshold_null"]))
    out.append("  未启用的原因与 `sdc check` 报告里的「未启用规则」同一套判据"
               "（同一个闸门矩阵 + 同一批 schema 字段，不是第二套口径）。")
    return out


def _render_queue(report: Dict[str, Any]) -> List[str]:
    queue = report["verify_queue"]
    out = ["[7] 核对队列（工单顺序：核对完这一条能解锁什么）"]
    if not queue:
        out.append("  队列为空：没有条目在等条款核对（通常意味着 verified 已到位）。")
        return out
    for index, item in enumerate(queue[:15], start=1):
        out.append("  %2d. %-28s status=%-8s 解锁 %2d 项（规则 %d／条目 %d）" % (
            index, item["clause_id"], item["status"], item["unlock_count"],
            len(item["rules"]), len(item["entries"])))
        if item["gist"]:
            out.append("      %s" % (item["gist"][:70] + ("…" if len(item["gist"]) > 70 else "")))
        if item["rules"]:
            out.append("      规则：%s" % ", ".join(item["rules"][:8]))
        if item["entries"]:
            shown = ", ".join(item["entries"][:6])
            out.append("      条目：%s%s" % (shown, " …" if len(item["entries"]) > 6 else ""))
    if len(queue) > 15:
        out.append("      …（其余 %d 条见 --json：整份队列都在 verify_queue 里）" % (len(queue) - 15))
    out.append("  合计 %d 条条款在挡着 %d 项判定（按解锁数排序，先啃解锁多的）。" % (
        len(queue), sum(item["unlock_count"] for item in queue)))
    return out
