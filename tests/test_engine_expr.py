"""式体求值器：白名单结构与比值方向的守门测试。"""

import pytest

from sdc.engine.errors import ExprError
from sdc.engine.expr import build_plan, evaluate, parse_expression


def test_derivation_plan_shape():
    plan = build_plan("h_e = 0.7*h_f", "F-TEST")
    assert plan.kind == "derivation"
    assert plan.target == "h_e"
    assert plan.names == ["h_f"]


def test_check_ratio_is_demand_over_capacity():
    plan = build_plan("N/(h_e*l_w) <= beta_f*f_f_w", "F-TEST")
    assert plan.kind == "check"
    assert plan.op == "<="
    env = {"N": 100000.0, "h_e": 7.0, "l_w": 200.0, "beta_f": 1.2, "f_f_w": 100.0}
    demand = evaluate(plan.left, env)
    capacity = evaluate(plan.right, env)
    assert demand == pytest.approx(71.42857142857143, abs=1e-9)
    assert capacity == pytest.approx(120.0, abs=1e-9)


def test_reversed_comparison_still_demand_over_capacity():
    """>= 形式（抗力在左）也必须翻成「作用/抗力」，否则应力比方向就反了。"""
    plan = build_plan("k*n_f*mu*P >= N_v_bolt", "F-TEST")
    env = {"k": 1.0, "n_f": 2.0, "mu": 0.4, "P": 60000.0, "N_v_bolt": 20000.0}
    # plan.left 恒为作用效应端，plan.right 恒为抗力端
    assert evaluate(plan.left, env) == pytest.approx(20000.0, abs=1e-9)
    assert evaluate(plan.right, env) == pytest.approx(48000.0, abs=1e-6)
    assert plan.names == ["N_v_bolt", "P", "k", "mu", "n_f"]


def test_bound_expression_entry_point():
    node, names = parse_expression("1.5*sqrt(t_min)", "FX:limits")
    assert names == ["t_min"]
    assert evaluate(node, {"t_min": 40.0}) == pytest.approx(9.486832980505138, abs=1e-12)
    with pytest.raises(ExprError):
        parse_expression("h_f >= 1.5*sqrt(t_min)", "FX:limits")


def test_functions_and_constants_allowed():
    plan = build_plan("lambda = max(l_0x/i_x, l_0y/i_y)", "F-TEST")
    env = {"l_0x": 1000.0, "i_x": 50.0, "l_0y": 800.0, "i_y": 40.0}
    assert evaluate(plan.left, env) == pytest.approx(20.0, abs=1e-12)

    area = build_plan("A_s = pi*d*d/4", "F-TEST")
    assert evaluate(area.left, {"d": 20.0}) == pytest.approx(314.1592653589793, abs=1e-9)


@pytest.mark.parametrize("expr,reason", [
    ("N <= f; import os", "不允许写语句"),
    ("x <= y <= z", "链式比较必须拆成多条公式"),
    ("x < y", "严格不等没有容差语义"),
    ("x == y", "等式不是验算式"),
    ("h_e = 0.7*h_f = 1", "派生式左端不合法"),
    ("= 0.7*h_f", "派生式两端不完整"),
    ("lambda n <= 0.215", "必须落在机器可解析形式内"),
])
def test_rejected_structures(expr, reason):
    with pytest.raises(ExprError):
        build_plan(expr, "F-TEST")


@pytest.mark.parametrize("expr", [
    "__import__('os').system('x') <= 1",
    "N.__class__ <= 1",
    "a[0] <= b",
    "N <= (f for f in [])",
])
def test_rejected_leaves_at_evaluation(expr):
    """这些在语法上能长成比较式，但求值时必须被白名单拦下（两端都过一遍）。"""
    plan = build_plan(expr, "F-TEST")
    env = {"N": 1.0, "a": 2.0, "f": 3.0, "x": 4.0, "y": 5.0}
    with pytest.raises(ExprError):
        evaluate(plan.left, env)
        evaluate(plan.right, env)


def test_rejected_structures_at_evaluation():
    plan = build_plan("N <= f", "F-TEST")
    with pytest.raises(ExprError):
        evaluate(plan.left, {"f": 2.0})  # N 没有值：报错而不是按 0 算
    plan = build_plan("V/A_w <= f_v_w", "F-TEST")
    with pytest.raises(ExprError):
        evaluate(plan.left, {"V": 1.0, "A_w": 0.0, "f_v_w": 1.0})
    with pytest.raises(ExprError):
        evaluate(build_plan("10**1000 <= f", "F-TEST").left, {"f": 1.0})
    with pytest.raises(ExprError):
        evaluate(build_plan("True <= f", "F-TEST").left, {"f": 1.0})


def test_empty_expr_is_refused_not_defaulted():
    for bad in ("", "   ", None, 1.0, ["N <= f"]):
        with pytest.raises(ExprError):
            build_plan(bad, "F-TEST")
