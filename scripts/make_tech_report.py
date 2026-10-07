"""docs/技术报告.md → docs/技术报告.docx（程序化生成，禁止手改产物）。

为什么走程序而不是手改：交付物的四条硬断言（0 外链、无真实身份信息、两次导出字节一致、
免责声明必存）由 `sdc report` 的同一个导出器执行（口径 K40/K41/K42），手改的 docx 既没有
这四条保障，也会在下次重生成时被覆盖。

写入器逐成员固定 ZipInfo（ZIP_STORED + 1980-01-01 + 元数据占位符），所以"重生成位级一致"
成立，`tests/test_tech_report.py` 就按这条守门。

跑法：`py -3.8 -X utf8 scripts/make_tech_report.py`
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD = os.path.join(ROOT, "docs", "技术报告.md")
DOCX = os.path.join(ROOT, "docs", "技术报告.docx")

try:
    from sdc.report.docxio import export_docx
except ImportError:                                  # 没做 editable 安装时退回源码路径
    sys.path.insert(0, os.path.join(ROOT, "src"))
    from sdc.report.docxio import export_docx

_FENCE = re.compile(r"^\s*```")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_CODE_PREFIX = "    "


def _inline(text):
    """去掉行内标记：链接只留文字（URL 本身不许进交付物，口径 K40/K42）。"""
    text = re.sub(r"\[([^\]]+)\]\(([^)]*)\)", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text.strip()


def _is_cjk(char):
    return "\u3000" <= char <= "\u9fff" or char in "——·「」【】"


def _fold(lines):
    """把折行的段落并成一行：中文按无边框直接接，拉丁词之间补空格。

    不并行的话，跨行书写的 `**强调**` 与 `` `行内代码` `` 会把标记漏进交付物正文。
    """
    out = lines[0]
    for nxt in lines[1:]:
        gap = "" if (_is_cjk(out[-1]) or _is_cjk(nxt[0])) else " "
        out += gap + nxt
    return out


def md_to_paragraphs(markdown):
    paragraphs = []
    pending = []      # 普通段落的折行缓冲
    in_fence = False

    def flush():
        if pending:
            paragraphs.append(_inline(_fold(pending)))
            del pending[:]

    for raw in markdown.splitlines():
        line = raw.rstrip()
        if _FENCE.match(line):
            flush()
            in_fence = not in_fence
            continue
        if in_fence:
            paragraphs.append(_CODE_PREFIX + line)
            continue
        stripped = line.strip()
        if not stripped:
            flush()
            if paragraphs and paragraphs[-1] != "":
                paragraphs.append("")
            continue
        if stripped in ("---", "***"):
            flush()
            continue
        heading = _HEADING.match(stripped)
        if heading:
            flush()
            level, text = len(heading.group(1)), _inline(heading.group(2))
            # docx 写入器只有段落、没有 Word 样式，所以用符号标记层级（已知限制见报告 §6）
            paragraphs.append(("" if level <= 2 else "●" * (level - 2)) + text)
            continue
        if stripped.startswith(">"):
            flush()
            paragraphs.append(_inline(stripped.lstrip("> ")))
            continue
        if stripped.startswith("|"):
            flush()
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if cells and not all(set(cell) <= {"-", ":"} for cell in cells):
                paragraphs.append(" ｜ ".join(_inline(cell) for cell in cells if cell != ""))
            continue
        if re.match(r"^[-*]\s+", stripped):
            flush()
            paragraphs.append("· " + _inline(re.sub(r"^[-*]\s+", "", stripped)))
            continue
        pending.append(stripped)
    flush()
    while paragraphs and paragraphs[-1] == "":
        paragraphs.pop()
    return paragraphs


def build(md_path=MD, out_path=DOCX):
    with open(md_path, "r", encoding="utf-8") as handle:
        markdown = handle.read()
    paragraphs = md_to_paragraphs(markdown)
    return export_docx(paragraphs, out_path)


def main():
    if not os.path.isfile(MD):
        sys.stderr.write("找不到源 md：%s\n" % MD)
        return 2
    written = build()
    with open(written, "rb") as handle:
        payload = handle.read()
    sys.stdout.write("TECH_REPORT_DOCX_WRITTEN %s（%d 字节）\n" % (
        os.path.basename(written), len(payload)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
