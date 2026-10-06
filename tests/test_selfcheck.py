"""selfcheck 看板与 CLI 退出码（口径 K9）。"""

import json
import os

from sdc import cli
from sdc.selfcheck import build_report, render_text

from _helpers import make_data_dir, pending_records


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
                    "[4] 三档看板", "[5] 各 kind 的目录"):
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
