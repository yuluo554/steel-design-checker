"""M4 报告导出的四条硬断言：0 外链、两次导出字节一致、免责声明必存、无真实个人信息。

外加两条"这套断言本身有效"的反证：正文里塞 URL、往 `.rels` 里塞外部目标，扫描必须报出来
——永不触发的守门测试等于没有守门。

口径：K40（0 外链的机器定义）、K41（报告与终端渲染同源）、K42（不写绝对路径与渠道 URL）。
"""

import io
import json
import os
import subprocess
import zipfile

import pytest

from _helpers import FIXTURE_KB_DIR, REPO_DATA_DIR
from sdc import checklist as checklist_module
from sdc import cli
from sdc.engine.core import DISCLAIMER, run_case
from sdc.kb.loader import load_kb
from sdc.parse.textio import read_document
from sdc.report import (REPORT_APP_NAME, REPORT_PLACEHOLDER, ReportError,
                        check_body, checklist_body, docx_bytes, export_docx,
                        find_external_refs, find_personal_info, metadata_values,
                        result_body)
from sdc.rules import run_rules
from sdc.synth.docx import build_docx

DOCX_DIR = os.path.join(REPO_DATA_DIR, "synth", "docx")
SRC_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), os.pardir, "src"))


@pytest.fixture(scope="module")
def kb():
    return load_kb(REPO_DATA_DIR)


@pytest.fixture(scope="module")
def ir_path(tmp_path_factory):
    path = os.path.join(str(tmp_path_factory.mktemp("ir")), "SYNTH-0013.ir.json")
    assert cli.main(["--data-dir", REPO_DATA_DIR, "parse", "--doc",
                     os.path.join(DOCX_DIR, "SYNTH-0013.docx"), "--out", path]) == 0
    return path


@pytest.fixture(scope="module")
def bodies(kb, ir_path):
    from sdc.parse.ir import load_ir
    ir = load_ir(ir_path)
    with open(os.path.join(REPO_DATA_DIR, "examples", "A2-fillet-weld.json"),
              "r", encoding="utf-8") as handle:
        card = json.loads(handle.read())
    return {
        "验算书": result_body(run_case(kb, card), "data/examples/A2-fillet-weld.json"),
        "核查清单": check_body(run_rules(kb, ir)),
        "检查单": checklist_body(checklist_module.build_report(kb, ir), ir_path),
    }


def _markers():
    """本机真实身份样本：用户名、home 路径、git 署名。空串与短串不参与比对（见 find_personal_info）。"""
    out = [os.environ.get("USERNAME") or "", os.environ.get("USER") or "",
           os.path.expanduser("~"), os.path.expandvars("%USERPROFILE%")]
    try:
        result = subprocess.run(["git", "config", "user.name"], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=10)
        out.append(result.stdout.decode("utf-8", "replace").strip())
    except OSError:
        pass
    return [m for m in out if m]


# ---------------------------------------------------------------------------
# 四条硬断言
# ---------------------------------------------------------------------------

def test_every_export_is_byte_identical_twice(bodies, tmp_path):
    for name, body in bodies.items():
        first = export_docx(body, os.path.join(str(tmp_path), "%s-a.docx" % name))
        second = export_docx(body, os.path.join(str(tmp_path), "%s-b.docx" % name))
        with open(first, "rb") as a, open(second, "rb") as b:
            assert a.read() == b.read(), "%s 两次导出不一致" % name
        assert docx_bytes(body) == docx_bytes(body)


def test_exports_have_zero_external_references(bodies):
    for name, body in bodies.items():
        violations = find_external_refs(docx_bytes(body))
        assert violations == [], "%s 有外链嫌疑：%s" % (name, violations)


def test_synth_corpus_also_passes_the_zero_link_scan():
    """同一把尺子量合成语料：0 外链口径不是为报告特制的，交付物与 fixtures 一起守。"""
    for name in sorted(os.listdir(DOCX_DIR)):
        if not name.endswith(".docx"):
            continue
        with open(os.path.join(DOCX_DIR, name), "rb") as handle:
            payload = handle.read()
        assert find_external_refs(payload) == [], name


def test_disclaimer_is_present_in_every_export(bodies):
    for name, body in bodies.items():
        text = "\n".join(body)
        assert DISCLAIMER in text, "%s 缺免责声明" % name


def test_disclaimer_has_exactly_one_definition_in_src():
    """口径 K23：免责声明文案单源于 engine/core.DISCLAIMER，散落副本早晚会各说一句话。"""
    offenders = []
    for root, dirs, files in os.walk(SRC_DIR):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            with open(path, "r", encoding="utf-8") as handle:
                if DISCLAIMER in handle.read():
                    offenders.append(os.path.relpath(path, SRC_DIR))
    assert offenders == [os.path.join("sdc", "engine", "core.py")], offenders


def test_exports_carry_no_real_identity(bodies):
    markers = _markers()
    assert markers, "取不到本机身份样本，这条断言就没被执行过"
    for name, body in bodies.items():
        payload = docx_bytes(body)
        assert find_personal_info(payload, markers) == [], name
        values = metadata_values(payload)
        assert values["creator"] == REPORT_PLACEHOLDER
        assert values["lastModifiedBy"] == REPORT_PLACEHOLDER
        assert values["Application"] == REPORT_APP_NAME


# ---------------------------------------------------------------------------
# 反证：守门扫描不是空转
# ---------------------------------------------------------------------------

def test_scan_flags_url_and_absolute_path_in_visible_text():
    payload = docx_bytes(["见 https://mirror.example.com/book/198 抄来的表",
                          r"来源 C:\Users\someone\Desktop\规范.pdf"])
    violations = "；".join(find_external_refs(payload))
    assert "外部地址" in violations, violations
    assert "绝对路径" in violations, violations


def test_scan_flags_external_relationship_target():
    payload = docx_bytes(["正文干净"])
    buffer = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(payload)) as source:
        names = source.namelist()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as sink:
            for name in names:
                raw = source.read(name)
                if name == "_rels/.rels":
                    raw = raw.replace(
                        b'<Relationship Id="rId1"',
                        b'<Relationship Id="rId9" TargetMode="External" '
                        b'Target="https://evil.example/x" Type="x" />'
                        b'<Relationship Id="rId1"')
                sink.writestr(zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0)), raw)
    violations = "；".join(find_external_refs(buffer.getvalue()))
    assert "外部" in violations or "外部地址" in violations, violations


def test_namespace_and_relationship_type_uris_are_not_links():
    """命名空间声明与关系类型标识符都是 `http://` 开头，但它们不是对外引用。"""
    payload = build_docx(["只有一行正文"])
    assert b"http://schemas.openxmlformats.org" in payload
    assert find_external_refs(payload) == []


def test_export_refuses_to_write_a_report_without_disclaimer(tmp_path):
    path = os.path.join(str(tmp_path), "bad.docx")
    with pytest.raises(ReportError) as excinfo:
        export_docx(["没有免责声明的正文"], path)
    assert "免责声明" in str(excinfo.value)
    assert not os.path.exists(path), "自检未通过却落了盘，等于把事故写成交付物"


# ---------------------------------------------------------------------------
# 内容契约：报告与终端同源；blocked 不出数值
# ---------------------------------------------------------------------------

def test_docx_body_contains_every_terminal_line(kb, ir_path):
    from sdc.engine.render import render_result
    from sdc.parse.ir import load_ir
    from sdc.rules.render import render_report

    with open(os.path.join(REPO_DATA_DIR, "examples", "A5-column-buckling.json"),
              "r", encoding="utf-8") as handle:
        card = json.loads(handle.read())
    result = run_case(kb, card)
    body = "\n".join(result_body(result, "data/examples/A5-column-buckling.json"))
    for line in render_result(result).split("\n"):
        assert line in body

    check_text = render_report(run_rules(kb, load_ir(ir_path)))
    check_body_text = "\n".join(check_body(run_rules(kb, load_ir(ir_path))))
    for line in check_text.split("\n"):
        assert line in check_body_text


def test_blocked_report_contains_no_numbers_in_the_ratio_line(kb):
    """真实数据一律 blocked：验算书里既没有比值数值，也要把缺哪条核对说全。"""
    with open(os.path.join(REPO_DATA_DIR, "examples", "A2-fillet-weld.json"),
              "r", encoding="utf-8") as handle:
        card = json.loads(handle.read())
    result = run_case(kb, card)
    assert result["conclusion"] == "blocked" and result["ratio"] is None
    body = "\n".join(result_body(result, "data/examples/A2-fillet-weld.json"))
    assert "不出数值（blocked）" in body
    assert "拒算依据" in body and "status=located" in body
    assert DISCLAIMER in body
    # K25 的报告侧延伸：真实数据通路的交付物里不得出现夹具痕迹（渠道、id 都不行）
    assert "FX-" not in body and "合成夹具" not in body


def test_verified_fixture_report_shows_steps():
    fixture_kb = load_kb(FIXTURE_KB_DIR)
    with open(os.path.join(REPO_DATA_DIR, "examples", "A2-fillet-weld.json"),
              "r", encoding="utf-8") as handle:
        card = json.loads(handle.read())
    result = run_case(fixture_kb, card)
    assert result["conclusion"] != "blocked", result
    assert result["steps"], "夹具上的 verified 通路必须真的出逐步计算"
    body = "\n".join(result_body(result, "data/examples/A2-fillet-weld.json"))
    assert "[计算过程]" in body and "h_e" in body
    assert "免责声明" in body


def test_exported_docx_is_readable_by_our_own_parser(bodies, tmp_path):
    for name, body in bodies.items():
        path = export_docx(body, os.path.join(str(tmp_path), "%s.docx" % name))
        document = read_document(path)
        assert document["paragraph_count"] == len(body)
        assert document["paragraphs"][0]["text"] == body[0]


# ---------------------------------------------------------------------------
# 命令面
# ---------------------------------------------------------------------------

def test_report_cli_writes_docx_and_keeps_blocked_exit_code(tmp_path, capsys):
    out = os.path.join(str(tmp_path), "验算书.docx")
    capsys.readouterr()
    code = cli.main(["--data-dir", REPO_DATA_DIR, "report", "--module", "fillet_weld",
                     "--case", os.path.join(REPO_DATA_DIR, "examples", "A2-fillet-weld.json"),
                     "--out", out])
    printed = capsys.readouterr().out
    assert code == 1, "blocked 的验算书照样导出，但退出码仍是降级完成（1）"
    assert "验算书已导出" in printed and os.path.exists(out)


def test_report_cli_on_verified_fixture_exits_zero(tmp_path, capsys):
    out = os.path.join(str(tmp_path), "验算书-夹具.docx")
    capsys.readouterr()
    code = cli.main(["--data-dir", FIXTURE_KB_DIR, "report",
                     "--case", os.path.join(REPO_DATA_DIR, "examples", "A2-fillet-weld.json"),
                     "--out", out])
    assert code == 0
    assert "验算书已导出" in capsys.readouterr().out
    assert find_external_refs(open(out, "rb").read()) == []


def test_report_cli_rejects_bad_input(tmp_path, capsys):
    capsys.readouterr()
    assert cli.main(["--data-dir", REPO_DATA_DIR, "report", "--case",
                     os.path.join(str(tmp_path), "nope.json"),
                     "--out", os.path.join(str(tmp_path), "x.docx")]) == 2
    assert "参数卡读取失败" in capsys.readouterr().err
    # --out 是必填：报告不能默默落到某个猜出来的目录
    with pytest.raises(SystemExit):
        cli.main(["--data-dir", REPO_DATA_DIR, "report", "--case",
                  os.path.join(REPO_DATA_DIR, "examples", "A2-fillet-weld.json")])


def test_check_and_checklist_export_via_cli(tmp_path, capsys, ir_path):
    check_out = os.path.join(str(tmp_path), "核查清单.docx")
    list_out = os.path.join(str(tmp_path), "检查单.docx")
    capsys.readouterr()
    assert cli.main(["--data-dir", REPO_DATA_DIR, "check", "--ir", ir_path,
                     "--out", check_out]) == 1
    printed = capsys.readouterr().out
    assert "docx 已导出" in printed

    assert cli.main(["--data-dir", REPO_DATA_DIR, "checklist", "--ir", ir_path,
                     "--out", list_out]) == 0
    assert "docx 已导出" in capsys.readouterr().out

    for path in (check_out, list_out):
        payload = open(path, "rb").read()
        assert find_external_refs(payload) == [], path
        assert find_personal_info(payload, _markers()) == [], path
        visible = "\n".join(p["text"] for p in read_document(path)["paragraphs"])
        assert DISCLAIMER in visible, path


def test_check_export_failure_is_exit_two(tmp_path, capsys, ir_path):
    """导出没落地就不能报成功：交付物缺失是输入/输出不可用（口径 K29），不是降级完成。"""
    blocker = os.path.join(str(tmp_path), "blocker")
    with open(blocker, "w", encoding="utf-8") as handle:
        handle.write("占位：让 sub 目录建不出来")
    capsys.readouterr()
    code = cli.main(["--data-dir", REPO_DATA_DIR, "check", "--ir", ir_path,
                     "--out", os.path.join(blocker, "sub", "y.docx")])
    assert code == 2
    assert "docx 写入失败" in capsys.readouterr().err
