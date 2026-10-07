"""docx 报告的落盘与交付物自检（0 外链 / 无个人信息 / 字节一致）。

写入走 `synth.docx.build_docx` 的固定 ZipInfo 写法：同一批段落两次导出必然得到同一串字节，
所以"两次导出字节一致"与合成语料是同一条纪律，M5 打包断言也只需认这一处。

`find_external_refs` 是 plan/05 §六「0 外链」的机器定义（口径 K40）：

1. 部件集合必须等于白名单（多一个部件＝多一个可能的引用入口）；
2. `.rels` 的每个 Relationship：**目标**（`Target`）不得是 URL 或绝对路径，
   `TargetMode` 不得为 `External`。`Type` 属性天生是 `http://schemas.openxmlformats.org/…`
   这种关系类型标识符，不属于对外引用，因此不参与检查；
3. `word/document.xml` 不得含 `<w:hyperlink`（超链接字段）；
4. **正文文字**（`w:t` 节点）不得含 URL scheme、`www.`、盘符绝对路径。

第 4 条只看正文而不是整份 XML，是因为 OOXML 的命名空间声明本身就是 `http://` 开头的 URI
（`xmlns:w="http://schemas.openxmlformats.org/..."`）——那是部件格式声明，不是对外资源引用。
把命名空间当外链会在任何合法 docx 上都误报，真正的泄漏路径是正文里打进渠道 URL 或
`C:\\Users\\<name>\\…` 这类绝对路径，所以本模块同时提供 `find_personal_info`。
"""

import io
import os
import zipfile
from xml.etree import ElementTree
from typing import Dict, List, Sequence

from ..engine.core import DISCLAIMER
from ..synth.docx import DOCX_PARTS, W_NS, build_docx

DC_NS = "http://purl.org/dc/elements/1.1/"
CP_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"

REPORT_APP_NAME = "sdc-report"
REPORT_PLACEHOLDER = "REPORT_PLACEHOLDER"

# 正文里出现任一即算对外引用；scheme 一律按小写比对（正文本身不保证小写）
URL_MARKS = ("http:", "https:", "ftp:", "mailto:", "file:", "www.")


class ReportError(Exception):
    """报告落盘失败（目录不可写、磁盘满一类）。"""


def export_docx(paragraphs: Sequence[str], out_path: str) -> str:
    """落盘前先跑交付物自检：外链或免责声明缺失 ⇒ 拒绝写出（fail closed）。

    把断言放在写文件的这一步，而不是只放在测试里，是因为"报告少一句免责声明"这种缺陷
    一旦落到交付物上就是对外事故；测试只能证明本仓库的三份样例正文，命令面得自己把关。
    """
    payload = docx_bytes(paragraphs)
    problems = find_external_refs(payload)
    if DISCLAIMER not in body_text(payload):
        problems.append("正文缺免责声明（%s）" % DISCLAIMER)
    if problems:
        raise ReportError("交付物自检未通过，未写出 %s：%s" % (
            out_path, "；".join(problems)))
    directory = os.path.dirname(os.path.abspath(out_path))
    try:
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(out_path, "wb") as handle:
            handle.write(payload)
    except OSError as exc:
        raise ReportError("docx 写入失败：%s（%s）" % (out_path, exc))
    return out_path


def docx_bytes(paragraphs: Sequence[str]) -> bytes:
    return build_docx(list(paragraphs), application=REPORT_APP_NAME,
                      creator=REPORT_PLACEHOLDER)


def _parts(payload: bytes) -> Dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        return dict((info.filename, archive.read(info.filename)) for info in archive.infolist())


def body_text(payload: bytes) -> str:
    """正文文字（按段落拼接），即"交付物里真正看得见的内容"。"""
    document = _parts(payload)["word/document.xml"]
    root = ElementTree.fromstring(document)
    lines = []  # type: List[str]
    for paragraph in root.iter("{%s}p" % W_NS):
        texts = [node.text or "" for node in paragraph.iter("{%s}t" % W_NS)]
        lines.append("".join(texts))
    return "\n".join(lines)


def _drive_path_hit(text: str) -> str:
    """`C:/x` 与 `C:\\x` 形态的绝对路径；返回命中的片段，未命中返回空串。"""
    for index, char in enumerate(text):
        if not char.isalpha() or len(text) <= index + 2:
            continue
        if text[index + 1] == ":" and text[index + 2] in ("/", "\\"):
            return text[index:index + 12]
    return ""


def _rels_violations(name: str, raw: bytes) -> List[str]:
    """关系部件只检查 `Target`：`Type` 属性天然是 `http://schemas.openxmlformats.org/…`
    这种格式标识符，把它当外链会在任何合法 docx 上都误报（同 body_text 只查正文的理由）。"""
    out = []  # type: List[str]
    root = ElementTree.fromstring(raw)
    for element in root.iter():
        if not element.tag.endswith("}Relationship"):
            continue
        target = element.attrib.get("Target", "")
        if element.attrib.get("TargetMode") == "External":
            out.append("%s 的关系 %s 声明为外部（TargetMode=External）" % (
                name, element.attrib.get("Id", "?")))
        lowered = target.lower()
        for mark in URL_MARKS:
            if mark in lowered:
                out.append("%s 的关系目标是外部地址：%s" % (name, target))
                break
        hit = _drive_path_hit(target)
        if hit:
            out.append("%s 的关系目标是绝对路径：%s" % (name, hit))
    return out


def find_external_refs(payload: bytes) -> List[str]:
    violations = []  # type: List[str]
    parts = _parts(payload)

    for name in sorted(set(parts) - set(DOCX_PARTS)):
        violations.append("部件不在白名单内：%s" % name)
    for name in sorted(set(DOCX_PARTS) - set(parts)):
        violations.append("缺少预期部件：%s" % name)

    for name, raw in sorted(parts.items()):
        if not name.endswith(".rels"):
            continue
        try:
            violations.extend(_rels_violations(name, raw))
        except ElementTree.ParseError as exc:
            violations.append("%s 不是合法 XML：%s" % (name, exc))

    document = parts.get("word/document.xml", b"").decode("utf-8", "replace")
    if "<w:hyperlink" in document:
        violations.append("正文含超链接字段 <w:hyperlink>")

    visible = body_text(payload)
    lowered = visible.lower()
    for mark in URL_MARKS:
        if mark in lowered:
            violations.append("正文出现外部地址 %r（出处只写标准号+条号+渠道名，不写 URL）" % mark)
    hit = _drive_path_hit(visible)
    if hit:
        violations.append("正文出现绝对路径 %r（交付物只写文件名，路径里带机器与用户名）" % hit)
    return violations


def metadata_values(payload: bytes) -> Dict[str, str]:
    """docProps 里能落到"是谁在什么机器上导出的"的几个字段。"""
    parts = _parts(payload)
    out = {}  # type: Dict[str, str]
    core = parts.get("docProps/core.xml")
    if core:
        root = ElementTree.fromstring(core)
        for tag, name in (("{%s}creator" % DC_NS, "creator"),
                          ("{%s}lastModifiedBy" % CP_NS, "lastModifiedBy")):
            node = root.find(tag)
            out[name] = (node.text or "") if node is not None else ""
    app = parts.get("docProps/app.xml")
    if app:
        root = ElementTree.fromstring(app)
        node = root.find("{*}Application")
        out["Application"] = (node.text or "") if node is not None else ""
    return out


def find_personal_info(payload: bytes, markers: Sequence[str]) -> List[str]:
    """硬断言"无真实个人信息"：正文与元数据里都不得出现机器用户名、home 路径、署名。

    环境相关的比对样本由调用方（测试）给出，本模块不猜哪串字符串算个人信息；
    元数据的 creator/lastModifiedBy 必须是占位符，这是 python-docx 会被禁掉的原因。
    """
    violations = []  # type: List[str]
    values = metadata_values(payload)
    for field in ("creator", "lastModifiedBy"):
        if values.get(field) != REPORT_PLACEHOLDER:
            violations.append("docProps.%s=%r 不是占位符" % (field, values.get(field, "")))
    if values.get("Application") != REPORT_APP_NAME:
        violations.append("docProps.Application=%r 不是本工具标识" % values.get("Application"))

    haystack = body_text(payload) + "\n" + "\n".join(
        "%s=%s" % (key, value) for key, value in sorted(values.items()))
    for marker in markers:
        needle = str(marker or "").strip()
        if len(needle) >= 3 and needle in haystack:
            violations.append("交付物出现真实身份信息 %r" % needle)
    return violations
