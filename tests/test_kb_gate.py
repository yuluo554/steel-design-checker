"""status 门控：未核对的数据不得进入计算路径（口径 K2、plan/03 §三.2）。"""

from sdc.kb import load_kb, module_gate, module_requirements
from sdc.kb.schema import MODULES

from _helpers import make_data_dir, pending_records, verified_records


def _gate(tmp_path, records, module):
    return module_gate(module, load_kb(make_data_dir(tmp_path, records)))


def test_all_modules_blocked_when_nothing_verified(tmp_path):
    for module in MODULES:
        gate = _gate(tmp_path, pending_records(), module)
        assert gate["status"] == "blocked", module


def test_requirements_are_derived_from_data(tmp_path):
    kb = load_kb(make_data_dir(tmp_path, pending_records()))
    req = module_requirements("fillet_weld", kb)
    assert req["formula"] == ["F-FILLET-POSITIVE"]
    assert req["clause"] == ["GB50017-2017:7.6.3"]
    assert req["symbol"] == ["h_e"]
    assert req["table"] == ["T-fillet-weld-value"]


def test_blocked_lists_every_unready_dependency(tmp_path):
    gate = _gate(tmp_path, pending_records(), "fillet_weld")
    unready = dict((item["kind"], item["id"]) for item in gate["unready"])
    assert set(unready) == {"formula", "clause", "symbol", "table"}
    assert all(item["status"] == "pending" for item in gate["unready"])


def test_module_becomes_ready_when_dependencies_verified(tmp_path):
    gate = _gate(tmp_path, verified_records(), "fillet_weld")
    assert gate["status"] == "ready", gate
    assert gate["unready"] == []


def test_one_pending_dependency_keeps_module_blocked(tmp_path):
    records = verified_records()
    records["tables"][0]["status"] = "pending"
    records["tables"][0]["values"] = []
    gate = _gate(tmp_path, records, "fillet_weld")
    assert gate["status"] == "blocked"
    assert [i["kind"] for i in gate["unready"]] == ["table"]


def test_missing_dependency_reports_missing(tmp_path):
    records = pending_records()
    records["clauses"] = []
    gate = _gate(tmp_path, records, "fillet_weld")
    assert gate["status"] == "blocked"
    missing = [i for i in gate["unready"] if i["status"] == "missing"]
    assert [i["id"] for i in missing] == ["GB50017-2017:7.6.3"]


def test_module_without_formula_is_blocked(tmp_path):
    gate = _gate(tmp_path, pending_records(), "butt_weld")
    assert gate["status"] == "blocked"
    assert "尚无已入库公式" in gate["reason"]


def test_blocked_gate_carries_no_numbers(tmp_path):
    """blocked 只给待核对清单，绝不给出比值/应力（K2：引用 pending 不出数值）。"""
    gate = _gate(tmp_path, pending_records(), "fillet_weld")
    assert "ratio" not in gate and "value" not in gate
    text = repr(gate["reason"]) + repr(gate["unready"])
    assert "MPa" not in text
