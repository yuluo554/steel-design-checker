"""GB 55006-2021 符合性检查单引擎（`sdc checklist`，plan/04 §五）。

条目分母按 **T4 拍板＝全 8 章要点化**：本模块负责"章节覆盖到什么程度"这件事必须被
显式说出来的地方 —— `summary.chapters_missing` 列出还没有条目的章，绝不把"四章 18 条"
当成"全章已覆盖"（07 §二.5 的 18 条只是核心四章的分母）。

初判口径与核查侧同一条闸门（K5）：依据条款只是 `located` 时，条目最多只能被标成
`auto_flag`（可疑/需确认），**不得**被判"不符合"；人工答复（`--answers`）单独记录来源，
不与自动初判混成一体。
"""

from typing import Any, Dict, List, Optional

from . import __version__
from .engine.core import DISCLAIMER
from .kb.fingerprint import data_fingerprint
from .rules.engine import build_units, condition_ok, judge_assert
from .rules.gate import effective_status, level_for

STANDARD = "GB 55006-2021"
# 规范目录级事实（07 §二.5，A+B 两渠道文字一致）：8 章名称。用于显式披露覆盖缺口。
CHAPTERS = {
    "1": "1 总则",
    "2": "2 基本规定",
    "3": "3 材料",
    "4": "4 构件及连接设计",
    "5": "5 结构设计",
    "6": "6 抗震与防护",
    "7": "7 施工及验收",
    "8": "8 维护与拆除",
}
VERDICT_LABEL = {
    "auto_pass": "自动初判：未见缺失",
    "auto_flag": "自动初判：可疑",
    "need_human": "待人工确认",
    "not_activated": "文档未涉及该主题",
    "human_pass": "人工答复：符合",
    "human_fail": "人工答复：不符合",
    "not_applicable": "人工答复：不适用",
}
ANSWER_TO_VERDICT = {"符合": "human_pass", "不符合": "human_fail",
                     "不适用": "not_applicable", "待确认": "need_human"}
ANSWER_OPTIONS = ("符合", "不符合", "不适用", "待确认")


def _chapter_key(chapter: str) -> str:
    head = str(chapter or "").strip()
    for token in ("1 总则", "2 基本规定", "3 材料", "4 构件及连接设计",
                  "5 结构设计", "6 抗震与防护", "7 施工及验收", "8 维护与拆除"):
        if head.startswith(token.split(" ")[0]) and head[:1] == token[:1]:
            return token.split(" ")[0]
    digits = ""
    for char in head:
        if char.isdigit():
            digits += char
        else:
            break
    return digits or "?"


def _linked_slot_state(entry: Dict[str, Any], ir: Optional[Dict[str, Any]]) -> List[str]:
    if ir is None:
        return []
    slots = ir.get("slots") or {}
    return sorted(name for name in (entry.get("linked_slots") or []) if name not in slots)


def _auto_verdict(kb, entry: Dict[str, Any], unit: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """条目自带的 `check`（与核查规则同一套条件/断言语言）→ 自动初判。"""
    check = entry.get("check")
    if unit is None or not isinstance(check, dict) or "assert" not in check:
        return {"verdict": "need_human", "level": "",
                "reason": "无文档 IR 或本条目未定义可自动判定的检查项"}
    status, _detail = effective_status(kb, {
        "status": entry.get("status", "pending"),
        "basis": [{"clause_id": entry["clause_id"], "gist": ""}]
        if entry.get("clause_id") else [],
    })
    when = check.get("when")
    if when is not None and not condition_ok(when, unit):
        return {"verdict": "not_activated", "level": "",
                "reason": "文档未出现本条目关注的用词（类目隔离）"}
    outcome = judge_assert(check["assert"], unit, status)["outcome"]
    if outcome == "none":
        return {"verdict": "auto_pass", "level": "", "reason": "文档层面未见缺失"}
    if outcome == "disabled":
        return {"verdict": "need_human", "level": "",
                "reason": "条目阈值未核对（一律写 null），不做数值判定"}
    level = level_for(entry.get("check_type", "presence"), outcome, status)
    if level is None:
        return {"verdict": "need_human", "level": "",
                "reason": "闸门表规定 %s/%s 不出结论" % (
                    entry.get("check_type", "presence"), status)}
    return {"verdict": "auto_flag", "level": level, "reason": "判定结果：%s" % outcome}


def build_report(kb, ir: Optional[Dict[str, Any]] = None,
                 answers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    entries = [r for r in kb.records.get("checklist", []) if isinstance(r, dict)]
    clauses = kb.by_id("clause")
    unit = build_units(ir)["document"][0] if ir else None
    answers = answers or {}

    rows = []  # type: List[Dict[str, Any]]
    for entry in sorted(entries, key=lambda e: str(e.get("id", ""))):
        entry_id = str(entry.get("id", ""))
        clause = clauses.get(entry.get("clause_id") or "")
        auto = _auto_verdict(kb, entry, unit)
        answer = answers.get(entry_id)
        verdict = ANSWER_TO_VERDICT.get(answer or "", auto["verdict"])
        row = {
            "id": entry_id,
            "chapter": _chapter_key(entry.get("chapter", "")),
            "chapter_text": entry.get("chapter", ""),
            "title": entry.get("title", ""),
            "gist": entry.get("gist", ""),
            "requirement_type": entry.get("requirement_type", ""),
            "mandatory": entry.get("mandatory") is True
                         or (isinstance(clause, dict) and clause.get("mandatory") is True),
            "status": entry.get("status", "pending"),
            "check_hint": entry.get("check_hint", ""),
            "supersedes": entry.get("supersedes", ""),
            "linked_slots": sorted(entry.get("linked_slots") or []),
            "missing_slots": _linked_slot_state(entry, ir),
            "verdict": verdict,
            "verdict_label": (VERDICT_LABEL.get(auto["verdict"]) + "（人工答复：%s）" % answer
                              if answer in ANSWER_TO_VERDICT and answer != "待确认"
                              else VERDICT_LABEL.get(auto["verdict"], auto["verdict"])),
            "auto": auto,
            "human_answer": answer or "",
            "source": entry.get("verified_by", {}).get("channel", "") if isinstance(
                entry.get("verified_by"), dict) else "",
            "source_url": entry.get("verified_by", {}).get("url", "") if isinstance(
                entry.get("verified_by"), dict) else "",
        }
        rows.append(row)

    by_verdict = {}  # type: Dict[str, int]
    for row in rows:
        by_verdict[row["verdict"]] = by_verdict.get(row["verdict"], 0) + 1
    covered = sorted(set(row["chapter"] for row in rows), key=lambda c: (c == "?", c))
    missing = sorted(CHAPTERS[key] for key in CHAPTERS
                     if key not in covered and key != "?")

    return {
        "standard": STANDARD,
        "ir_used": ir is not None,
        "entries": rows,
        "summary": {
            "total": len(rows),
            "by_verdict": dict(sorted(by_verdict.items())),
            "chapters_covered": covered,
            "chapters_missing": missing,
            "mandatory_total": sum(1 for row in rows if row["mandatory"]),
            "verified_total": sum(1 for row in rows if row["status"] == "verified"),
            "located_total": sum(1 for row in rows if row["status"] == "located"),
            "pending_total": sum(1 for row in rows if row["status"] == "pending"),
        },
        "meta": {"engine_version": __version__,
                 "data_fingerprint": data_fingerprint(kb.data_dir)},
        "disclaimer": DISCLAIMER,
    }


def render_text(report: Dict[str, Any]) -> str:
    summary = report["summary"]
    out = ["=" * 72, "sdc checklist（GB 55006-2021 符合性检查单）", "=" * 72]
    out.append("条目 %d 条，覆盖 %d 章；依据档位 verified %d / located %d / pending %d" % (
        summary["total"], len(summary["chapters_covered"]), summary["verified_total"],
        summary["located_total"], summary["pending_total"]))
    out.append("全文强制规范：本清单 %d 条**都是**强制性条文（前言「全部条文必须严格执行」，"
               "50017 的 7 条强条清单不适用于本标准）" % summary["mandatory_total"])
    out.append("文档 IR：%s" % ("已接入，可自动初判的条目见下" if report["ir_used"] else
                                "未接入 —— 全部条目只能标为待人工确认"))
    out.append("判定分布：%s" % ", ".join(
        "%s=%d" % (VERDICT_LABEL.get(key, key), value)
        for key, value in summary["by_verdict"].items()))
    if summary["chapters_missing"]:
        out.append("尚未覆盖的章（T4 要求全 8 章要点化，缺口必须显式）：%s"
                   % ", ".join(summary["chapters_missing"]))
    out.append("")

    flagged = [row for row in report["entries"] if row["verdict"] == "auto_flag"]
    if flagged:
        out.append("[1] 自动初判为可疑的条目（依据只到 located，不判不符合）")
        for row in flagged:
            out.append("  ？ %s %s" % (row["id"], row["title"]))
            out.append("      %s；文档中未找到的相关槽位：%s" % (
                row["auto"]["reason"], ", ".join(row["missing_slots"]) or "-"))
            if row["check_hint"]:
                out.append("      核对：%s" % row["check_hint"])
        out.append("")

    out.append("[2] 分章清单（判定｜条目｜标题）")
    current = None
    for row in report["entries"]:
        if row["chapter"] != current:
            current = row["chapter"]
            out.append("")
            out.append("— %s —" % (row["chapter_text"] or ("第 %s 章" % current)))
        marks = {"auto_pass": "初判无缺失", "auto_flag": "可疑", "need_human": "待确认",
                 "not_applicable": "不适用(人工)", "not_activated": "未涉及",
                 "human_pass": "符合(人工)", "human_fail": "不符合(人工)"}
        out.append("  [%-10s] %-22s %s（%s｜出处：%s）" % (
            marks.get(row["verdict"], row["verdict"]), row["id"], row["title"],
            row["requirement_type"], row["source"] or "渠道未登记"))
        if row["human_answer"]:
            out.append("        人工答复：%s（自动初判：%s）" % (
                row["human_answer"], VERDICT_LABEL.get(row["auto"]["verdict"], "")))
    out.append("")

    out.append("[3] 说明")
    out.append("  · 自动初判受依据档位约束：依据只是 located 的条目不会判「不符合」（口径 K5）。")
    out.append("  · 未挂自动判据的条目一律「待确认」，本工具不替人打勾。")
    out.append("  · 人工答复用 --answers 提供（{\"条目 id\": \"符合|不符合|不适用|待确认\"}），")
    out.append("    答复与自动初判分列留痕。")
    out.append("  · 逐条出处只写渠道名：渠道 URL 属取证台账（data/README.md、.tmp_verify/），"
               "不写进交付物（口径 K40/K42）。")
    out.append("  · docx 导出：`sdc checklist --out 检查单.docx`（与本文同源，含免责声明）。")
    out.append("免责声明：%s" % report["disclaimer"])
    return "\n".join(out)
