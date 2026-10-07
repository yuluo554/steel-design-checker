"""CRLF 守门（口径 K8 的一部分）。

本机 `core.autocrlf=true`（仓库级与全局均如此），全新 clone 会把 LF 写成 CRLF；
一旦合成语料等冻结 fixtures 出现 CR，字节基准必挂。此测试让"仓库里出现 CR"直接失败。
"""

import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 守门范围 = 会被 clone 出来的文件。`.tmp_verify/` 与 `.tmp_parse/` 都在 .gitignore 里
# （取证缓存与 IR 工作目录，收尾不删），它们不落进仓库就不该参与跨平台字节基准，
# 但目录名必须写在这里——否则会话里一份带 CRLF 的临时输出会把守门测试本身打挂。
SKIP_DIRS = (".git", ".venv", "__pycache__", ".tmp_verify", ".tmp_parse",
             ".qoder-credits", ".pytest_cache", "build", "dist")
TEXT_EXTS = (".py", ".md", ".json", ".txt", ".toml", ".ini", ".cfg", ".yaml",
             ".yml", ".ps1", ".sh")
TEXT_NAMES = (".gitignore", ".gitattributes")


def _text_files():
    for root, dirs, files in os.walk(REPO):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.endswith(".egg-info"))
        for name in sorted(files):
            ext = os.path.splitext(name)[1]
            if ext in TEXT_EXTS or name in TEXT_NAMES:
                yield os.path.relpath(os.path.join(root, name), REPO)


def test_no_carriage_return_in_text_files():
    offenders = []
    for rel in _text_files():
        with open(os.path.join(REPO, rel), "rb") as handle:
            if b"\r" in handle.read():
                offenders.append(rel)
    assert offenders == [], "以下文本文件含 CR，会打挂跨平台字节基准：%s" % offenders


def test_gitattributes_declares_eol_lf():
    path = os.path.join(REPO, ".gitattributes")
    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()
    assert "text=auto eol=lf" in content, ".gitattributes 的 eol=lf 是对冲 autocrlf 的口径，不得移除"
