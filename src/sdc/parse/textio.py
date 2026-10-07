"""文档 → 段落文本（只用标准库）。

支持 `.docx`（OOXML zip 直读，不引第三方 docx 库——口径 K27 与合成生成器同一理由：
引入 python-docx 只会带来版本与打包面，读取需求只有"取正文文本"）、`.txt`/`.md`。

段落序号 `index` 从 0 起，是核查结论回指原文位置的唯一坐标；`.txt` 另记原始行号。
"""

import hashlib
import io
import os
import zipfile
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

from .errors import ParseError

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
DOC_PART = "word/document.xml"
MAX_TEXT_BYTES = 32 * 1024 * 1024
_TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030")


def _tag(name: str) -> str:
    return "{%s}%s" % (W_NS, name)


def _paragraph_text(node) -> str:
    parts = []
    for run in node.iter():
        if run.tag == _tag("t") and run.text:
            parts.append(run.text)
        elif run.tag in (_tag("tab"), _tag("br")):
            parts.append(" ")
    return "".join(parts).strip()


def docx_paragraphs(payload: bytes) -> List[str]:
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            if DOC_PART not in archive.namelist():
                raise ParseError("docx 缺少 %s（不是有效的 WordprocessingML 文档）" % DOC_PART)
            total = sum(info.file_size for info in archive.infolist())
            if total > MAX_TEXT_BYTES:
                raise ParseError("docx 解压后体积 %d 字节超过上限 %d，拒绝解析" % (
                    total, MAX_TEXT_BYTES))
            xml = archive.read(DOC_PART)
    except zipfile.BadZipFile as exc:
        raise ParseError("docx 不是合法 zip（文件损坏或不是 docx）：%s" % exc)

    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ParseError("word/document.xml 解析失败：%s" % exc)

    body = root.find(_tag("body"))
    if body is None:
        raise ParseError("word/document.xml 没有 w:body")

    out = []  # type: List[str]
    for child in body:
        if child.tag == _tag("p"):
            out.append(_paragraph_text(child))
        elif child.tag == _tag("tbl"):
            for row in child.iter(_tag("tr")):
                cells = [_paragraph_text(cell) for cell in row.findall(_tag("tc"))]
                out.append(" | ".join(cell for cell in cells if cell))
    return out


def plain_text_paragraphs(payload: bytes) -> Tuple[List[str], str]:
    encoding = None  # type: Optional[str]
    text = None  # type: Optional[str]
    for candidate in _TEXT_ENCODINGS:
        try:
            text = payload.decode(candidate)
            encoding = candidate
            break
        except UnicodeDecodeError:
            continue
    if text is None or encoding is None:
        raise ParseError("文本文件编码无法识别（尝试过：%s）" % ", ".join(_TEXT_ENCODINGS))
    paragraphs = []  # type: List[str]
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            paragraphs.append(stripped)
    return paragraphs, encoding


def read_document(path: str) -> Dict[str, Any]:
    """文档 → {"paragraphs":[{"index","text","line"}], "encoding", "format", "sha256"}。"""
    try:
        with open(path, "rb") as handle:
            payload = handle.read()
    except OSError as exc:
        raise ParseError("文档读取失败：%s" % exc)

    digest = hashlib.sha256(payload).hexdigest()
    suffix = os.path.splitext(path)[1].lower()

    encoding = ""
    if suffix == ".docx":
        fmt = "docx"
        texts = docx_paragraphs(payload)
    elif suffix in (".txt", ".md"):
        fmt = "text"
        texts, encoding = plain_text_paragraphs(payload)
    else:
        raise ParseError("不支持的文档格式 %r（首期支持 .docx/.txt/.md；PDF 属扩展项）" % suffix)

    paragraphs = []
    for index, text in enumerate(texts):
        paragraphs.append({"index": index, "line": index + 1, "text": text})

    return {
        "format": fmt,
        "encoding": encoding,
        "sha256": digest,
        "byte_size": len(payload),
        "paragraph_count": len(paragraphs),
        "paragraphs": paragraphs,
    }
