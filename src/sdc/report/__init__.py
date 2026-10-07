"""报告导出层（M4）：Result / 核查报告 / 检查单报告 → docx 交付物。

只用标准库，不引入 python-docx（口径 K40 的成立前提，也是 `data/synth/` 字节冻结的同一套写法）。
"""

from .body import (TITLE_CHECK, TITLE_CHECKLIST, TITLE_RESULT, check_body,
                   checklist_body, result_body)
from .docxio import (REPORT_APP_NAME, REPORT_PLACEHOLDER, ReportError,
                     body_text, docx_bytes, export_docx, find_external_refs,
                     find_personal_info, metadata_values)

__all__ = [
    "REPORT_APP_NAME", "REPORT_PLACEHOLDER", "ReportError",
    "TITLE_CHECK", "TITLE_CHECKLIST", "TITLE_RESULT",
    "body_text", "check_body", "checklist_body", "docx_bytes", "export_docx",
    "find_external_refs", "find_personal_info", "metadata_values", "result_body",
]
