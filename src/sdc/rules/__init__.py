"""文本核查规则层（M3）。

判定层，与 `sdc.parse`（解析层）之间只通过落盘的 IR 交接；本层不对文档执行正则
（`re` 会随 `parse.slots` 的 import 进来，真正被隔离的是抽取式匹配与文档读取——
实测与口径见 `.tmp_verify/m4/k26-import-graph/result.tsv`、K26/K39）。
"""

from .engine import (RuleError, build_units, condition_ok, findings_tokens,
                     judge_assert, run_rules)
from .gate import LEVEL_MATRIX, effective_status, level_for
from .render import render_report

__all__ = [
    "LEVEL_MATRIX",
    "RuleError",
    "build_units",
    "condition_ok",
    "effective_status",
    "findings_tokens",
    "judge_assert",
    "level_for",
    "render_report",
    "run_rules",
]
