"""`sdc bench`：算例真值库对账 + 引擎自校验样例 + 解析/核查配对评测。

四条口径（改任何一条都会打挂基准语义）：

- **K6**：通过率分母只含 `status=verified` 的算例；`pending` 与 `selfcheck` 分列，不得静默通过。
- **K3**：与真值比对的容差**逐算例登记**在算例的 `tolerance` 里；`expected` 出现数值字段而
  `tolerance` 没有对应项 → 判失败，不做"默认容差"。
- **D07**：`data/selfcheck/` 的样例只做单位不变性与确定性这类引擎级断言，永远不进分母。
- **K26**：`--parse`/`--audit` 只吃落盘的 IR（`sdc parse` 的产物），本模块不 import 正则；
  IR 缺失直接判输入不可用（rc=2），不在评测进程里现场解析文档——一次正则相关的进程崩溃
  不能连带打挂整套基准。

模块被门控 `blocked` 时算例记 `blocked_skip`（显式说明，不算通过，也不算崩溃）。
"""

import hashlib
import json
import os
from typing import Any, Dict, List, Tuple

from .engine.core import DISCLAIMER, run_case
from .engine.errors import EngineError, ExprError, InputError
from .kb.fingerprint import data_fingerprint
from .kb.loader import load_kb
from .parse.slots import canonical_value
from .rules.engine import findings_tokens, run_rules

_FORCE_SCALE = {"N": 1.0, "kN": 1000.0}

# 解析 F1 与核查指标的门槛（plan/05 §六）
PARSE_F1_GATE = 0.95
DETECTION_GATE = 0.95

# 语料真值里的 `grade_alt` 是生成器的变量名，语义是"同一槽位的第二个取值"，
# 不是另一个字段。评测按 (slot, value) 事实集对账，别名在此显式登记。
TRUTH_SLOT_ALIASES = {"grade_alt": "grade"}


def _card(record: Dict[str, Any]) -> Dict[str, Any]:
    raw = dict(record.get("inputs") or {})
    raw["case_id"] = str(record.get("case_id", ""))
    raw["module"] = record.get("module")
    return raw


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _compare(expected: Dict[str, Any], tolerance: Dict[str, Any],
             result: Dict[str, Any]) -> Tuple[bool, List[str]]:
    details = []
    ok = True
    for field in sorted(expected):
        want = expected[field]
        got = result.get(field)
        if field == "conclusion" or isinstance(want, str):
            if got != want:
                ok = False
                details.append("conclusion 期望 %s，实际 %s" % (want, got))
            continue
        if _is_number(want):
            tol = tolerance.get(field)
            if tol is None or not _is_number(tol):
                ok = False
                details.append("%s 未登记容差（口径 K3：真值比对容差逐算例登记）" % field)
                continue
            if not _is_number(got):
                ok = False
                details.append("%s 期望 %s，实际 %r（引擎未产出该量）" % (field, want, got))
                continue
            if abs(float(got) - float(want)) > float(tol):
                ok = False
                details.append("%s 期望 %s±%s，实际 %s" % (field, want, tol, got))
            continue
        if got != want:
            ok = False
            details.append("%s 期望 %r，实际 %r" % (field, want, got))
    return ok, details


def _unit_variant(card: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """把同一物理荷载换成另一种力单位表达，其余不变（口径 K1 的不变性断言）。"""
    units = dict(card.get("units") or {})
    current = units.get("force", "N")
    if current not in _FORCE_SCALE:
        return card, "skip"
    other = "kN" if current == "N" else "N"
    factor = _FORCE_SCALE[current] / _FORCE_SCALE[other]
    variant = json.loads(json.dumps(card, sort_keys=True))
    variant.setdefault("units", {})["force"] = other
    forces = variant.get("forces") or {}
    for name in sorted(forces):
        if name in ("N", "V", "T"):
            forces[name] = float(forces[name]) * factor
    return variant, other


def _digest(result: Dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(result, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def run_cases(kb) -> Dict[str, Any]:
    verified = [r for r in kb.records.get("case", [])
                if isinstance(r, dict) and r.get("status") == "verified"]
    pending = [str(r.get("case_id", "")) for r in kb.records.get("case", [])
               if isinstance(r, dict) and r.get("status") not in ("verified",)]
    rows = []
    passed = 0
    for record in sorted(verified, key=lambda r: str(r.get("case_id", ""))):
        case_id = str(record.get("case_id", ""))
        row = {"case_id": case_id, "module": record.get("module"), "status": "error",
               "details": []}
        try:
            result = run_case(kb, _card(record))
        except InputError as exc:
            row["status"] = "input_error"
            row["details"] = ["参数卡不可用：%s" % exc]
            rows.append(row)
            continue
        except (EngineError, ExprError) as exc:
            row["status"] = "engine_error"
            row["details"] = ["数据/引擎失败：%s" % exc]
            rows.append(row)
            continue

        if result["conclusion"] == "blocked":
            row["status"] = "blocked_skip"
            row["details"] = ["依赖未核对，未对账（不静默通过，口径 K6）；缺 %d 项，"
                              "首项 %s/%s" % (
                                  len(result["blocked"]),
                                  result["blocked"][0]["kind"] if result["blocked"] else "-",
                                  result["blocked"][0]["id"] if result["blocked"] else "-")]
            rows.append(row)
            continue

        tolerance = record.get("tolerance") if isinstance(record.get("tolerance"), dict) else {}
        ok, details = _compare(record.get("expected") or {}, tolerance, result)
        row["status"] = "pass" if ok else "fail"
        row["details"] = details
        row["ratio"] = result["ratio"]
        row["conclusion"] = result["conclusion"]
        if ok:
            passed += 1
        rows.append(row)

    denominator = len(verified)
    return {
        "denominator": denominator,
        "passed": passed,
        "pass_rate": (float(passed) / denominator) if denominator else None,
        "rows": rows,
        "pending_case_ids": sorted(set(pending)),
    }


def run_selfcheck_samples(kb) -> List[Dict[str, Any]]:
    """自校验样例：确定性 + 单位不变性。断言文本里的单调性等依赖未核对数值，留给夹具测试。"""
    out = []
    for record in sorted(kb.records.get("selfcheck", []),
                         key=lambda r: str(r.get("case_id", ""))):
        if not isinstance(record, dict):
            continue
        case_id = str(record.get("case_id", ""))
        row = {"case_id": case_id, "module": record.get("module"), "status": "error",
               "details": []}
        wants_rejection = record.get("expect_input_error") is True
        card = _card(record)
        try:
            first = run_case(kb, card)
        except InputError as exc:
            if wants_rejection:
                row["status"] = "ok"
                row["details"] = ["按要求判输入不可用（退出码 2 语义）：%s" % exc]
            else:
                row["status"] = "input_error"
                row["details"] = ["自校验样例的参数卡不合法（应作为缺陷修数据）：%s" % exc]
            out.append(row)
            continue
        except (EngineError, ExprError) as exc:
            row["status"] = "engine_error"
            row["details"] = ["%s" % exc]
            out.append(row)
            continue
        if wants_rejection:
            row["status"] = "fail"
            row["details"] = ["样例要求判输入不可用，但引擎接受了该参数卡（范围纪律失效）"]
            out.append(row)
            continue

        try:
            again = run_case(kb, card)
            variant, toggled = _unit_variant(card)
            third = run_case(kb, variant)
        except (EngineError, ExprError, InputError) as exc:
            row["status"] = "engine_error"
            row["details"] = ["重复运行或单位换算变体失败：%s" % exc]
            out.append(row)
            continue

        problems = []
        if _digest(first) != _digest(again):
            problems.append("同输入两次运行的 Result 不一致（口径 K8）")
        if toggled != "skip":
            if (first.get("ratio") is None) != (third.get("ratio") is None):
                problems.append("换算力单位后 blocked/出数值状态翻转（口径 K1）")
            elif first.get("ratio") is not None and first["ratio"] != third["ratio"]:
                problems.append("力单位从 %s 换成 %s 后 ratio 变化（口径 K1：换算只在入口层）" % (
                    (card.get("units") or {}).get("force", "N"), toggled))
        row["status"] = "fail" if problems else "ok"
        row["details"] = problems or ["确定性一致；单位不变性成立"]
        row["conclusion"] = first["conclusion"]
        row["blocked_count"] = len(first["blocked"])
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# 解析 / 核查配对评测（plan/05 §六 的 `sdc bench --parse` 与 `--audit`）
# ---------------------------------------------------------------------------

def _fact(slot: str, raw: Any) -> Tuple[str, str]:
    canon = canonical_value(slot, str(raw))
    return (slot, ("%.10g" % canon) if canon is not None else str(raw))


def _truth_facts(doc: Dict[str, Any]) -> List[Tuple[str, str]]:
    return sorted(set(
        _fact(TRUTH_SLOT_ALIASES.get(slot, slot), value)
        for slot, value in (doc.get("slots") or {}).items()))


def _ir_facts(ir: Dict[str, Any]) -> List[Tuple[str, str]]:
    return sorted(set(_fact(item["slot"], item["value"])
                      for item in ir.get("slot_evidence") or []))


def ir_files_by_doc(ir_dir: str) -> Dict[str, str]:
    """IR 目录 → {doc_id（= 文件名主干）: 路径}。缺失的语料在评测里记 missing_ir。"""
    if not os.path.isdir(ir_dir):
        return {}
    out = {}
    for name in sorted(os.listdir(ir_dir)):
        if name.endswith(".ir.json"):
            out[name[: -len(".ir.json")]] = os.path.join(ir_dir, name)
    return out


def _groundtruth_documents(data_dir: str) -> List[Dict[str, Any]]:
    path = os.path.join(data_dir, "synth", "groundtruth.json")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.loads(handle.read())
    except OSError as exc:
        raise InputError("合成语料真值读取失败：%s" % exc)
    except ValueError as exc:
        raise InputError("合成语料真值不是合法 JSON：%s（%s）" % (path, exc))
    documents = payload.get("documents")
    if not isinstance(documents, list) or not documents:
        raise InputError("合成语料真值缺少 documents（先跑 `sdc synth`）")
    return documents


def _prf(tp: int, fp: int, fn: int) -> Tuple[Any, Any, Any]:
    precision = float(tp) / (tp + fp) if (tp + fp) else None
    recall = float(tp) / (tp + fn) if (tp + fn) else None
    denom = (2 * tp + fp + fn)
    f1 = float(2 * tp) / denom if denom else None
    return precision, recall, f1


def run_parse_eval(data_dir: str, ir_dir: str) -> Dict[str, Any]:
    """字段级 P/R/F1：解析结果与 `data/synth/groundtruth.json` 的 (槽位, 取值) 事实集对账。"""
    documents = _groundtruth_documents(data_dir)
    available = ir_files_by_doc(ir_dir)
    rows = []
    totals = {"tp": 0, "fp": 0, "fn": 0}
    per_slot: Dict[str, Dict[str, int]] = {}

    missing = []  # type: List[str]
    for doc in sorted(documents, key=lambda d: str(d.get("doc_id", ""))):
        doc_id = str(doc.get("doc_id", ""))
        path = available.get(doc_id)
        if path is None:
            missing.append(doc_id)
            continue
        with open(path, "r", encoding="utf-8") as handle:
            ir = json.loads(handle.read())
        want = _truth_facts(doc)
        got = _ir_facts(ir)
        want_set, got_set = set(want), set(got)
        tp, fp, fn = len(want_set & got_set), len(got_set - want_set), len(want_set - got_set)
        totals["tp"] += tp
        totals["fp"] += fp
        totals["fn"] += fn
        for slot, _value in sorted(want_set & got_set):
            per_slot.setdefault(slot, {"tp": 0, "fp": 0, "fn": 0})["tp"] += 1
        for slot, _value in sorted(got_set - want_set):
            per_slot.setdefault(slot, {"tp": 0, "fp": 0, "fn": 0})["fp"] += 1
        for slot, _value in sorted(want_set - got_set):
            per_slot.setdefault(slot, {"tp": 0, "fp": 0, "fn": 0})["fn"] += 1
        rows.append({"doc_id": doc_id, "ir": os.path.basename(path),
                     "tp": tp, "fp": fp, "fn": fn,
                     "missed": sorted("%s=%s" % pair for pair in (want_set - got_set)),
                     "extra": sorted("%s=%s" % pair for pair in (got_set - want_set))})

    precision, recall, f1 = _prf(totals["tp"], totals["fp"], totals["fn"])
    slot_rows = {}
    for slot in sorted(per_slot):
        counts = per_slot[slot]
        p, r, s = _prf(counts["tp"], counts["fp"], counts["fn"])
        slot_rows[slot] = {"tp": counts["tp"], "fp": counts["fp"], "fn": counts["fn"],
                           "precision": p, "recall": r, "f1": s}

    return {
        "ir_dir": ir_dir,
        "doc_total": len(documents),
        "doc_evaluated": len(rows),
        "missing_ir": missing,
        "totals": dict(totals),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "gate": PARSE_F1_GATE,
        "per_slot": slot_rows,
        "rows": rows,
        "ok": bool(missing == [] and rows and f1 is not None and f1 >= PARSE_F1_GATE),
    }


def run_audit_eval(kb, data_dir: str, ir_dir: str) -> Dict[str, Any]:
    """检出率/误报：按 K4「文档全部非 pass 集合」对账，`suspicious` 同样计为检出。

    另单列「可硬判 abnormal 的规则分母」——只含有效档位 verified 的规则；为 0 时显式说明，
    这是依据档位的诚实结果，不是漏检（plan/04 §四 的档位收紧不打挂检出率）。
    """
    documents = _groundtruth_documents(data_dir)
    available = ir_files_by_doc(ir_dir)
    rules = [r for r in kb.records.get("rule", []) if isinstance(r, dict)]

    from .rules.gate import effective_status
    verified_rules = [r for r in rules
                      if effective_status(kb, r)[0] == "verified"]

    injections_total = 0
    injections_detected = 0
    by_type: Dict[str, Dict[str, int]] = {}
    false_positives: List[Dict[str, Any]] = []
    missed: List[Dict[str, Any]] = []
    uncovered_expected: List[Dict[str, str]] = []
    level_tally = {"abnormal": 0, "suspicious": 0}
    findings_total = 0
    findings_with_clause = 0
    rows = []  # type: List[Dict[str, Any]]
    missing = []  # type: List[str]

    for doc in sorted(documents, key=lambda d: str(d.get("doc_id", ""))):
        doc_id = str(doc.get("doc_id", ""))
        path = available.get(doc_id)
        if path is None:
            missing.append(doc_id)
            continue
        with open(path, "r", encoding="utf-8") as handle:
            ir = json.loads(handle.read())
        report = run_rules(kb, ir)
        got = findings_tokens(report)
        expected = list(doc.get("expected_non_pass") or [])
        got_set, expected_set = set(got), set(expected)

        for finding in report["findings"]:
            if finding["level"] in level_tally:
                level_tally[finding["level"]] += 1
            findings_total += 1
            if finding["clause_ids"]:
                findings_with_clause += 1

        for token in sorted(got_set - expected_set):
            false_positives.append({"doc_id": doc_id, "token": token})
        for token in sorted(expected_set - got_set):
            uncovered_expected.append({"doc_id": doc_id, "token": token})

        for mark in doc.get("injections") or []:
            primary = mark.get("primary") or {}
            rule_id = str(primary.get("rule", ""))
            kind = str(mark.get("type", ""))
            bucket = by_type.setdefault(kind, {"total": 0, "detected": 0,
                                               "abnormal": 0, "suspicious": 0})
            bucket["total"] += 1
            injections_total += 1
            if rule_id in got_set:
                bucket["detected"] += 1
                injections_detected += 1
                for finding in report["findings"]:
                    if finding["rule_id"] == rule_id and finding["level"] in bucket:
                        bucket[finding["level"]] += 1
            else:
                missed.append({"doc_id": doc_id, "type": kind, "rule_id": rule_id,
                               "note": "注入项未被检出"})

        rows.append({"doc_id": doc_id, "clean": doc.get("clean") is True,
                     "conclusion": report["conclusion"],
                     "findings": [f["rule_id"] for f in report["findings"]],
                     "not_activated": len(report["not_activated"])})

    rate = (float(injections_detected) / injections_total) if injections_total else None
    return {
        "ir_dir": ir_dir,
        "doc_total": len(documents),
        "doc_evaluated": len(rows),
        "missing_ir": missing,
        "rules_total": len(rules),
        "hard_judge_denominator": len(verified_rules),
        "hard_judge_note": ("有效档位 verified 的规则 %d 条，可判 abnormal 的检出上限另有分母"
                            % len(verified_rules)) if verified_rules else
                           "分母 0：全部规则的依据只到 located/pending，最高只能判 suspicious"
                           "（plan/04 §四），语料真值里的 expect=abnormal 是规则升 verified 后的档位",
        "injection_total": injections_total,
        "injection_detected": injections_detected,
        "detection_rate": rate,
        "detection_gate": DETECTION_GATE,
        "by_type": dict(sorted(by_type.items())),
        "false_positives": false_positives,
        "missed": missed,
        "uncovered_expected": uncovered_expected,
        "level_tally": level_tally,
        "findings_total": findings_total,
        "findings_with_clause": findings_with_clause,
        "rows": rows,
        "ok": bool(not missing and not false_positives and rate is not None
                   and rate >= DETECTION_GATE),
    }


def build_report(kb, only_cases: bool = False) -> Dict[str, Any]:
    cases = run_cases(kb)
    report = {
        "data_dir": kb.data_dir,
        "data_fingerprint": data_fingerprint(kb.data_dir),
        "cases": cases,
        "selfcheck_samples": [] if only_cases else run_selfcheck_samples(kb),
    }
    report["ok"] = (cases["denominator"] > 0
                    and cases["passed"] == cases["denominator"]
                    and all(row["status"] == "ok" for row in report["selfcheck_samples"]))
    return report


def render_parse(report: Dict[str, Any]) -> str:
    out = ["=" * 72, "sdc bench --parse（字段级 P/R/F1，对账 data/synth 真值）", "=" * 72]
    out.append("IR 目录：%s" % report["ir_dir"])
    out.append("语料 %d 份，参与对账 %d 份" % (report["doc_total"], report["doc_evaluated"]))
    if report["missing_ir"]:
        out.append("缺少 IR：%s（先跑 `sdc parse --dir … --out-dir …`）"
                   % ", ".join(report["missing_ir"]))
    t = report["totals"]
    out.append("事实计数：TP %d / FP %d / FN %d" % (t["tp"], t["fp"], t["fn"]))
    for name, value in (("精确率", report["precision"]), ("召回率", report["recall"]),
                        ("F1", report["f1"])):
        out.append("%-6s：%s（门槛 %.2f）" % (
            name, "n/a" if value is None else "%.4f" % value, report["gate"]))
    out.append("")
    out.append("分槽位：")
    out.append("%-12s %5s %5s %5s %8s" % ("slot", "TP", "FP", "FN", "F1"))
    for slot in sorted(report["per_slot"]):
        row = report["per_slot"][slot]
        out.append("%-12s %5d %5d %5d %8s" % (
            slot, row["tp"], row["fp"], row["fn"],
            "n/a" if row["f1"] is None else "%.4f" % row["f1"]))
    bad = [row for row in report["rows"] if row["fp"] or row["fn"]]
    if bad:
        out.append("")
        out.append("不一致清单（最多 20 条）：")
        for row in bad[:20]:
            out.append("  %s 漏 %s / 多 %s" % (
                row["doc_id"], row["missed"] or "-", row["extra"] or "-"))
    out.append("")
    out.append("结论：%s" % ("达标" if report["ok"] else "未达标（见上）"))
    out.append("免责声明：%s" % DISCLAIMER)
    return "\n".join(out)


def render_audit(report: Dict[str, Any]) -> str:
    out = ["=" * 72, "sdc bench --audit（缺陷检出率 / 误报，按 K4 非 pass 集合对账）", "=" * 72]
    out.append("IR 目录：%s；规则 %d 条" % (report["ir_dir"], report["rules_total"]))
    out.append("语料 %d 份，参与对账 %d 份" % (report["doc_total"], report["doc_evaluated"]))
    if report["missing_ir"]:
        out.append("缺少 IR：%s" % ", ".join(report["missing_ir"]))
    rate = report["detection_rate"]
    out.append("注入项 %d 处，检出 %d 处，检出率 %s（门槛 %.2f；suspicious 同样计为检出）" % (
        report["injection_total"], report["injection_detected"],
        "n/a" if rate is None else "%.4f" % rate, report["detection_gate"]))
    out.append("误报（非注入项被判非 pass）：%d 处（硬门 0）" % len(report["false_positives"]))
    out.append("等级分布：abnormal %d / suspicious %d" % (
        report["level_tally"]["abnormal"], report["level_tally"]["suspicious"]))
    out.append("")
    out.append("分类计数：")
    for kind in sorted(report["by_type"]):
        row = report["by_type"][kind]
        out.append("  %-28s 注入 %d，检出 %d（abnormal %d / suspicious %d）" % (
            kind, row["total"], row["detected"], row["abnormal"], row["suspicious"]))
    out.append("")
    out.append("[可硬判分母] %d —— %s" % (
        report["hard_judge_denominator"], report["hard_judge_note"]))
    if report["missed"]:
        out.append("")
        out.append("漏检：")
        for item in report["missed"]:
            out.append("  - %s %s（%s）：%s" % (
                item["doc_id"], item["rule_id"], item["type"], item["note"]))
    if report["false_positives"]:
        out.append("")
        out.append("误报明细：")
        for item in report["false_positives"]:
            out.append("  - %s → %s" % (item["doc_id"], item["token"]))
    if report["uncovered_expected"]:
        out.append("")
        out.append("期望集中未出现的连带结论（不计误报，但要说清差在哪）：")
        for item in report["uncovered_expected"]:
            out.append("  - %s ← %s" % (item["doc_id"], item["token"]))
    out.append("")
    out.append("结论：%s" % ("达标" if report["ok"] else "未达标（见上）"))
    out.append("免责声明：%s" % DISCLAIMER)
    return "\n".join(out)


def render_text(report: Dict[str, Any]) -> str:
    cases = report["cases"]
    out = ["=" * 72, "sdc bench（算例真值库对账）", "=" * 72]
    out.append("数据目录：%s" % report["data_dir"])
    out.append("data_fingerprint：%s" % report["data_fingerprint"])
    out.append("")
    out.append("[1] 通过率（分母只含 status=verified 算例，口径 K6）")
    if not cases["denominator"]:
        out.append("  分母 0，样本待补 —— 无来源可确证的算例一律不作真值（口径 K7/D07）。")
        out.append("  这是诚实结果，不是通过；不得用编造来源换取通过率数字。")
    else:
        out.append("  %d / %d 通过，通过率 %.1f%%" % (
            cases["passed"], cases["denominator"], 100.0 * cases["pass_rate"]))
    for row in cases["rows"]:
        mark = {"pass": "OK  ", "fail": "FAIL", "blocked_skip": "SKIP",
                "input_error": "IN  ", "engine_error": "ERR "}.get(row["status"], row["status"])
        out.append("  [%s] %s (%s)" % (mark, row["case_id"], row["module"]))
        for detail in row["details"]:
            out.append("        · %s" % detail)
    if cases["pending_case_ids"]:
        out.append("  未计入分母的算例：%s" % ", ".join(cases["pending_case_ids"]))
    out.append("")

    if report["selfcheck_samples"]:
        out.append("[2] 引擎自校验样例（不进通过率分母，口径 D07）")
        for row in report["selfcheck_samples"]:
            extra = ""
            if row["status"] == "ok":
                extra = "（结论 %s，blocked 项 %d）" % (
                    row.get("conclusion", "-"), row.get("blocked_count", 0))
            out.append("  [%s] %s (%s)%s" % (
                "OK  " if row["status"] == "ok" else row["status"], row["case_id"],
                row["module"], extra))
            for detail in row["details"]:
                out.append("        · %s" % detail)
        out.append("")

    out.append("免责声明：%s" % DISCLAIMER)
    return "\n".join(out)
