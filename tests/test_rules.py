"""规则层：闸门矩阵（K5）、schema 陷阱、判定引擎与夹具上的 abnormal 通路。

这一组测试是 M3 的纪律核心：**依据只到 located 的 limit/construct/presence 规则不得出 abnormal**。
它由矩阵单点决定（`rules/gate.py`），所以既要测"压得住"，也要测"该放的放得开"
（consistency 在 located 档就是 abnormal，夹具的 verified 档也是 abnormal）。
"""

import json
import os

import pytest

from _helpers import FIXTURE_RULES_DIR, REPO_DATA_DIR, patch_status
from sdc.kb.loader import load_kb
from sdc.kb.schema import validate_record
from sdc.parse import build_ir
from sdc.rules import run_rules
from sdc.rules.engine import findings_tokens
NL = chr(10)
from sdc.rules.gate import COLUMN, LEVEL_MATRIX, effective_status, level_for

DOCX = os.path.join(REPO_DATA_DIR, "synth", "docx")
FIXTURE_DOCX = os.path.join(FIXTURE_RULES_DIR, "docs")


def _ir_for(name):
    return build_ir(os.path.join(FIXTURE_DOCX, name))


# ---------------------------------------------------------------------------
# 矩阵本体：与 plan/04 §四 一一对应
# ---------------------------------------------------------------------------

def test_matrix_matches_the_plan_table():
    assert LEVEL_MATRIX[("consistency", "located")] == "abnormal"
    assert LEVEL_MATRIX[("presence", "located")] == "suspicious"
    assert LEVEL_MATRIX[("limit", "located")] == "suspicious"
    assert LEVEL_MATRIX[("limit", "pending")] is None
    assert LEVEL_MATRIX[("presence", "pending")] == "suspicious"
    assert LEVEL_MATRIX[("consistency", "verified")] == "abnormal"
    for check_type in ("limit", "construct", "cross_param"):
        assert COLUMN[check_type] == "limit"


def test_construct_and_pending_limit_emit_nothing():
    assert level_for("construct", "missing", "pending") is None
    assert level_for("construct", "mismatch", "located") == "suspicious"
    assert level_for("limit", "mismatch", "verified") == "abnormal"
    assert level_for("limit", "ambiguous", "verified") == "suspicious"


def test_effective_status_is_min_of_rule_and_basis():
    kb = load_kb(FIXTURE_RULES_DIR)
    capped = [r for r in kb.records["rule"] if r["id"] == "FX-R-HF-CAPPED"][0]
    assert capped["status"] == "verified"
    status, detail = effective_status(kb, capped)
    assert status == "located", detail
    honest = [r for r in kb.records["rule"] if r["id"] == "FX-R-HF-VERIFIED"][0]
    assert effective_status(kb, honest)[0] == "verified"


def test_effective_status_treats_missing_clause_as_pending():
    kb = load_kb(FIXTURE_RULES_DIR)
    rule = {"status": "verified", "basis": [{"clause_id": "不存在", "gist": "x"}]}
    assert effective_status(kb, rule) == ("pending", ["不存在=missing"])


# ---------------------------------------------------------------------------
# 夹具：verified 档真的能出 abnormal（真实数据永远跑不到这半张矩阵）
# ---------------------------------------------------------------------------

def test_fixture_verified_rules_emit_abnormal_and_cap_the_located_one():
    kb = load_kb(FIXTURE_RULES_DIR)
    report = run_rules(kb, _ir_for("doc_low.txt"))
    by_rule = dict((f["rule_id"], f) for f in report["findings"])

    assert by_rule["FX-R-WELD-ORDINAL"]["level"] == "abnormal"
    assert by_rule["FX-R-MU-PRESENCE"]["level"] == "abnormal"
    assert by_rule["FX-R-HF-VERIFIED"]["level"] == "abnormal"
    # 同一事实（焊脚 4mm < 限值），自称 verified 但依据 located 的规则只能可疑
    assert by_rule["FX-R-HF-CAPPED"]["level"] == "suspicious"
    assert by_rule["FX-R-HF-CAPPED"]["status"] == "located"
    assert report["counts"]["abnormal"] == 3
    assert "FX-C-WELD" in report["mandatory_clause_ids"]


def test_fixture_clean_doc_produces_no_findings():
    kb = load_kb(FIXTURE_RULES_DIR)
    report = run_rules(kb, _ir_for("doc_ok.txt"))
    assert report["findings"] == []
    assert report["conclusion"] == "pass"


def test_report_is_byte_stable():
    kb = load_kb(FIXTURE_RULES_DIR)
    ir = _ir_for("doc_low.txt")
    first = json.dumps(run_rules(kb, ir), sort_keys=True, ensure_ascii=False)
    second = json.dumps(run_rules(kb, ir), sort_keys=True, ensure_ascii=False)
    assert first == second


# ---------------------------------------------------------------------------
# 真实数据：located 封顶 + 未启用清单
# ---------------------------------------------------------------------------

def test_real_data_rules_never_emit_abnormal_except_consistency():
    kb = load_kb(REPO_DATA_DIR)
    offenders = []
    for name in sorted(os.listdir(DOCX)):
        report = run_rules(kb, build_ir(os.path.join(DOCX, name)))
        for finding in report["findings"]:
            if finding["level"] == "abnormal" and finding["check_type"] != "consistency":
                offenders.append((name, finding["rule_id"], finding["status"]))
    assert offenders == [], offenders


def test_real_data_threshold_rules_are_disabled_not_guessed():
    kb = load_kb(REPO_DATA_DIR)
    report = run_rules(kb, build_ir(os.path.join(DOCX, "SYNTH-0000.docx")))
    reasons = dict((item["rule_id"], item["reason"]) for item in report["not_activated"])
    assert "限值（min_hf）未核对" in reasons["R-WELD-MIN-HF-CONSTRUCT"]
    assert "限值（fire_hour）未核对" in reasons["R-FIRE-HOUR-LIMIT"]
    assert "阈值（weld_class）未核对" in reasons["R-WELD-CLASS-ORDINAL"]


def test_category_isolation_keeps_irrelevant_rules_out():
    kb = load_kb(REPO_DATA_DIR)
    report = run_rules(kb, build_ir(os.path.join(DOCX, "SYNTH-0000.docx")))
    reasons = dict((item["rule_id"], item["reason"]) for item in report["not_activated"])
    assert "类目隔离" in reasons["R-HIGH-TEMP-PROTECTION"]
    # 螺栓规则在这份文档上被激活且判过（clean 语料主受力段落写明摩擦型）⇒ 既不在 findings
    # 也不在 not_activated，这才是"误报 0"的机制
    assert "R-BOLT-GRADE-MISMATCH" not in reasons
    assert "R-BOLT-GRADE-MISMATCH" not in [f["rule_id"] for f in report["findings"]]


def test_findings_tokens_cover_rule_id_and_also_expect():
    kb = load_kb(REPO_DATA_DIR)
    ir = build_ir(os.path.join(DOCX, "SYNTH-0013.docx"))
    report = run_rules(kb, ir)
    tokens = findings_tokens(report)
    assert "R-STEEL-GRADE-CONSISTENCY" in tokens
    assert "连接板与主体材质不匹配需人工确认" in tokens


def test_paragraph_scoped_rule_does_not_let_other_paragraphs_supply_evidence(tmp_path):
    """主受力段与"摩擦面"段分开写 ⇒ 段落级作用域要报，文档级作用域会漏检。"""
    import shutil

    kb_dir = os.path.join(str(tmp_path), "data")
    shutil.copytree(REPO_DATA_DIR, kb_dir)
    doc = os.path.join(str(tmp_path), "split.txt")
    texts = ("主受力连接采用4.6级螺栓，普通螺栓施工按常规要求。",
             "摩擦面处理为喷砂，抗滑移系数取0.40。")
    with open(doc, "w", encoding="utf-8", newline=NL) as handle:
        handle.write(NL.join(texts) + NL)
    ir = build_ir(doc)

    findings = run_rules(load_kb(kb_dir), ir)["findings"]
    hit = [f for f in findings if f["rule_id"] == "R-BOLT-GRADE-MISMATCH"]
    assert hit and hit[0]["paras"] == [0], hit

    _patch_rule_scope(kb_dir, "R-BOLT-GRADE-MISMATCH", "document")
    relaxed = run_rules(load_kb(kb_dir), ir)["findings"]
    assert not [f for f in relaxed if f["rule_id"] == "R-BOLT-GRADE-MISMATCH"], relaxed


def _patch_rule_scope(data_dir, rule_id, scope):
    path = os.path.join(data_dir, "rules", "description_rules.json")
    with open(path, "r", encoding="utf-8") as handle:
        records = json.loads(handle.read())
    for record in records:
        if record["id"] == rule_id:
            record["scope"] = scope
    with open(path, "w", encoding="utf-8", newline=NL) as handle:
        handle.write(json.dumps(records, ensure_ascii=False, indent=2, sort_keys=True) + NL)
def _rule_record(assertion=None, **overrides):
    base = {
        "id": "R-T-001", "name": "测试规则", "check_type": "limit", "status": "located",
        "basis": [{"clause_id": "GB50017-2017:11.3.5", "gist": "构造限值"}],
        "assert": {"kind": "numeric_min", "slot": "min_hf", "bound": None, "unit": "mm"},
    }
    if assertion is not None:
        base["assert"] = assertion
    base.update(overrides)
    return base


def test_located_rule_carrying_a_threshold_is_a_data_problem():
    kb = load_kb(REPO_DATA_DIR)
    known = {"clause": set(kb.by_id("clause")), "rule": set(), "symbol": set(), "table": set(),
             "formula": set(), "case": set(), "selfcheck": set()}
    sneaky = _rule_record(assertion={"kind": "numeric_min", "slot": "min_hf", "bound": 5.0})
    problems = validate_record("rule", sneaky, "rules/x.json", known)
    assert any("不得携带" in p["problem"] for p in problems), problems

    honest = _rule_record(status="verified",
                          verified_by={"channel": "纸质规范", "date": "2026-10-07",
                                       "url": "https://example.invalid/11.3.5"})
    problems = validate_record("rule", honest, "rules/x.json", known)
    assert any("必须给出核对过的" in p["problem"] for p in problems), problems


def test_rule_cannot_declare_its_own_level_rules():
    kb = load_kb(REPO_DATA_DIR)
    known = {"clause": set(kb.by_id("clause"))}
    record = _rule_record(level_rules={"missing": "abnormal"})
    problems = validate_record("rule", record, "rules/x.json", known)
    assert any("schema 外字段" in p["problem"] for p in problems), problems


def test_unknown_operators_and_dangling_basis_are_rejected():
    kb = load_kb(REPO_DATA_DIR)
    known = {"clause": set(kb.by_id("clause"))}
    problems = validate_record("rule", _rule_record(when={"regex": "焊脚"}), "r.json", known)
    assert any("未知条件算子" in p["problem"] for p in problems), problems

    problems = validate_record("rule", _rule_record(
        assertion={"kind": "magic", "slot": "min_hf"}), "r.json", known)
    assert any("未知断言算子" in p["problem"] for p in problems), problems

    problems = validate_record("rule", _rule_record(
        basis=[{"clause_id": "GB50017-2017:9.9.9", "gist": "x"}]), "r.json", known)
    assert any("悬空引用" in p["problem"] for p in problems), problems

    problems = validate_record("rule", _rule_record(basis=[]), "r.json", known)
    assert any(p["field"] == "basis" and "无出处" in p["problem"]
               for p in problems), problems


def test_repo_rules_and_checklist_load_without_problems():
    kb = load_kb(REPO_DATA_DIR)
    assert kb.problems == [], kb.problems[:5]
    assert len(kb.records["rule"]) == 10
    assert len(kb.records["checklist"]) == 107
    for rule in kb.records["rule"]:
        assert rule["basis"], rule["id"]
        for entry in rule["basis"]:
            assert entry["clause_id"] in kb.by_id("clause"), (rule["id"], entry)


def test_downgrading_a_rule_basis_leaks_no_abnormal():
    """把夹具里一条已核对依据降回 located ⇒ 全部命中只能可疑（K5 的动态验证）。"""
    import shutil
    import tempfile

    target = os.path.join(tempfile.mkdtemp(), "rules_kb")
    shutil.copytree(FIXTURE_RULES_DIR, target)
    patch_status(target, "clauses", ["FX-C-WELD"], "located")
    kb = load_kb(target)
    report = run_rules(kb, _ir_for("doc_low.txt"))
    levels = dict((f["rule_id"], f["level"]) for f in report["findings"])
    assert levels["FX-R-WELD-ORDINAL"] == "suspicious"
    assert levels["FX-R-HF-VERIFIED"] == "suspicious"
    assert levels["FX-R-MU-PRESENCE"] == "abnormal"     # 依据仍 verified 的那条不受影响


def test_run_rules_rejects_rule_without_assert_kind():
    from sdc.rules.engine import RuleError
    kb = load_kb(REPO_DATA_DIR)
    broken = load_kb(REPO_DATA_DIR)
    broken.records["rule"].append({"id": "R-BROKEN", "check_type": "presence",
                                   "basis": [], "status": "located"})
    with pytest.raises(RuleError):
        run_rules(broken, build_ir(os.path.join(DOCX, "SYNTH-0000.docx")))
