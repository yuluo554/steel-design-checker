"""5 个验算模块的四件套（正例 / 反例 / 边界 / 非法输入）+ 计算过程可追溯性。

数值通路只能在**合成 verified 夹具**（tests/fixtures/kb/，数值全部虚构）上测；
仓内真实数据全 located ⇒ 一律 blocked。两条路同一个引擎、同一套门控。
"""

import copy
import json

import pytest

from _helpers import (BASE_CARDS, CARD_A2, CARD_A5, FIXTURE_KB_DIR, RATIO_A5, scaled)
from sdc.engine.core import NEED_ADJUST_FLOOR, RATIO_TOL, run_case
from sdc.engine.errors import EngineError, InputError
from sdc.kb import load_kb


@pytest.fixture(scope="module")
def kb():
    handle = load_kb(FIXTURE_KB_DIR)
    assert handle.problems == [], "夹具知识库没过 schema：%s" % handle.problems
    return handle


@pytest.mark.parametrize("module", sorted(BASE_CARDS))
def test_positive_case_conclusion_and_ratio(kb, module):
    card, expected = BASE_CARDS[module]
    result = run_case(kb, card)
    assert result["conclusion"] == "satisfied"
    assert result["ratio"] == pytest.approx(expected, abs=1e-9)
    assert result["blocked"] == []
    assert result["steps"], "出数值就必须给逐步过程"


@pytest.mark.parametrize("module", sorted(BASE_CARDS))
def test_over_limit_case(kb, module):
    card, expected = BASE_CARDS[module]
    result = run_case(kb, scaled(card, 1.5 / expected))
    assert result["ratio"] == pytest.approx(1.5, abs=1e-9)
    assert result["conclusion"] == "unsatisfied"


@pytest.mark.parametrize("module", sorted(BASE_CARDS))
def test_boundary_case_is_need_adjust_not_satisfied(kb, module):
    """> 0.95 且 ≤ 1.0 判需调整（口径 K2），不是「满足」。"""
    card, expected = BASE_CARDS[module]
    result = run_case(kb, scaled(card, 0.97 / expected))
    assert result["ratio"] == pytest.approx(0.97, abs=1e-9)
    assert result["conclusion"] == "need_adjust"


def test_conclusion_band_edges(kb):
    """把容差与档位边界钉死：1.0 本身归 need_adjust，1.0+1e-3 以内仍算不超限。"""
    assert NEED_ADJUST_FLOOR == 0.95
    assert RATIO_TOL == 1e-3
    card, expected = BASE_CARDS["fillet_weld"]
    at_one = run_case(kb, scaled(card, 1.0 / expected))
    assert at_one["ratio"] == pytest.approx(1.0, abs=1e-9)
    assert at_one["conclusion"] == "need_adjust"
    just_over = run_case(kb, scaled(card, (1.0 + 5e-4) / expected))
    assert just_over["conclusion"] == "need_adjust", "K3 容差内不得判不符合"
    clearly_over = run_case(kb, scaled(card, (1.0 + 5e-3) / expected))
    assert clearly_over["conclusion"] == "unsatisfied"


@pytest.mark.parametrize("module", sorted(BASE_CARDS))
def test_illegal_inputs_are_rejected_not_silently_zeroed(kb, module):
    card = BASE_CARDS[module][0]
    mutations = [
        ("缺少必填槽位", _drop_one_required(card, module)),
        ("未定义槽位", _with_slot(card, "nonsense_slot", 1.0)),
        ("数据侧量不得由输入提供", _with_slot(card, "beta_f", 1.22)),
        ("枚举越界", _with_slot(card, "steel_grade", "Q999")),
        ("负值", _with_force(card, "N", -1000.0)),
        ("未知单位", _with_slot(card, "units", {"force": "吨", "length": "mm"})),
        ("字符串冒充数值", _with_slot(card, "case_id", "   ")),
    ]
    for label, broken in mutations:
        with pytest.raises(InputError):
            run_case(kb, broken)  # label 只作可读性用途，失败时由参数化 id 定位


def test_zero_force_is_allowed_and_gives_zero_ratio(kb):
    result = run_case(kb, _with_force(CARD_A2, "N", 0.0))
    assert result["ratio"] == 0.0
    assert result["conclusion"] == "satisfied"


def test_missing_force_component_fails_loudly_instead_of_defaulting(kb):
    """卡里不给 N：符号不闭合必须报错，不能悄悄按 0 算。"""
    card = copy.deepcopy(CARD_A2)
    card["forces"] = {"V": 1000.0}
    with pytest.raises(EngineError):
        run_case(kb, card)


@pytest.mark.parametrize("module", sorted(BASE_CARDS))
def test_unit_invariance_only_at_entry_layer(kb, module):
    """同一物理荷载换成 kN 表达，ratio 必须完全相同（口径 K1）。"""
    card, _ = BASE_CARDS[module]
    base = run_case(kb, card)
    variant = copy.deepcopy(card)
    forces = variant["forces"]
    for name in sorted(forces):
        forces[name] = forces[name] / 1000.0
    variant["units"] = dict(variant["units"], force="kN")
    assert run_case(kb, variant)["ratio"] == base["ratio"]


def test_derived_steps_come_from_data_not_hardcoded(kb):
    """h_e 与 β_f 都得是数据交出来的：步骤里能追到公式 id 与查表代入值。"""
    result = run_case(kb, CARD_A2)
    by_formula = dict((step["formula_id"], step) for step in result["steps"])
    assert by_formula["F-FX-A2-HE"]["value"] == pytest.approx(7.0, abs=1e-12)
    assert by_formula["F-FX-A2-HE"]["clause_id"] == "FX-C-A2"
    assert by_formula["F-FX-A2-HE"]["unit"] == "mm"
    assert by_formula["F-FX-A2-HE"]["symbol_zh"]
    side = by_formula["F-FX-A2-SIDE"]
    assert side["substituted"]["f_f_w"] == 100.0
    assert side["substituted"]["l_w_total"] == 200.0
    front = by_formula["F-FX-A2-FRONT"]
    assert front["substituted"]["beta_f"] == 1.2, "β_f 必须来自夹具表而非代码"
    assert sorted(by_formula) == sorted(step["formula_id"] for step in result["steps"])


def test_governing_ratio_is_the_worst_check(kb):
    """多条验算式取最大比值，且每条都留在 steps 里。"""
    result = run_case(kb, CARD_A5)
    check_steps = [s for s in result["steps"] if s["output"] == "ratio"]
    assert len(check_steps) == 1
    assert result["ratio"] == pytest.approx(RATIO_A5, abs=1e-9)

    result = run_case(kb, BASE_CARDS["bolt_normal"][0])
    check_steps = [s for s in result["steps"] if s["output"] == "ratio"]
    assert len(check_steps) == 2, "受剪与承压两条都要留痕"
    assert result["ratio"] == max(step["value"] for step in check_steps)


def test_construct_limit_can_flip_conclusion_to_unsatisfied(kb):
    """比值满足但构造限值不过：结论必须不满足（plan/04 §一 的判定顺序）。"""
    card = copy.deepcopy(CARD_A2)
    card["h_f"] = 6.0
    card["t_min"] = 40.0
    card["forces"] = {"N": 70000.0}
    result = run_case(kb, card)
    assert result["ratio"] == pytest.approx(0.8333333333333334, abs=1e-9)
    assert result["limits"][0]["param"] == "h_f"
    assert result["limits"][0]["ok"] is False
    assert result["conclusion"] == "unsatisfied"


def test_mandatory_clause_warning_is_data_driven(kb):
    """强条联动提示只由数据侧 mandatory 标记产生，代码里没有 7 条硬编码清单。"""
    result = run_case(kb, BASE_CARDS["butt_weld"][0])
    assert [w["clause_id"] for w in result["warnings"]] == ["FX-C-A1"]
    assert result["warnings"][0]["type"] == "mandatory_clause"
    basis = dict((b["clause_id"], b) for b in result["basis"])
    assert basis["FX-C-A1"]["mandatory"] is True


def test_buckling_axis_selection_is_order_independent(kb):
    """λ 取两轴较大者，交换输入顺序结果必须一致（口径 K8）。"""
    swapped = copy.deepcopy(CARD_A5)
    swapped["l_0x"], swapped["l_0y"] = CARD_A5["l_0y"], CARD_A5["l_0x"]
    swapped["i_x"], swapped["i_y"] = CARD_A5["i_y"], CARD_A5["i_x"]
    assert run_case(kb, swapped)["ratio"] == run_case(kb, CARD_A5)["ratio"]

    governing_y = copy.deepcopy(CARD_A5)
    governing_y["i_y"] = 20.0
    result = run_case(kb, governing_y)
    assert result["ratio"] > run_case(kb, CARD_A5)["ratio"], "应取较大 λ，即更小 φ"


def test_phi_table_refuses_extrapolation(kb):
    """λ 超表界必须失败，不外推（插值口径得与原文一致，plan/04 A5 易错点）。"""
    card = copy.deepcopy(CARD_A5)
    card["i_y"] = 10.0  # λ = max(20, 80) = 80 仍在界内
    assert run_case(kb, card)["ratio"] > run_case(kb, CARD_A5)["ratio"]
    card["i_y"] = 2.0  # λ = 400 超出夹具表 0~200
    with pytest.raises(EngineError) as exc:
        run_case(kb, card)
    assert "禁止外推" in str(exc.value)


def test_phi_interpolation_is_linear(kb):
    """λ=30 落在 20(0.97) 与 40(0.92) 中间 → 0.945，显式线性插值。"""
    card = copy.deepcopy(CARD_A5)
    card["l_0x"] = 1500.0  # λx = 30 > λy = 20
    card["forces"] = {"N": 94500.0}
    result = run_case(kb, card)
    step = [s for s in result["steps"] if s["formula_id"] == "F-FX-A5-CHECK"][0]
    assert step["substituted"]["phi"] == pytest.approx(0.945, abs=1e-12)
    assert result["ratio"] == pytest.approx(0.5, abs=1e-9)


def test_result_is_deterministic_and_json_stable(kb):
    first = run_case(kb, CARD_A2)
    second = run_case(kb, CARD_A2)
    assert json.dumps(first, sort_keys=True, ensure_ascii=False) == \
        json.dumps(second, sort_keys=True, ensure_ascii=False)


def test_basis_lists_all_verified_clauses_once(kb):
    result = run_case(kb, BASE_CARDS["bolt_hsb_friction"][0])
    clause_ids = [b["clause_id"] for b in result["basis"]]
    assert clause_ids == sorted(set(clause_ids))
    assert "FX-C-A4" in clause_ids
    assert all(b["status"] == "verified" for b in result["basis"])


def _drop_one_required(card, module):
    from sdc.engine.params import MODULE_SLOTS

    broken = copy.deepcopy(card)
    for name in MODULE_SLOTS[module]["required"]:
        if name in broken:
            broken.pop(name)
            break
    return broken


def _with_slot(card, name, value):
    broken = copy.deepcopy(card)
    broken[name] = value
    return broken


def _with_force(card, name, value):
    broken = copy.deepcopy(card)
    broken["forces"] = dict(card["forces"], **{name: value})
    return broken
