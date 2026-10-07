"""门控失败路径（M2 DoD 第 3 条，本项目含金量所在）。

要证明的事：**引用 located/pending 数据却出了数值 = 测试红**。
所以这里既测仓内真实数据（全 located ⇒ 全 blocked），也用夹具副本主动制造
「未核对但带着数值/式体」的陷阱，逼引擎去取那些值，确认它取不到。
"""

import pytest

from _helpers import (CARD_A1, CARD_A2, CARD_A3, CARD_A4, CARD_A5, REPO_DATA_DIR,
                      fixture_copy, patch_status)
from sdc.engine.core import run_case
from sdc.engine.errors import EngineError
from sdc.engine.tables import lookup
from sdc.kb import load_kb
from sdc.kb.schema import MODULES

CARDS = {
    "butt_weld": CARD_A1,
    "fillet_weld": CARD_A2,
    "bolt_normal": CARD_A3,
    "bolt_hsb_friction": CARD_A4,
    "column_buckling": CARD_A5,
}


def _numbers(value):
    """递归找出 Result 里的一切数值（bool 不算）。"""
    found = []
    if isinstance(value, bool):
        return found
    if isinstance(value, (int, float)):
        found.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            found.extend(_numbers(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.extend(_numbers(item))
    return found


@pytest.fixture(scope="module")
def repo_kb():
    return load_kb(REPO_DATA_DIR)


@pytest.mark.parametrize("module", MODULES)
def test_repo_data_blocks_every_module_and_produces_no_number(repo_kb, module):
    result = run_case(repo_kb, CARDS[module])
    assert result["conclusion"] == "blocked"
    assert result["ratio"] is None
    assert result["steps"] == []
    assert result["limits"] == []
    assert result["basis"] == []
    assert _numbers({k: v for k, v in result.items() if k != "meta"}) == []


@pytest.mark.parametrize("module", MODULES)
def test_blocked_lists_every_unready_dependency_with_kind_and_id(repo_kb, module):
    result = run_case(repo_kb, CARDS[module])
    blocked = result["blocked"]
    assert blocked, "blocked 项不得为空，否则用户看不到还缺什么"
    for item in blocked:
        assert item["kind"] in ("formula", "clause", "symbol", "table")
        assert item["id"]
        assert item["status"] in ("pending", "located", "missing")
        assert item["reason"]
    ids = set((item["kind"], item["id"]) for item in blocked)
    assert len(ids) == len(blocked), "blocked[] 出现重复项，说明门控去重没做好"


def test_located_table_that_still_carries_values_cannot_leak(tmp_path):
    """陷阱：表降到 located 但 values 一个没删——引擎必须仍然拒取。"""
    kb_dir = fixture_copy(tmp_path)
    patch_status(kb_dir, "tables", ["FX-T-FILLET"], "located")
    kb = load_kb(kb_dir)
    assert not kb.problems, kb.problems

    result = run_case(kb, CARD_A2)
    assert result["conclusion"] == "blocked"
    assert result["ratio"] is None
    assert _numbers({k: v for k, v in result.items() if k != "meta"}) == []
    assert ("table", "FX-T-FILLET") in [
        (item["kind"], item["id"]) for item in result["blocked"]]


def test_located_formula_with_real_expr_cannot_leak(tmp_path):
    kb_dir = fixture_copy(tmp_path)
    patch_status(kb_dir, "formulas", ["F-FX-A2-SIDE"], "located")
    kb = load_kb(kb_dir)
    result = run_case(kb, CARD_A2)
    assert result["conclusion"] == "blocked"
    assert ("formula", "F-FX-A2-SIDE") in [
        (item["kind"], item["id"]) for item in result["blocked"]]


def test_construct_clause_also_gates_via_reverse_index(tmp_path):
    """构造条款不直接挂在公式的 clause_id 上，靠 clause.formulas 反向进依赖集。
    它未核对就必须挡住计算——否则「构造依据只是 located」会被静默跳过。"""
    kb_dir = fixture_copy(tmp_path)
    patch_status(kb_dir, "clauses", ["FX-C-A2-CONSTRUCT"], "located")
    kb = load_kb(kb_dir)
    result = run_case(kb, CARD_A2)
    assert result["conclusion"] == "blocked"
    assert ("clause", "FX-C-A2-CONSTRUCT") in [
        (item["kind"], item["id"]) for item in result["blocked"]]


def test_unverified_symbol_also_blocks(tmp_path):
    """符号表降到 located：β_f 的对应关系没核对过，就不允许当已知系数用。"""
    kb_dir = fixture_copy(tmp_path)
    patch_status(kb_dir, "symbols", ["beta_f"], "located", id_field="symbol")
    kb = load_kb(kb_dir)
    result = run_case(kb, CARD_A2)
    assert result["conclusion"] == "blocked"
    assert ("symbol", "beta_f") in [
        (item["kind"], item["id"]) for item in result["blocked"]]


def test_direct_table_lookup_refuses_unverified_even_when_called_bypassing_gate(tmp_path):
    """绕过 run_case 直接调查表也必须失败：门控不是只在编排层做一次。"""
    kb_dir = fixture_copy(tmp_path)
    patch_status(kb_dir, "tables", ["FX-T-FILLET"], "located")
    kb = load_kb(kb_dir)
    with pytest.raises(EngineError) as exc:
        lookup(kb, "FX-T-FILLET",
               {"steel_grade": "Q235", "thickness_group": "t<=16"}, {})
    assert "未核对不进计算" in str(exc.value)


def test_downgraded_buckling_table_blocks_a5(tmp_path):
    """φ 表一旦降到未核对档，A5 必须整体 blocked（D11/K14 的机器形态）。"""
    kb_dir = fixture_copy(tmp_path)
    patch_status(kb_dir, "tables", ["FX-T-PHI"], "pending")
    kb = load_kb(kb_dir)
    result = run_case(kb, CARD_A5)
    assert result["conclusion"] == "blocked"
    assert ("table", "FX-T-PHI") in [
        (item["kind"], item["id"]) for item in result["blocked"]]


def test_blocked_result_still_carries_fingerprint_for_attribution(repo_kb):
    result = run_case(repo_kb, CARD_A2)
    assert len(result["meta"]["data_fingerprint"]) == 64
    assert result["meta"]["engine_version"]
