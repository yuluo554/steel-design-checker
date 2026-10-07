"""`sdc bench`：分母只含 verified、容差逐算例登记、blocked 不得静默通过（K3/K6/D07）。"""

import json
import os

import pytest

from _helpers import FIXTURE_KB_DIR, REPO_DATA_DIR, fixture_copy, patch_status
from sdc import bench
from sdc.kb import load_kb


def _write_cases(data_dir, records):
    path = os.path.join(data_dir, "cases", "fix.json")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(records, ensure_ascii=False, indent=2, sort_keys=True))
    return path


def _read_cases(data_dir):
    with open(os.path.join(data_dir, "cases", "fix.json"), encoding="utf-8") as handle:
        return json.loads(handle.read())


def test_fixture_bench_denominator_and_full_pass():
    kb = load_kb(FIXTURE_KB_DIR)
    report = bench.build_report(kb)
    assert report["cases"]["denominator"] == 7, "分母只数 verified 算例"
    assert report["cases"]["passed"] == 7
    assert report["cases"]["pass_rate"] == 1.0
    assert "FX-CASE-PENDING-001" in report["cases"]["pending_case_ids"]
    assert report["ok"] is True
    for row in report["cases"]["rows"]:
        assert row["status"] == "pass", row


def test_tampered_expectation_is_a_fail_not_a_skip(tmp_path):
    kb_dir = fixture_copy(tmp_path)
    records = _read_cases(kb_dir)
    for rec in records:
        if rec["case_id"] == "FX-CASE-A2-OK":
            rec["expected"]["ratio"] = 0.8
    _write_cases(kb_dir, records)
    report = bench.build_report(load_kb(kb_dir))
    assert report["cases"]["passed"] == 6
    assert report["ok"] is False
    failed = [row for row in report["cases"]["rows"] if row["status"] == "fail"]
    assert len(failed) == 1
    assert "ratio 期望 0.8" in failed[0]["details"][0]


def test_verified_case_without_tolerance_is_a_fail(tmp_path):
    """没有逐条登记的容差就不能对账（K3），宁可判失败也不给默认容差。"""
    kb_dir = fixture_copy(tmp_path)
    records = _read_cases(kb_dir)
    for rec in records:
        if rec["case_id"] == "FX-CASE-A5-OK":
            rec.pop("tolerance")
    _write_cases(kb_dir, records)
    kb = load_kb(kb_dir)
    assert kb.problems, "schema 层也应拦住 verified 且无 tolerance 的算例"
    assert any(p["field"] == "tolerance" for p in kb.problems)

    report = bench.build_report(load_kb(kb_dir))
    row = [r for r in report["cases"]["rows"] if r["case_id"] == "FX-CASE-A5-OK"][0]
    assert row["status"] == "fail"
    assert "未登记容差" in row["details"][0]


def test_blocked_cases_are_skipped_explicitly_not_counted_pass(tmp_path):
    kb_dir = fixture_copy(tmp_path)
    patch_status(kb_dir, "tables", ["FX-T-FILLET"], "located")
    report = bench.build_report(load_kb(kb_dir))
    rows = dict((row["case_id"], row) for row in report["cases"]["rows"])
    assert rows["FX-CASE-A2-OK"]["status"] == "blocked_skip"
    assert "不静默通过" in rows["FX-CASE-A2-OK"]["details"][0]
    assert report["cases"]["denominator"] == 7, "分母不因为 blocked 而缩水"
    assert report["cases"]["passed"] == 4
    assert report["ok"] is False


def test_repo_data_bench_declares_zero_denominator(repo_report):
    text = bench.render_text(repo_report)
    assert "分母 0，样本待补" in text
    assert repo_report["ok"] is False
    assert repo_report["cases"]["denominator"] == 0


def test_repo_selfcheck_samples_pass_their_machine_assertions(repo_report):
    rows = repo_report["selfcheck_samples"]
    assert len(rows) == 9
    for row in rows:
        assert row["status"] == "ok", row
    scope = [row for row in rows if row["case_id"] == "SC-A4-SCOPE-001"][0]
    assert "承压型" in scope["details"][0], "范围纪律必须由输入层拒绝"


def test_selfcheck_section_can_be_skipped_with_cases_flag(repo_report):
    kb = load_kb(REPO_DATA_DIR)
    only = bench.build_report(kb, only_cases=True)
    assert only["selfcheck_samples"] == []
    assert only["cases"]["denominator"] == 0


@pytest.fixture(scope="module")
def repo_report():
    return bench.build_report(load_kb(REPO_DATA_DIR))
