"""`sdc run` / `sdc bench` 的 CLI 契约：退出码 0 完成 / 1 降级（blocked）/ 2 输入不可用（K9）。"""

import json
import os
import sys

import pytest

from _helpers import CARD_A2, CARD_A5, FIXTURE_KB_DIR, REPO_DATA_DIR
from sdc.cli import main

DEMO_A2 = os.path.join(REPO_DATA_DIR, "examples", "A2-fillet-weld.json")


def _card_file(tmp_path, card, name="card.json"):
    path = os.path.join(str(tmp_path), name)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(card, ensure_ascii=False, indent=2, sort_keys=True))
    return path


def _run(tmp_path, capsys, card, data_dir=FIXTURE_KB_DIR, extra=()):
    path = _card_file(tmp_path, card)
    argv = ["--data-dir", data_dir, "run", "--json", "--case", path] + list(extra)
    code = main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_run_on_repo_data_is_blocked_with_exit_code_1(capsys):
    code = main(["--data-dir", REPO_DATA_DIR, "run", "--json", "--case", DEMO_A2])
    captured = capsys.readouterr()
    assert code == 1
    result = json.loads(captured.out)
    assert result["conclusion"] == "blocked"
    assert result["ratio"] is None
    assert result["steps"] == []
    assert result["blocked"], "拒算必须逐项列出缺什么"


def test_run_text_output_carries_basis_and_disclaimer(capsys):
    code = main(["--data-dir", REPO_DATA_DIR, "run", "--case", DEMO_A2])
    text = capsys.readouterr().out
    assert code == 1
    assert "拒算依据" in text
    assert "status=located" in text
    assert "免责声明" in text


def test_run_on_verified_fixture_produces_numbers_with_exit_code_0(tmp_path, capsys):
    code, out, _err = _run(tmp_path, capsys, CARD_A2)
    assert code == 0
    result = json.loads(out)
    assert result["conclusion"] == "satisfied"
    assert result["ratio"] == pytest.approx(0.7142857142857143, abs=1e-9)
    assert result["steps"]


def test_run_is_deterministic(tmp_path, capsys):
    """同一份卡连跑两次，输出必须逐字节一致（口径 K8）。"""
    path = _card_file(tmp_path, CARD_A2)
    argv = ["--data-dir", FIXTURE_KB_DIR, "run", "--json", "--case", path]
    first = main(list(argv))
    out_first = capsys.readouterr().out
    second = main(list(argv))
    out_second = capsys.readouterr().out
    assert first == second == 0
    assert out_first == out_second


def test_module_flag_must_agree_with_card(tmp_path, capsys):
    path = _card_file(tmp_path, CARD_A2)
    code = main(["--data-dir", FIXTURE_KB_DIR, "run", "--module", "butt_weld",
                 "--case", path])
    assert code == 2
    assert "不一致" in capsys.readouterr().err


def test_missing_case_file_is_exit_2(capsys):
    code = main(["--data-dir", FIXTURE_KB_DIR, "run", "--case",
                 os.path.join("nope", "missing.json")])
    assert code == 2
    assert "读取失败" in capsys.readouterr().err


def test_malformed_json_is_exit_2(tmp_path, capsys):
    path = os.path.join(str(tmp_path), "bad.json")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("{not json")
    assert main(["--data-dir", FIXTURE_KB_DIR, "run", "--case", path]) == 2
    assert "不是合法 JSON" in capsys.readouterr().err


def test_illegal_card_is_exit_2(tmp_path, capsys):
    broken = dict(CARD_A2, steel_grade="Q999")
    code, _out, err = _run(tmp_path, capsys, broken)
    assert code == 2
    assert "输入词表" in err


def test_data_self_inconsistency_is_degraded_not_silent(tmp_path, capsys):
    """λ 超出 φ 表界：引擎不许外推，走「降级完成」并说清原因。"""
    broken = dict(CARD_A5, i_y=2.0)
    code, _out, err = _run(tmp_path, capsys, broken)
    assert code == 1
    assert "禁止外推" in err
    assert "免责声明" in err


def test_bench_cli_exit_codes(capsys):
    assert main(["--data-dir", REPO_DATA_DIR, "bench", "--cases"]) == 1
    assert "分母 0，样本待补" in capsys.readouterr().out
    assert main(["--data-dir", FIXTURE_KB_DIR, "bench", "--cases"]) == 0


def test_bench_json_is_sorted_and_timestamp_free(capsys):
    assert main(["--data-dir", REPO_DATA_DIR, "bench", "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    text = json.dumps(report, sort_keys=True)
    assert text == json.dumps(report, sort_keys=True)
    assert "2026-10-07" not in text
    assert report["ok"] is False


def test_unknown_data_dir_is_exit_2(capsys, tmp_path):
    code = main(["--data-dir", os.path.join(str(tmp_path), "empty"), "bench"])
    assert code == 2
    assert "数据目录不可用" in capsys.readouterr().err


def test_error_channel_uses_the_same_encoding_as_stdout(monkeypatch):
    """stdout 与 stderr 必须落成同一套 UTF-8 字节（口径 K47）。

    干净环境验证实测：冻结 exe 的 stderr 默认跟随系统代码页（本机 GBK），于是同一句
    拒算说明在 `python -X utf8 -m sdc` 与 `sdc-cli.exe` 里是两种字节。这里用一对
    GBK 流当诱饵：`_err` 若没把 stderr 钉成 UTF-8，解码出来就是乱码。
    """
    import io

    out, err = io.BytesIO(), io.BytesIO()
    monkeypatch.setattr("sys.stdout", io.TextIOWrapper(out, encoding="gbk", errors="replace"))
    monkeypatch.setattr("sys.stderr", io.TextIOWrapper(err, encoding="gbk", errors="replace"))
    assert main(["--data-dir", REPO_DATA_DIR, "run", "--case",
                 os.path.join("nope", "missing.json")]) == 2
    sys_stream = sys.stderr
    sys_stream.flush()
    text = err.getvalue().decode("utf-8")
    assert "参数卡读取失败" in text
    assert "免责声明" not in text          # 输入不可用（2）不该混进计算未完成的说法
    assert out.getvalue() == b""
