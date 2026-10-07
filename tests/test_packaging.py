"""打包面测试：子进程通路的冻结分支、白名单单一事实源、构建红线断言本身。

`verify_dist.py` 是发布门，所以它自己也要有反证测试：伪造一棵 dist 树，逐项种违反，
扫描器必须每一项都点名——扫不出东西的守门脚本等于没有守门。
"""

import hashlib
import os
import shutil
import sys

from _helpers import REPO_DATA_DIR  # noqa: F401  （与其它测试同一份路径口径）

from sdc import suite

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import bundle_rules  # noqa: E402
import verify_dist  # noqa: E402


# ---------------------------------------------------------------------------
# 口径 K45：打包版的 CLI 子进程通路
# ---------------------------------------------------------------------------

def test_source_mode_uses_the_interpreter(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delenv(suite.CLI_ENV_VAR, raising=False)
    argv, cwd = suite.cli_channel()
    assert argv == [sys.executable, "-X", "utf8", "-m", "sdc"]
    assert os.path.basename(cwd) == "src"


def test_frozen_mode_uses_the_sibling_cli_exe(monkeypatch, tmp_path):
    gui_dir = tmp_path / "sdc-gui"
    cli_dir = tmp_path / "sdc-cli"
    gui_dir.mkdir()
    cli_dir.mkdir()
    gui_exe = gui_dir / "sdc-gui.exe"
    gui_exe.write_bytes(b"MZ")
    cli_exe = cli_dir / "sdc-cli.exe"
    cli_exe.write_bytes(b"MZ")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(gui_exe))
    monkeypatch.delenv(suite.CLI_ENV_VAR, raising=False)
    argv, cwd = suite.cli_channel()
    assert argv == [str(cli_exe)]
    assert cwd == str(cli_dir)


def test_frozen_mode_prefers_an_explicit_env_override(monkeypatch, tmp_path):
    gui_exe = tmp_path / "sdc-gui.exe"
    gui_exe.write_bytes(b"MZ")
    pointed = tmp_path / "elsewhere" / "sdc-cli.exe"
    pointed.parent.mkdir()
    pointed.write_bytes(b"MZ")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(gui_exe))
    monkeypatch.setenv(suite.CLI_ENV_VAR, str(pointed))
    argv, _cwd = suite.cli_channel()
    assert argv == [str(pointed)]


def test_frozen_mode_without_cli_reports_no_channel(monkeypatch, tmp_path):
    gui_exe = tmp_path / "sdc-gui.exe"
    gui_exe.write_bytes(b"MZ")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(gui_exe))
    monkeypatch.delenv(suite.CLI_ENV_VAR, raising=False)
    argv, _cwd = suite.cli_channel()
    assert argv is None
    rc, output = suite.run_cli(["parse", "--dir", "x", "--out-dir", "y"], REPO_DATA_DIR)
    assert rc is None
    assert "不可用" in output and "sdc-cli" in output


def test_unavailable_channel_degrades_the_row_instead_of_passing(monkeypatch):
    """HANDOFF-M5 §三.4 的那条：通路没了只能显示「不可用」，不许静默变达标。"""
    monkeypatch.setattr(suite, "run_cli", lambda *a, **k: (None, "子进程不可用"))
    result = suite.parse_corpus_twice(REPO_DATA_DIR, "unused-workdir")
    assert result["status"] == "unavailable"
    assert suite.STATUS_LABEL[result["status"]] == "不可用"
    assert suite._exit_code([suite._row("确定性回归", "100%", "x", result["status"], "s")]) == 2


# ---------------------------------------------------------------------------
# 白名单单一事实源
# ---------------------------------------------------------------------------

def test_whitelist_covers_every_runtime_data_directory():
    for name in bundle_rules.DATA_SUBDIRS:
        assert os.path.isdir(os.path.join(REPO_DATA_DIR, name)), name
    top = sorted(name for name in os.listdir(REPO_DATA_DIR)
                 if os.path.isdir(os.path.join(REPO_DATA_DIR, name)))
    unknown = [name for name in top
               if name not in bundle_rules.DATA_SUBDIRS
               and name not in bundle_rules.DATA_EXCLUDED]
    assert not unknown, "data/ 出现了既没入包也没登记排除的目录：%s" % unknown
    assert "README.md" in bundle_rules.DATA_EXCLUDED, "取证台账（含渠道 URL）必须排除（K42）"


def test_data_pairs_fails_loudly_when_a_whitelisted_directory_is_missing(tmp_path):
    empty = str(tmp_path)
    try:
        bundle_rules.data_pairs(empty)
    except SystemExit as exc:
        assert "不存在" in str(exc)
    else:
        raise AssertionError("白名单目录缺失时必须大声失败")


def test_spec_and_entries_are_thin_and_excluded_from_the_cli_bundle():
    with open(os.path.join(ROOT, "sdc.spec"), "r", encoding="utf-8") as handle:
        spec = handle.read()
    assert "from bundle_rules import data_pairs" in spec      # 白名单不在 spec 里另写一份
    assert 'name="sdc-cli"' in spec and "console=True" in spec
    assert 'name="sdc-gui"' in spec and "console=False" in spec
    cli_block = spec.split("a_cli = Analysis")[1].split("coll_cli")[0]
    assert "PySide6" in cli_block and "sdc.gui" in cli_block   # 界面依赖不许漏进控制台包

    for entry, marker in (("entry_cli.py", "sdc.cli"), ("entry_gui.py", "sdc.gui.app")):
        path = os.path.join(ROOT, "scripts", entry)
        with open(path, "r", encoding="utf-8") as handle:
            source = handle.read()
        assert marker in source
        assert len(source.splitlines()) < 30, "入口脚本只准薄薄一层"


def test_gitignore_keeps_the_spec_tracked():
    with open(os.path.join(ROOT, ".gitignore"), "r", encoding="utf-8") as handle:
        lines = [line.strip() for line in handle]
    assert "*.spec" in lines and "!sdc.spec" in lines


# ---------------------------------------------------------------------------
# 构建红线断言脚本自身
# ---------------------------------------------------------------------------

def _sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def make_fake_dist(base, repo_data_dir=REPO_DATA_DIR):
    """造一棵"应当全绿"的假 dist：两个包 + 内嵌数据逐份一致 + GUI 旁边有 CLI exe。

    复制是**整目录**的：`data/synth/docx/` 里的 24 份语料也在白名单内，
    对账必须连子目录一起比，否则等于没查。
    """
    dist = os.path.join(str(base), "dist")
    for name in sorted(bundle_rules.BUNDLES):
        bundle = os.path.join(dist, name)
        os.makedirs(bundle)
        with open(os.path.join(bundle, bundle_rules.BUNDLES[name]["exe"]), "wb") as handle:
            handle.write(b"MZ")
        internal = os.path.join(bundle, "_internal")
        os.makedirs(internal)
        if name == "sdc-gui":
            os.makedirs(os.path.join(internal, "PySide6"))
        embedded = os.path.join(internal, "data")
        for subdir in bundle_rules.DATA_SUBDIRS:
            shutil.copytree(os.path.join(repo_data_dir, subdir),
                            os.path.join(embedded, subdir))
    return dist


def test_fake_clean_dist_passes_the_audit(tmp_path):
    dist = make_fake_dist(tmp_path)
    problems, stats = verify_dist.audit(dist, REPO_DATA_DIR)
    assert problems == [], problems
    assert len(stats) == 2


def test_audit_reconciles_nested_data_files(tmp_path):
    """子目录里的语料被改一个字节也必须被抓出来。"""
    dist = make_fake_dist(tmp_path)
    target = os.path.join(dist, "sdc-gui", "_internal", "data", "synth", "docx")
    assert os.path.isdir(target)
    victim = os.path.join(target, sorted(os.listdir(target))[0])
    with open(victim, "ab") as handle:
        handle.write(b" ")
    problems, _stats = verify_dist.audit(dist, REPO_DATA_DIR)
    assert any("synth/docx/" in problem and "字节不一致" in problem
               for problem in problems), problems


def test_audit_names_every_planted_violation(tmp_path):
    dist = make_fake_dist(tmp_path)
    cli_bundle = os.path.join(dist, "sdc-cli")

    # ① 禁区成分：取证缓存目录混进包
    os.makedirs(os.path.join(cli_bundle, "_internal", ".tmp_verify"))
    # ② 禁区文件：台账跟进了包
    with open(os.path.join(cli_bundle, "_internal", "data", "README.md"), "w",
              encoding="utf-8") as handle:
        handle.write("# 台账\n")
    # ③ 内嵌数据被改过一个字节
    tampered = os.path.join(cli_bundle, "_internal", "data", "clauses",
                            os.listdir(os.path.join(REPO_DATA_DIR, "clauses"))[0])
    with open(tampered, "ab") as handle:
        handle.write(b" ")
    # ④ 白名单外多塞了一个文件
    with open(os.path.join(cli_bundle, "_internal", "data", "symbols", "extra.json"),
              "w", encoding="utf-8") as handle:
        handle.write("{}")
    # ⑤ 整个白名单目录没入包
    # ⑥ GUI 依赖漏进 CLI 包
    os.makedirs(os.path.join(cli_bundle, "_internal", "PySide6"))
    # ⑦ GUI 旁边没有配套 CLI exe ⇒ K45 通路断掉
    os.remove(os.path.join(dist, "sdc-cli", "sdc-cli.exe"))

    problems, _stats = verify_dist.audit(dist, REPO_DATA_DIR)
    joined = "\n".join(problems)
    assert ".tmp_verify" in joined
    assert "README.md" in joined
    assert "字节不一致" in joined
    assert "白名单外的多出文件" in joined
    assert "混进了界面依赖" in joined
    assert "sdc-cli.exe" in joined


def test_audit_fails_when_a_whitelisted_directory_is_not_packed(tmp_path):
    dist = make_fake_dist(tmp_path)
    missing = os.path.join(dist, "sdc-gui", "_internal", "data", "rules")
    for name in os.listdir(missing):
        os.remove(os.path.join(missing, name))
    problems, _stats = verify_dist.audit(dist, REPO_DATA_DIR)
    assert any("data/rules/" in problem and "未入包" in problem
               for problem in problems), problems


def test_main_returns_one_on_violations_and_zero_when_clean(tmp_path, capsys):
    dist = make_fake_dist(tmp_path)
    assert verify_dist.main(["--dist", dist, "--data", REPO_DATA_DIR]) == 0
    assert "DIST_AUDIT_OK" in capsys.readouterr().out
    os.makedirs(os.path.join(dist, "sdc-cli", "_internal", "plan"))
    assert verify_dist.main(["--dist", dist, "--data", REPO_DATA_DIR]) == 1


def test_real_build_is_audited_when_dist_exists():
    """本机跑过 `pyinstaller sdc.spec` 之后，这条就把真产物过一遍红线。

    没有 dist 时是**声明式跳过**（不是静默少跑）：`-rs` 看得到原因，CI 与干净环境
    要么先构建再跑，要么按这条的跳过计数对账。
    """
    import pytest

    dist = os.path.join(ROOT, "dist")
    if not os.path.isdir(dist):
        pytest.skip("尚未构建：py -3.8 -m PyInstaller sdc.spec")
    problems, stats = verify_dist.audit(dist, REPO_DATA_DIR)
    assert problems == [], problems
    assert len(stats) == 2
