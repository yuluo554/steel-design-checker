"""三类交付物的正文（验算书 / 核查清单 / 检查单）。

段落内容 = 报告头 + **终端渲染器的同一批行**（口径 K41：报告与 CLI 同源）。
不在这里重写一遍判定或排版逻辑，理由与 GUI 同一条（D08）：多写一套就多有的一套漂移，
而"报告里说的和终端里说的不一样"在辅助验算工具里属于最坏的缺陷。

报告只写"标准号 + 条号 + 渠道名"，**不写渠道 URL、不写绝对路径**：前者会把第三方镜像站点
打进交付物并触发 0 外链断言（口径 K40），后者会把机器名与用户名带出去（K42）。
URL 的归属地是取证台账（`data/README.md` 与 `.tmp_verify/`），不是对外文件。
"""

from typing import Any, Dict, List

from .. import __version__
from ..checklist import render_text as render_checklist
from ..engine.render import render_result
from ..rules.render import render_report

TITLE_RESULT = "钢结构连接与构件验算书"
TITLE_CHECK = "设计说明文本核查清单"
TITLE_CHECKLIST = "GB 55006-2021 符合性检查单"

# 报告头：依据版本（阶段三 任务 5）。文号/实施日期与 README「判定依据」表、
# data/review/ruleset-review.json 的 meta.review 三处一致，由 tests/test_clause_review.py 守门。
# 刻意不写「生成时间」：本仓交付物要求无身份信息 + 两次导出逐字节一致（K42）。
STANDARDS_LINE = ("依据规范：GB 50017-2017（2018-07-01 实施）、"
                  "GB 55006-2021（2022-01-01 实施）、JGJ 82-2011（2011-10-01 实施）；"
                  "本次复核 2026-10-19，下次复核 2027-10-19")


def _name(path: str) -> str:
    """只留文件名：绝对路径里带机器名与用户名，不进交付物（口径 K42）。"""
    text = str(path or "").replace("\\", "/").rstrip("/")
    return text.rsplit("/", 1)[-1] if text else ""


def _header(title: str, tool: str, extra: List[str]) -> List[str]:
    out = [title, "导出命令：sdc %s；引擎版本：%s" % (tool, __version__), STANDARDS_LINE]
    out.extend(line for line in extra if line)
    out.append("")
    return out


def result_body(result: Dict[str, Any], case_path: str = "") -> List[str]:
    lines = _header(TITLE_RESULT, "report", ["参数卡：%s" % _name(case_path)])
    lines.extend(render_result(result).split("\n"))
    return lines


def check_body(report: Dict[str, Any]) -> List[str]:
    lines = _header(TITLE_CHECK, "check",
                    ["文档：%s" % _name(report.get("doc", {}).get("name", ""))])
    lines.extend(render_report(report).split("\n"))
    return lines


def checklist_body(report: Dict[str, Any], ir_path: str = "") -> List[str]:
    lines = _header(TITLE_CHECKLIST, "checklist",
                    ["依据文档：%s" % _name(ir_path)])
    lines.extend(render_checklist(report).split("\n"))
    return lines
