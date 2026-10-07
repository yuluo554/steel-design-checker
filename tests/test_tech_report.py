"""材料固化的守门测试（M6）：docs/技术报告.md → docs/技术报告.docx 的三条联动。

- **产物不许手改**：docx 由 md 程序化生成，重生成必须逐字节相同（与合成语料同一条纪律）；
- **交付物四条硬断言**：0 外链、无真实身份信息、免责声明必存、正文残留 Markdown 标记即红
  （并段逻辑漏了标记，Word 里就会看见 `**`，那是版式事故）；
- **报告不许漂移**：§2.1 的记录计数表与 `sdc selfcheck` 的实测 counts 必须一致——
  指标表本身不在报告里复述（唯一来源是 README，由 test_suite.py 与实跑对账）。
"""

import importlib.util
import os

from sdc.report.docxio import body_text, find_external_refs
from sdc.selfcheck import build_report

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD = os.path.join(REPO, "docs", "技术报告.md")
DOCX = os.path.join(REPO, "docs", "技术报告.docx")

_spec = importlib.util.spec_from_file_location(
    "make_tech_report", os.path.join(REPO, "scripts", "make_tech_report.py"))
maker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(maker)

THEMES = ("条款-公式-符号表引擎", "条文核对与三档定档", "合成语料与内置基准")


def _md_text():
    with open(MD, "r", encoding="utf-8") as handle:
        return handle.read()


def _docx_bytes():
    with open(DOCX, "rb") as handle:
        return handle.read()


def test_report_and_docx_exist():
    assert os.path.isfile(MD) and os.path.isfile(DOCX), "md 先定稿，docx 由生成器产出"


def test_docx_is_byte_identical_to_regeneration(tmp_path):
    """产物是固化物：手改一次，重生成就会红。"""
    out = str(tmp_path / "技术报告.docx")
    maker.build(MD, out)
    with open(out, "rb") as handle:
        assert handle.read() == _docx_bytes(), "docx 与 md 重生成结果不一致：请跑 make_tech_report.py"


def test_docx_passes_the_four_delivery_assertions():
    payload = _docx_bytes()
    assert find_external_refs(payload) == []
    body = body_text(payload)
    from sdc.engine.core import DISCLAIMER
    assert DISCLAIMER in body
    for marker in ("**", chr(96), "](http"):
        assert marker not in body, "正文残留 Markdown 标记：%r" % marker


def test_docx_paragraphs_have_no_external_address():
    """正文里出现 URL scheme 或盘符路径就等于把交付物接到了外部（口径 K40/K42）。"""
    body = body_text(_docx_bytes())
    for mark in ("http:", "https:", "www.", "mailto:"):
        assert mark not in body.lower(), mark


def test_report_kind_counts_match_live_selfcheck():
    counts = build_report(os.path.join(REPO, "data"))["counts"]
    checked = 0
    for line in _md_text().splitlines():
        if not line.startswith("|") or "（" not in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 5 or not cells[1].isdigit():
            continue
        kind = cells[0].split("（")[0]
        if kind not in counts:
            continue
        assert int(cells[1]) == counts[kind]["total"], kind
        if cells[2].isdigit():
            assert int(cells[2]) == counts[kind]["verified"], "%s verified" % kind
            assert int(cells[3]) == counts[kind]["located"], "%s located" % kind
            assert int(cells[4]) == counts[kind]["pending"], "%s pending" % kind
        checked += 1
    assert checked >= 5, "报告 §2.1 的计数表没被解析到（改了体例要同步改这条测试）"


def test_report_covers_the_three_themes_and_the_honest_list():
    text = _md_text()
    for theme in THEMES:
        assert theme in text, "报告缺主题：%s" % theme
    assert "已知限制" in text and "免责声明" in text
    # 两个"不可判"与"没有任何模块出数值"必须在报告里如实出现，不许被写成达标
    assert "不可判" in text and "没有任何一个模块开始出数值" in text


def test_md_has_no_urls_or_absolute_paths():
    """md 是生成源：它干净了，docx 才可能过 0 外链；顺带保证脱敏扫描不会因为报告而红。"""
    text = _md_text()
    lowered = text.lower()
    for mark in ("http:", "https:", "www.", "mailto:"):
        assert mark not in lowered, "技术报告里不该出现外部地址：%s" % mark
    import re
    assert not re.search(r"(?<![A-Za-z0-9])(?i:[a-z]):[\\/]", text), "不该出现盘符绝对路径"
