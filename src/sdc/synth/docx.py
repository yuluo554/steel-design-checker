"""最小 docx 写入器（只用标准库 zipfile）。

不用 python-docx 的原因：它会写入真实创建/修改时间与用户名，破坏"两次生成逐字节一致"
与口径 K8（产物无时间戳、docProps 元数据占位符化）。这里逐成员固定：

- 压缩方式 ZIP_STORED（deflate 输出随 zlib 版本而变，STORED 才能保证跨机器一致）；
- ZipInfo.date_time 固定 1980-01-01、external_attr 固定 0、create_system 固定 0；
- docProps 的 creator/lastModifiedBy 用占位符，时间戳写死 epoch。

产物只含文本部件，无超链接、无图片、无外部引用（0 外链硬断言的成立前提）。

`application` 与 `creator` 有默认值：合成语料用默认值（改了会打挂 `data/synth/` 的字节冻结），
报告导出（`sdc report`）另传自己的值。两条产物共用同一套固定 ZipInfo 写法，
"两次导出字节一致"因此是同一条纪律，不是两处各写一遍。
"""

import io
import zipfile
from typing import List, Tuple

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
FIXED_DATE_TIME = (1980, 1, 1, 0, 0, 0)
META_PLACEHOLDER = "SYNTH_PLACEHOLDER"
EPOCH_STAMP = "1970-01-01T00:00:00Z"
APP_NAME = "sdc-synth"

_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType='
    '"application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType='
    '"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/styles.xml" ContentType='
    '"application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
    '<Override PartName="/docProps/core.xml" ContentType='
    '"application/vnd.openxmlformats-package.core-properties+xml"/>'
    '<Override PartName="/docProps/app.xml" ContentType='
    '"application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
    '</Types>'
)

_ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
    'relationships/officeDocument" Target="word/document.xml"/>'
    '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/'
    'relationships/metadata/core-properties" Target="docProps/core.xml"/>'
    '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
    'relationships/extended-properties" Target="docProps/app.xml"/>'
    '</Relationships>'
)

_DOC_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
    'relationships/styles" Target="styles.xml"/>'
    '</Relationships>'
)

_STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:styles xmlns:w="%s"><w:docDefaults><w:rPrDefault><w:rPr>'
    '<w:rFonts w:ascii="SimSun" w:eastAsia="SimSun" w:hAnsi="SimSun"/>'
    '<w:sz w:val="21"/></w:rPr></w:rPrDefault></w:docDefaults>'
    '<w:style w:type="paragraph" w:styleId="Normal" w:default="1">'
    '<w:name w:val="Normal"/></w:style></w:styles>' % W_NS
)

def _core(creator: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties '
        'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<dc:creator>%s</dc:creator><cp:lastModifiedBy>%s</cp:lastModifiedBy>'
        '<dcterms:created xsi:type="dcterms:W3CDTF">%s</dcterms:created>'
        '<dcterms:modified xsi:type="dcterms:W3CDTF">%s</dcterms:modified>'
        '</cp:coreProperties>' % (creator, creator, EPOCH_STAMP, EPOCH_STAMP)
    )


def _app(application: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/'
        'extended-properties">'
        '<Application>%s</Application></Properties>' % application
    )


def _escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _paragraph(text: str) -> str:
    if not text:
        return "<w:p/>"
    return ('<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>' % _escape(text))


def document_xml(paragraphs: List[str]) -> str:
    body = "".join(_paragraph(line) for line in paragraphs)
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="%s"><w:body>%s'
            '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>'
            '</w:body></w:document>' % (W_NS, body))


def _entries(paragraphs: List[str], application: str, creator: str) -> List[Tuple[str, bytes]]:
    return [
        ("[Content_Types].xml", _CONTENT_TYPES.encode("utf-8")),
        ("_rels/.rels", _ROOT_RELS.encode("utf-8")),
        ("word/_rels/document.xml.rels", _DOC_RELS.encode("utf-8")),
        ("word/styles.xml", _STYLES.encode("utf-8")),
        ("word/document.xml", document_xml(paragraphs).encode("utf-8")),
        ("docProps/core.xml", _core(creator).encode("utf-8")),
        ("docProps/app.xml", _app(application).encode("utf-8")),
    ]


def build_docx(paragraphs: List[str], application: str = APP_NAME,
               creator: str = META_PLACEHOLDER) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for name, payload in _entries(paragraphs, application, creator):
            info = zipfile.ZipInfo(name, date_time=FIXED_DATE_TIME)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0
            info.create_system = 0
            archive.writestr(info, payload)
    return buffer.getvalue()


DOCX_PARTS = tuple(name for name, _payload in
                   _entries([], APP_NAME, META_PLACEHOLDER))
