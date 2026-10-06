"""仓内真实数据与冻结语料的守门测试（M1 DoD 的「门控跑通 + 位级一致」两项）。

与 tests/test_kb_*.py 的区别：那里用夹具验证规则本身，这里验证**仓库里真实入库的数据**
满足同样的规则，因此任何手改 data/ 的提交都会在这里被拦下。
"""

import os

from sdc.kb import data_fingerprint, load_kb, module_gate
from sdc.kb.schema import MODULES
from sdc.selfcheck import build_report
from sdc.synth.generator import compare_corpus

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "data")


def test_repo_knowledge_base_is_clean():
    kb = load_kb(DATA)
    assert kb.problems == [], kb.problems[:5]


def test_repo_has_clause_table_and_symbol_inventory():
    kb = load_kb(DATA)
    assert len(kb.records["clause"]) >= 60, "M1 DoD：条款库 ≥60 条"
    assert len(kb.records["table"]) >= 9, "M1 DoD：9 张数值表条目建好"
    assert len(kb.records["symbol"]) > 0 and len(kb.records["formula"]) > 0


def test_no_record_is_verified_without_being_rechecked():
    """本轮纪律：在线渠道拿不到表体与式体，任何 verified 都属越界（plan/07 §四）。"""
    kb = load_kb(DATA)
    for kind in ("clause", "table", "formula", "symbol"):
        verified = [r for r in kb.records[kind] if isinstance(r, dict)
                    and r.get("status") == "verified"]
        assert verified == [], "%s 出现 verified：%s" % (kind, verified[:2])


def test_every_module_is_blocked_while_nothing_verified():
    kb = load_kb(DATA)
    for module in MODULES:
        gate = module_gate(module, kb)
        assert gate["status"] == "blocked", module
        assert gate["unready"], (module, gate["reason"])
        assert "ratio" not in gate


def test_selfcheck_on_repo_data_reports_ok():
    report = build_report(DATA)
    assert report["ok"] is True
    assert report["counts"]["case"]["total"] == 0, "真值算例来源未落实前必须为空"
    assert report["counts"]["selfcheck"]["total"] >= 8
    assert len(report["data_fingerprint"]) == 64


def test_repo_data_fingerprint_is_stable():
    assert data_fingerprint(DATA) == data_fingerprint(DATA)


def test_committed_corpus_is_reproducible():
    """位级一致守门：改模板或手改 data/synth 都会在这里失败（口径 K8）。"""
    assert compare_corpus(DATA) == []
