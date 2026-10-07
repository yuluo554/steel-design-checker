"""selfcheck 看板与 CLI 退出码（口径 K9），以及 M4 的推进看板与核对队列（口径 K44）。"""

import json
import os

from sdc import cli
from sdc.selfcheck import build_report, render_text

from _helpers import REPO_DATA_DIR, make_data_dir, pending_records


def test_report_shape(tmp_path):
    report = build_report(make_data_dir(tmp_path))
    assert report["ok"] is True
    assert report["counts"]["clause"] == {
        "total": 1, "verified": 0, "located": 0, "pending": 1, "selfcheck_only": 0,
        "no_status": 0}
    assert len(report["modules"]) == 5
    assert all(m["status"] == "blocked" for m in report["modules"])
    assert report["status_board"]["clause"]["pending"] == ["GB50017-2017:7.6.3"]
    assert report["status_board"]["clause"]["located"] == []
    assert len(report["data_fingerprint"]) == 64


def test_located_status_shows_in_its_own_bucket(tmp_path):
    records = pending_records()
    records["clauses"][0].update({"status": "located", "verified_by": {
        "channel": "建标库", "url": "https://example.invalid/x", "date": "2026-10-06"}})
    report = build_report(make_data_dir(tmp_path, records))
    board = report["status_board"]["clause"]
    assert board["located"] == ["GB50017-2017:7.6.3"] and board["pending"] == []
    assert report["counts"]["clause"]["located"] == 1
    # located 仍然不得进计算：门控必须继续 blocked
    assert all(m["status"] == "blocked" for m in report["modules"])


def test_verified_data_shows_in_traceability(tmp_path):
    records = pending_records()
    records["clauses"][0].update({"status": "verified", "verified_by": {
        "channel": "建标库", "url": "https://example.invalid/x", "date": "2026-10-06"}})
    report = build_report(make_data_dir(tmp_path, records))
    assert report["traceability"] == {"checked_total": 1, "checked_with_channel": 1}


def test_render_text_is_deterministic(tmp_path):
    data_dir = make_data_dir(tmp_path)
    first = render_text(build_report(data_dir))
    assert first == render_text(build_report(data_dir))
    for section in ("[1] 记录计数", "[2] 结构与引用问题", "[3] 模块门控",
                    "[4] 三档看板", "[5] 各 kind 的目录", "[6] 推进看板", "[7] 核对队列"):
        assert section in first


def test_problems_appear_in_report_and_text(tmp_path):
    records = pending_records()
    records["symbols"][0]["status"] = "unknown"
    report = build_report(make_data_dir(tmp_path, records))
    assert report["ok"] is False
    text = render_text(report)
    assert "status" in text and "symbol" in text


def test_cli_ok_exit_zero(tmp_path, capsys):
    code = cli.main(["--data-dir", make_data_dir(tmp_path), "selfcheck"])
    assert code == 0
    assert "sdc selfcheck" in capsys.readouterr().out


def test_cli_problems_exit_one(tmp_path, capsys):
    records = pending_records()
    records["tables"][0]["interpolation"] = "spline"
    code = cli.main(["--data-dir", make_data_dir(tmp_path, records), "selfcheck"])
    assert code == 1


def test_cli_json_output_is_parseable(tmp_path, capsys):
    code = cli.main(["--data-dir", make_data_dir(tmp_path), "selfcheck", "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert "status_board" in payload


def test_cli_missing_data_dir_exit_two(tmp_path, capsys):
    assert cli.main(["--data-dir", os.path.join(str(tmp_path), "nope"),
                     "selfcheck"]) == 2
    assert "数据目录不可用" in capsys.readouterr().err


def test_cli_no_command_exit_two(capsys):
    assert cli.main([]) == 2


# ---------------------------------------------------------------------------
# M4 推进看板与核对队列（口径 K44）
# ---------------------------------------------------------------------------

_VERIFIED_BY = {"channel": "建标库", "url": "https://example.invalid/x",
                "date": "2026-10-06", "note": "测试夹具：模拟已定位"}
_CLAUSE_ID = "GB50017-2017:7.6.3"


def _rule(check_type, assert_spec, rule_status="located"):
    return {
        "id": "R-T-BOARD", "name": "看板用例规则", "check_type": check_type,
        "status": rule_status,
        "basis": [{"clause_id": _CLAUSE_ID, "gist": "测试夹具要点"}],
        "assert": assert_spec,
        "verified_by": dict(_VERIFIED_BY),
    }


def _records(check_type, assert_spec, clause_status="located", rule_status="located"):
    records = pending_records()
    records["clauses"][0]["status"] = clause_status
    records["clauses"][0]["verified_by"] = dict(_VERIFIED_BY)
    records["rules"] = [_rule(check_type, assert_spec, rule_status)]
    return records


def test_repo_progress_counts_and_queue_shape():
    report = build_report(REPO_DATA_DIR)
    progress = report["progress"]
    # M3 定档后（06 D22，±0.001 容差）附录 D 一套已升 verified：条款 5 条 + 表 2 张 + 符号 phi
    assert progress["clause"]["total"] == 161 and progress["clause"]["verified"] == 5
    assert progress["table"]["verified"] == 2 and progress["symbol"]["verified"] == 1
    assert progress["formula"]["verified"] == 0, "F-D.0.5-1 故意留 pending：引擎还不会选分段（D23）"
    assert progress["rule"]["total"] == 10 and progress["checklist"]["total"] == 107
    counts = report["rules"]["counts"]
    assert counts["threshold_unverified"] == 3, "三条带 null 阈值的规则要单独数出来"
    assert counts["active"] == 7 and counts["slot_unsupported"] == 0
    queue = report["verify_queue"]
    assert queue, "全部依据都只 located，队列不可能为空"
    unlocks = [item["unlock_count"] for item in queue]
    assert unlocks == sorted(unlocks, reverse=True), "工单要按解锁数排，先啃解锁多的"
    assert all(item["status"] != "verified" for item in queue)
    checklist = report["checklist"]
    assert checklist["auto_judgeable"] == 9 and checklist["manual_only"] == 98


def test_repo_text_shows_both_new_boards():
    text = render_text(build_report(REPO_DATA_DIR))
    assert "[6] 推进看板" in text and "[7] 核对队列" in text
    assert "阈值 null" in text and "还差核对" in text
    assert "其余" in text, "107 条检查单会把队列撑爆，必须截断并指向 --json"


def test_slot_the_parser_lacks_is_not_reported_as_a_verification_task(tmp_path):
    """解析层还没有 `spacing` 这个槽位：这类"未启用"补多少正式文本都没用，得先补抽取。"""
    report = build_report(make_data_dir(tmp_path, _records(
        "construct", {"kind": "numeric_max", "slot": "spacing", "bound": None})))
    row = report["rules"]["rules"][0]
    assert row["reason"] == "slot_unsupported", row
    assert row["unsupported_slots"] == ["spacing"]
    assert "解析层没有这个槽位" in render_text(report)


def test_null_threshold_becomes_an_actionable_queue_item(tmp_path):
    report = build_report(make_data_dir(tmp_path, _records(
        "construct", {"kind": "numeric_max", "slot": "min_hf", "bound": None})))
    row = report["rules"]["rules"][0]
    assert row["reason"] == "threshold_unverified", row
    assert row["threshold_null"] == ["bound"] and row["blockers"] == [_CLAUSE_ID]
    queue = report["verify_queue"]
    assert queue[0]["clause_id"] == _CLAUSE_ID and queue[0]["rules"] == ["R-T-BOARD"]
    assert "闸门表在该档位不出结论" not in render_text(report)


def test_matrix_silent_rules_are_labelled_as_such(tmp_path):
    """依据 pending 的构造类规则按闸门表不出结论（K31 的反面），要单独说清。"""
    report = build_report(make_data_dir(tmp_path, _records(
        "construct", {"kind": "presence", "slots": ["grade"]},
        clause_status="pending", rule_status="pending")))
    row = report["rules"]["rules"][0]
    assert row["reason"] == "matrix_silent", row
    assert row["effective_status"] == "pending"


def test_queue_empties_once_the_basis_clause_is_verified(tmp_path):
    report = build_report(make_data_dir(
        tmp_path, _records("construct", {"kind": "numeric_max", "slot": "min_hf",
                                         "bound": None}, clause_status="verified")))
    assert report["verify_queue"] == []
    assert "队列为空" in render_text(report)
    # 依据已核对 ≠ 规则已启用：阈值仍是 null（K31），这两件事必须分开说
    assert report["rules"]["rules"][0]["reason"] == "threshold_unverified"


def test_active_rule_is_absent_from_the_disabled_list_but_still_in_the_queue(tmp_path):
    """已启用的规则不进"未启用清单"，但它仍在核对队列里：依据升 verified 才判得出 abnormal。"""
    report = build_report(make_data_dir(
        tmp_path, _records("presence", {"kind": "presence", "slots": ["grade"]})))
    row = report["rules"]["rules"][0]
    assert row["reason"] == "active", row
    text = render_text(report)
    assert "    - R-T-BOARD" not in text, "已启用的规则不该混进未启用清单"
    assert "规则：R-T-BOARD" in text, "核对这条依据能把它从可疑升到异常，队列里要说出来"
