"""仓内真实数据与冻结语料的守门测试（M1 DoD 的「门控跑通 + 位级一致」两项）。

与 tests/test_kb_*.py 的区别：那里用夹具验证规则本身，这里验证**仓库里真实入库的数据**
满足同样的规则，因此任何手改 data/ 的提交都会在这里被拦下。
"""

import os

import pytest

from sdc.engine.errors import EngineError
from sdc.kb import data_fingerprint, load_kb, module_gate
from sdc.kb.schema import MODULES, VERIFIED_BY_CHANNELS
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


def test_verified_records_are_exactly_the_appendix_d_set():
    """verified 不是"随便谁能声称"的档位：本轮唯一升档的是附录 D（06 D22，用户拍板 ±0.001）。

    M1/M2 时代这条测试断言"verified 必须为空"；D22 之后改成**白名单式断言**：
    只有附录 D 的条款/表/符号可以 verified，且必须挂渠道；其余（表体数值、式体）一律没升。
    新增任何 verified 记录都必须先有一条决策记录，否则这里就会红。
    """
    kb = load_kb(DATA)
    allowed_clause = {"GB50017-2017:%s" % no for no in ("D.0.1", "D.0.2", "D.0.3", "D.0.4", "D.0.5")}
    allowed_table = {"T-buckling-curve", "T-buckling-alpha"}
    allowed_symbol = {"phi"}
    for kind, allowed in (("clause", allowed_clause), ("table", allowed_table),
                          ("symbol", allowed_symbol), ("formula", set())):
        verified = set(kb.id_of(kind, r) for r in kb.records[kind]
                       if isinstance(r, dict) and r.get("status") == "verified")
        assert verified == allowed, "%s 的 verified 集合变了：%s" % (kind, sorted(verified))
    for kind in ("clause", "table", "formula", "symbol"):
        for rec in kb.records[kind]:
            if isinstance(rec, dict) and rec.get("status") == "verified":
                channel = (rec.get("verified_by") or {}).get("channel")
                assert channel in VERIFIED_BY_CHANNELS, (kind, rec.get("id"), channel)


def test_promoted_phi_table_is_usable_but_a5_still_blocked():
    """升档的实际效果要能量出来：φ 表能查、能插值、超界不外推；但 A5 仍然不出数值。"""
    from sdc.engine.tables import lookup

    kb = load_kb(DATA)
    assert lookup(kb, "T-buckling-curve", {"section_class": "b"},
                  {"lambda_over_eps_k": 100.0}) == {"phi": 0.555}
    between = lookup(kb, "T-buckling-curve", {"section_class": "b"},
                     {"lambda_over_eps_k": 55.5})["phi"]
    assert 0.83 < between < 0.84, between          # 55 与 56 之间线性内插
    with pytest.raises(EngineError):               # 超表界拒绝，不外推（K18）
        lookup(kb, "T-buckling-curve", {"section_class": "a"}, {"lambda_over_eps_k": 400.0})
    # 分组轴没给 ⇒ 返回 None（编排层记"未查表"），绝不把 a/b/c/d 四类行混在一起插值
    assert lookup(kb, "T-buckling-curve", {}, {"lambda_over_eps_k": 100.0}) is None
    with pytest.raises(EngineError):               # 词表外的分类不给兜底值
        lookup(kb, "T-buckling-curve", {"section_class": "e"}, {"lambda_over_eps_k": 100.0})
    gate = module_gate("column_buckling", kb)
    assert gate["status"] == "blocked"
    unready = {(item["kind"], item["id"]) for item in gate["unready"]}
    assert ("formula", "F-7.2.1-1") in unready and ("formula", "F-D.0.5-1") in unready
    assert ("table", "T-buckling-curve") not in unready, "φ 表已升 verified，不该再阻塞"


def test_every_module_is_blocked_while_core_data_unverified():
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
