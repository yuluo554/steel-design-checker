"""CLI 命令面（plan/03 §五）。退出码 0 完成 / 1 降级完成 / 2 输入不可用（口径 K9）。

M3 新增 `parse` / `check` / `checklist` 与 `bench --parse/--audit`；
M4 新增 `report`（docx 验算书）与 `check`/`checklist` 的 `--out`（docx 交付物），
以及 `bench --sweep`（确定性回归）与 `bench --all`（四基准合一 + 指标表）。
解析与判定分命令、以落盘 IR 交接（口径 K26）：`check`/`checklist`/`bench --audit` 不读文档、
不对文档执行正则，一键基准需要 IR 时**另起子进程**跑 `sdc parse`（口径 K39）。

`check` 的退出码（口径 K29）：0 = 文档无非 pass 项；1 = 存在可疑或异常（等级差异看报告，
不看码）；2 = 文档/IR/数据不可用。`checklist`：1 还包含"没接 IR"或"章节未覆盖齐"。
"""

import argparse
import json
import os
import sys
from typing import Any, Optional

from . import __version__, bench as bench_module
from . import checklist as checklist_module
from . import suite
from .engine import run_case, result_exit_code
from .engine.core import DISCLAIMER
from .engine.errors import EngineError, ExprError, InputError
from .kb.loader import load_kb
from .kb.schema import MODULES
from .paths import DataDirNotFound, find_data_dir
from .parse import (build_ir, card_gaps, default_ir_path, load_ir, write_ir)
from .parse.errors import IrError, ParseError
from .report import (ReportError, check_body, checklist_body, export_docx,
                     result_body)
from .rules import render_report, run_rules
from .rules.engine import RuleError
from .selfcheck import build_report, render_text
from .synth.generator import DEFAULT_SEED, compare_corpus, generate_corpus

EXIT_OK = 0
EXIT_DEGRADED = 1
EXIT_BAD_INPUT = 2

DOC_SUFFIXES = (".docx", ".txt", ".md")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdc", description="钢结构连接与构件验算计算器（辅助工具，不替代正式设计文件）")
    parser.add_argument("--version", action="version", version="sdc %s" % __version__)
    parser.add_argument("--data-dir", default=None,
                        help="知识库数据目录；默认按 find_data_dir 优先级解析")
    sub = parser.add_subparsers(dest="command")

    selfcheck = sub.add_parser("selfcheck", help="数据完整性 + status 门控审计 + 待核对看板")
    selfcheck.add_argument("--json", action="store_true", dest="as_json",
                           help="输出机器可读 JSON（排序键、无时间戳）")

    synth = sub.add_parser("synth", help="重新生成或校验合成设计说明语料（固定 seed，位级一致）")
    synth.add_argument("--seed", type=int, default=DEFAULT_SEED,
                       help="生成种子，默认 %d" % DEFAULT_SEED)
    synth.add_argument("--check", action="store_true",
                       help="不写文件，只校验仓内语料与按 seed 重生成的结果是否逐字节一致")

    run = sub.add_parser("run", help="单模块验算：参数卡 → Result（blocked 时不出数值）")
    run.add_argument("--case", required=True, metavar="X.json", help="参数卡 JSON 文件")
    run.add_argument("--module", default=None, choices=list(MODULES),
                     help="可选校验：与参数卡里的 module 必须一致")
    run.add_argument("--json", action="store_true", dest="as_json",
                     help="输出机器可读 JSON（排序键、无时间戳）")

    b = sub.add_parser("bench", help="内置基准：算例通过率 / 解析 F1 / 核查检出率 / 一键四基准")
    b.add_argument("--cases", action="store_true", dest="only_cases",
                   help="只对账 data/cases，跳过引擎自校验样例")
    b.add_argument("--parse", action="store_true", dest="bench_parse",
                   help="解析字段级 P/R/F1 对账 data/synth 真值（只吃 --ir-dir 的 IR）")
    b.add_argument("--audit", action="store_true", dest="bench_audit",
                   help="缺陷检出率/误报对账注入清单（只吃 --ir-dir 的 IR）")
    b.add_argument("--sweep", action="store_true", dest="bench_sweep",
                   help="确定性回归：算例两次一致 + 整批 IR 两次字节一致 + 报告与 docx 两次一致")
    b.add_argument("--all", action="store_true", dest="bench_all",
                   help="四基准合一：算例通过率 / 确定性回归 / 解析 F1 / 检出率与误报 + 指标表")
    b.add_argument("--ir-dir", default=None, metavar="DIR", dest="ir_dir",
                   help="`sdc parse` 产出的 IR 目录（--parse/--audit 必填；--all 缺省时自己跑解析）")
    b.add_argument("--workdir", default=None, metavar="DIR",
                   help="--sweep/--all 的两次解析工作目录，默认 .tmp_parse/suite")
    b.add_argument("--markdown", action="store_true", dest="as_markdown",
                   help="--all 的指标表以 Markdown 打印（README 引用的是同一张表）")
    b.add_argument("--json", action="store_true", dest="as_json",
                   help="输出机器可读 JSON（排序键、无时间戳）")

    p = sub.add_parser("parse", help="文档 → 参数卡 IR（解析层，落盘后交给 check）")
    p.add_argument("--doc", default=None, metavar="X.docx", help="单个文档（.docx/.txt/.md）")
    p.add_argument("--dir", default=None, metavar="DIR", dest="doc_dir",
                   help="批量：目录内全部文档（按文件名排序），用于合成语料评测")
    p.add_argument("--out", default=None, metavar="X.ir.json",
                   help="IR 输出路径（单文档模式，默认 .tmp_parse/<文档名>.ir.json）")
    p.add_argument("--out-dir", default=None, metavar="DIR", dest="ir_dir",
                   help="IR 输出目录（批量模式）")
    p.add_argument("--module", default=None, choices=list(MODULES),
                   help="可选：只列该模块距可运行参数卡的缺口")
    p.add_argument("--json", action="store_true", dest="as_json",
                   help="输出机器可读 JSON（排序键、无时间戳）")

    c = sub.add_parser("check", help="规则引擎三级判定：IR → 异常/可疑清单（不读文档）")
    c.add_argument("--ir", required=True, metavar="X.ir.json",
                   help="`sdc parse` 产出的 IR 文件")
    c.add_argument("--out", default=None, metavar="X.docx", dest="out_path",
                   help="可选：同时导出 docx 核查清单（落盘前跑 0 外链与免责声明自检）")
    c.add_argument("--json", action="store_true", dest="as_json",
                   help="输出机器可读 JSON（排序键、无时间戳）")

    k = sub.add_parser("checklist", help="GB 55006-2021 符合性检查单（全 8 章，缺口显式）")
    k.add_argument("--ir", default=None, metavar="X.ir.json", dest="ir_path",
                   help="可选：接入 `sdc parse` 的 IR 做自动初判；不接则全部待人工确认")
    k.add_argument("--answers", default=None, metavar="A.json",
                   help='可选：人工答复 {"条目 id": "符合|不符合|不适用|待确认"}')
    k.add_argument("--out", default=None, metavar="X.docx", dest="out_path",
                   help="可选：同时导出 docx 符合性检查单（逐条带判定与出处）")
    k.add_argument("--json", action="store_true", dest="as_json",
                   help="输出机器可读 JSON（排序键、无时间戳）")

    r = sub.add_parser("report", help="导出 docx 验算书：参数卡 → 逐步计算/拒算依据 + 出处 + 免责声明")
    r.add_argument("--case", required=True, metavar="X.json", help="参数卡 JSON 文件")
    r.add_argument("--module", default=None, choices=list(MODULES),
                   help="可选校验：与参数卡里的 module 必须一致")
    r.add_argument("--out", required=True, metavar="X.docx", dest="out_path",
                   help="验算书输出路径（blocked 也照样出，逐项写明缺哪条核对）")

    g = sub.add_parser("gui", help="启动 PySide6 桌面界面（五页签，只消费本命令面同一套 API）")
    g.add_argument("--screenshot", default=None, metavar="X.png", dest="screenshot",
                   help="截一张主窗口帧后退出（native QPA 才有中文字体，口径见 plan/03 §六）")
    return parser


def _utf8_stream(stream) -> None:
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass  # stdout/stderr 被换成不支持 reconfigure 的对象（测试捕获时）


def _emit(text: str) -> None:
    _utf8_stream(sys.stdout)
    print(text)


def _err(text: str) -> None:
    """错误信息走 stderr，编码口径与 `_emit` 一致。

    实测：冻结 exe 的 stderr 默认跟随系统代码页（本机 GBK），stdout 却是 UTF-8，
    同一句话在 `python -X utf8 -m sdc` 与 `sdc-cli.exe` 里会落成两种字节 ——
    干净环境验证抓到的就是这一条（口径 K47）。
    """
    _utf8_stream(sys.stderr)
    sys.stderr.write(text)


def _cmd_selfcheck(data_dir: str, as_json: bool) -> int:
    report = build_report(data_dir)
    if as_json:
        _emit(json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2))
    else:
        _emit(render_text(report))
    return EXIT_OK if report["ok"] else EXIT_DEGRADED


def _cmd_synth(data_dir: str, seed: int, check: bool) -> int:
    if check:
        problems = compare_corpus(data_dir, seed)
        if problems:
            _emit("合成语料与固定 seed 重生成结果不一致（seed=%d）：" % seed)
            for problem in problems:
                _emit("  - %s" % problem)
            return EXIT_DEGRADED
        _emit("合成语料位级一致（seed=%d）。" % seed)
        return EXIT_OK

    manifest = generate_corpus(os.path.join(data_dir, "synth"), seed)
    _emit("已生成合成语料 %d 份（干净 %d / 含注入 %d），seed=%d" % (
        manifest["doc_count"], manifest["clean_count"], manifest["injected_count"], seed))
    for injection_type in sorted(manifest["injection_counts"]):
        _emit("  %-28s %d 处" % (injection_type, manifest["injection_counts"][injection_type]))
    return EXIT_OK


def load_kb_or_error(data_dir: str):
    """加载知识库，返回 (kb 或 None, 错误信息)。数据有结构/引用问题时带着说明拒绝计算。

    错误信息以**字符串**返回而不是直接写 stderr：CLI 写 stderr，GUI 显示在界面上，
    但两条通路判的是同一件事（口径 D08）。
    """
    kb = load_kb(data_dir)
    if kb.has_problems():
        return None, ("知识库存在 %d 项结构/引用问题，拒绝计算。先跑 `sdc selfcheck` 看明细。\n"
                      % len(kb.problems))
    return kb, ""


def run_card_command(data_dir: str, card: Any, module: Optional[str]):
    """已解析成对象的参数卡 → (Result 或 None, 退出码, 错误信息)。

    GUI 的表单与 CLI 的文件输入都汇到这一个函数：同一批异常映射、同一个退出码，
    界面上不可能算出与命令行不一样的结论（口径 D08）。
    """
    if isinstance(card, dict) and module and card.get("module") and module != card.get("module"):
        return None, EXIT_BAD_INPUT, ("--module=%s 与参数卡的 module=%s 不一致\n"
                                      % (module, card.get("module")))
    if isinstance(card, dict) and module and not card.get("module"):
        card = dict(card)
        card["module"] = module

    kb, error = load_kb_or_error(data_dir)
    if kb is None:
        return None, EXIT_BAD_INPUT, error

    try:
        result = run_case(kb, card)
    except InputError as exc:
        return None, EXIT_BAD_INPUT, "参数卡不可用：%s\n" % exc
    except (EngineError, ExprError) as exc:
        return None, EXIT_DEGRADED, ("计算未完成（数据不自洽）：%s\n免责声明：%s\n"
                                     % (exc, DISCLAIMER))
    return result, result_exit_code(result), ""


def run_case_command(data_dir: str, case_path: str, module: Optional[str]):
    """参数卡文件 → (Result 或 None, 退出码, 错误信息)，`run` 与 `report` 与 GUI 共用。"""
    try:
        with open(case_path, "r", encoding="utf-8") as handle:
            card = json.loads(handle.read())
    except OSError as exc:
        return None, EXIT_BAD_INPUT, "参数卡读取失败：%s\n" % exc
    except ValueError as exc:
        return None, EXIT_BAD_INPUT, "参数卡不是合法 JSON：%s（%s）\n" % (case_path, exc)
    return run_card_command(data_dir, card, module)


def check_command(data_dir: str, ir_path: str):
    """IR → 核查报告（判定层不读文档，口径 K26）。"""
    kb, error = load_kb_or_error(data_dir)
    if kb is None:
        return None, EXIT_BAD_INPUT, error
    try:
        ir = load_ir(ir_path)
        report = run_rules(kb, ir)
    except (IrError, RuleError) as exc:
        return None, EXIT_BAD_INPUT, "核查未完成：%s\n" % exc
    code = EXIT_OK if report["conclusion"] == "pass" else EXIT_DEGRADED
    return report, code, ""


def checklist_command(data_dir: str, ir_path: Optional[str],
                      answers_path: Optional[str]):
    """检查单报告；没接 IR 或章节未覆盖齐都算降级完成（口径 K29）。"""
    kb, error = load_kb_or_error(data_dir)
    if kb is None:
        return None, EXIT_BAD_INPUT, error
    ir = None
    if ir_path:
        try:
            ir = load_ir(ir_path)
        except IrError as exc:
            return None, EXIT_BAD_INPUT, "IR 不可用：%s\n" % exc
    answers = None
    if answers_path:
        try:
            with open(answers_path, "r", encoding="utf-8") as handle:
                answers = json.loads(handle.read())
        except OSError as exc:
            return None, EXIT_BAD_INPUT, "人工答复读取失败：%s\n" % exc
        except ValueError as exc:
            return None, EXIT_BAD_INPUT, "人工答复不是合法 JSON：%s（%s）\n" % (answers_path, exc)
        if not isinstance(answers, dict):
            return None, EXIT_BAD_INPUT, "人工答复需要 {条目 id: 判定} 对象\n"

    report = checklist_module.build_report(kb, ir, answers)
    degraded = (not report["ir_used"]) or bool(report["summary"]["chapters_missing"])
    return report, (EXIT_DEGRADED if degraded else EXIT_OK), ""


def bench_suite_command(data_dir: str, workdir: Optional[str], sweep_only: bool):
    """`bench --all` / `--sweep` 的报告；退出码按 K43 的口径分别取。"""
    kb, error = load_kb_or_error(data_dir)
    if kb is None:
        return None, EXIT_BAD_INPUT, error
    try:
        report = suite.build_report(kb, data_dir, workdir)
    except InputError as exc:
        return None, EXIT_BAD_INPUT, "套件输入不可用：%s\n" % exc
    code = suite.sweep_exit_code(report) if sweep_only else report["exit_code"]
    return report, code, ""


def export_command(paragraphs: list, out_path: str):
    """docx 落盘（自检不过就不写文件，口径 K40/K41）：交付物不可用记退出码 2。"""
    try:
        written = export_docx(paragraphs, out_path)
    except ReportError as exc:
        return None, EXIT_BAD_INPUT, "%s\n" % exc
    return written, EXIT_OK, ""


def bench_suite_command(data_dir: str, workdir: Optional[str], sweep_only: bool,
                        as_markdown: bool = False):
    """`bench --all` / `--sweep` 的报告 → (report 或 None, 退出码, 错误信息)。

    两者的确定性步骤都要把整批语料解析两遍，那一步走子进程（口径 K39/K45）；
    `--sweep` 的退出码只看确定性回归自己，`--all` 看整张指标表（口径 K43）。
    """
    kb, error = load_kb_or_error(data_dir)
    if kb is None:
        return None, EXIT_BAD_INPUT, error
    if as_markdown and sweep_only:
        return None, EXIT_BAD_INPUT, ("bench --sweep 没有指标表：--markdown 只对 --all 有意义\n")
    try:
        report = suite.build_report(kb, data_dir, workdir)
    except InputError as exc:
        return None, EXIT_BAD_INPUT, "套件输入不可用：%s\n" % exc
    code = suite.sweep_exit_code(report) if sweep_only else report["exit_code"]
    return report, code, ""


def _cmd_run(data_dir: str, case_path: str, module: Optional[str], as_json: bool) -> int:
    result, rc, error = run_case_command(data_dir, case_path, module)
    if result is None:
        _err(error)
        return rc
    if as_json:
        _emit(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
    else:
        from .engine.render import render_result
        _emit(render_result(result))
    return rc


def _cmd_report(data_dir: str, case_path: str, module: Optional[str], out_path: str) -> int:
    result, rc, error = run_case_command(data_dir, case_path, module)
    if result is None:
        _err(error)
        return rc
    written, export_rc, error = export_command(result_body(result, case_path), out_path)
    if written is None:
        _err(error)
        return export_rc
    _emit("验算书已导出：%s" % written)
    _emit("结论：%s；比值：%s；依据条款 %d 条；免责声明已强制写入。" % (
        result["conclusion"],
        "不出数值（blocked）" if result["conclusion"] == "blocked" else result["ratio"],
        len(result["basis"])))
    return rc


def _cmd_bench(data_dir: str, only_cases: bool, as_json: bool) -> int:
    kb, error = load_kb_or_error(data_dir)
    if kb is None:
        _err(error)
        return EXIT_BAD_INPUT
    report = bench_module.build_report(kb, only_cases=only_cases)
    if as_json:
        _emit(json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2))
    else:
        _emit(bench_module.render_text(report))
    return EXIT_OK if report["ok"] else EXIT_DEGRADED


def _cmd_bench_text(data_dir: str, kind: str, ir_dir: Optional[str],
                    as_json: bool) -> int:
    """`bench --parse` / `--audit`：只吃落盘 IR，本进程不做任何正则解析（口径 K26）。"""
    if not ir_dir:
        _err("--%s 需要 --ir-dir（先跑 `sdc parse --dir … --out-dir …`）\n" % kind)
        return EXIT_BAD_INPUT
    if kind == "parse":
        try:
            report = bench_module.run_parse_eval(data_dir, ir_dir)
        except InputError as exc:
            _err("评测输入不可用：%s\n" % exc)
            return EXIT_BAD_INPUT
        _emit(json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2) if as_json
              else bench_module.render_parse(report))
        return EXIT_OK if report["ok"] else EXIT_DEGRADED

    kb, error = load_kb_or_error(data_dir)
    if kb is None:
        _err(error)
        return EXIT_BAD_INPUT
    try:
        report = bench_module.run_audit_eval(kb, data_dir, ir_dir)
    except (InputError, IrError, RuleError) as exc:
        _err("评测输入不可用：%s\n" % exc)
        return EXIT_BAD_INPUT
    _emit(json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2) if as_json
          else bench_module.render_audit(report))
    return EXIT_OK if report["ok"] else EXIT_DEGRADED


def _cmd_bench_suite(data_dir: str, workdir: Optional[str], sweep_only: bool,
                     as_json: bool, as_markdown: bool = False) -> int:
    report, code, error = bench_suite_command(data_dir, workdir, sweep_only, as_markdown)
    if report is None:
        _err(error)
        return code
    if as_markdown:
        _emit(suite.metrics_markdown(report))
        return code
    if as_json:
        payload = dict(report)
        if sweep_only:
            payload = {"data_dir": report["data_dir"],
                       "data_fingerprint": report["data_fingerprint"],
                       "workdir": report["workdir"],
                       "determinism": report["detail"]["determinism"],
                       "exit_code": code, "ok": code == EXIT_OK}
        _emit(json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2))
    else:
        _emit(suite.render_text(report, sweep_only=sweep_only, exit_code=code))
    return code


# ---------------------------------------------------------------------------
# M3：解析 / 核查 / 检查单
# ---------------------------------------------------------------------------

def _ir_summary(ir: dict, module: Optional[str]) -> str:
    lines = ["文档：%s（%d 段，sha256=%s）" % (
        ir["doc"]["name"], ir["doc"]["paragraph_count"], ir["doc"]["sha256"][:12])]
    slots = ir["slots"]
    lines.append("抽到槽位 %d 个：%s" % (
        len(slots), ", ".join("%s=%s" % pair for pair in sorted(slots.items())) or "无"))
    if ir["conflicts"]:
        for conflict in ir["conflicts"]:
            lines.append("同槽位多值：%s → %s（段落 %s）" % (
                conflict["slot"], ", ".join(conflict["values"]),
                ", ".join(str(p) for p in conflict["paras"])))
    if ir["dropped"]:
        lines.append("白名单外丢弃 %d 处（留痕，不进参数卡）：" % len(ir["dropped"]))
        for item in ir["dropped"][:10]:
            lines.append("  - %s=%s（第 %s 段）：%s" % (
                item.get("slot"), item.get("value", item.get("candidate")),
                item.get("para", item.get("paras", "-")), item["reason"]))
        if len(ir["dropped"]) > 10:
            lines.append("  …（其余 %d 处见 IR）" % (len(ir["dropped"]) - 10))
    lines.append("参数卡槽位（可等值落进输入词表的部分）：%s" % (
        ", ".join("%s=%s" % pair for pair in sorted(ir["card_slots"].items())) or "无"))
    for line in card_gaps(ir, module):
        lines.append("距可运行参数卡：%s" % line)
    return "\n".join(lines)


def _cmd_parse(doc: Optional[str], doc_dir: Optional[str], out: Optional[str],
               ir_dir: Optional[str], module: Optional[str], as_json: bool) -> int:
    if bool(doc) == bool(doc_dir):
        _err("parse 需要 --doc 或 --dir 二者之一（单文档 / 批量）\n")
        return EXIT_BAD_INPUT

    if doc:
        targets = [doc]
    elif not os.path.isdir(doc_dir):
        _err("文档目录不存在：%s\n" % doc_dir)
        return EXIT_BAD_INPUT
    else:
        targets = sorted(
            os.path.join(doc_dir, name) for name in os.listdir(doc_dir)
            if os.path.splitext(name)[1].lower() in DOC_SUFFIXES)
        if not targets:
            _err("目录里没有可解析的文档（支持 %s）：%s\n" % (
                ", ".join(DOC_SUFFIXES), doc_dir))
            return EXIT_BAD_INPUT

    failures = 0
    for path in targets:
        try:
            ir = build_ir(path)
        except ParseError as exc:
            _err("%s：文档不可读：%s\n" % (path, exc))
            failures += 1
            continue
        if doc:
            target = out or default_ir_path(path)
        else:
            stem = os.path.splitext(os.path.basename(path))[0]
            target = os.path.join(ir_dir or ".tmp_parse", "%s.ir.json" % stem)
        written = write_ir(ir, target)
        if as_json:
            _emit(json.dumps(ir, sort_keys=True, ensure_ascii=False, indent=2))
        elif doc:
            _emit(_ir_summary(ir, module))
            _emit("IR 已写入：%s" % written)
        else:
            # 批量模式只给一行摘要：24 份语料 × 全文摘要会把有用信息埋掉
            _emit("%-12s 段落 %2d 槽位 %2d 冲突 %d 丢弃 %d → %s" % (
                ir["doc"]["name"], ir["doc"]["paragraph_count"], len(ir["slots"]),
                len(ir["conflicts"]), len(ir["dropped"]) + len(ir["card_dropped"]), written))
    return EXIT_OK if failures == 0 else (EXIT_BAD_INPUT if failures == len(targets)
                                          else EXIT_DEGRADED)


def _emit_export(paragraphs: list, out_path: Optional[str]) -> int:
    """把 docx 导出接进 `check`/`checklist`：导出失败＝交付物不可用（rc=2），文本仍照常打印。"""
    if not out_path:
        return EXIT_OK
    written, code, error = export_command(paragraphs, out_path)
    if written is None:
        _err(error)
        return code
    _emit("docx 已导出：%s" % written)
    return code


def _cmd_check(data_dir: str, ir_path: str, as_json: bool,
               out_path: Optional[str] = None) -> int:
    report, code, error = check_command(data_dir, ir_path)
    if report is None:
        _err(error)
        return code

    _emit(json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2) if as_json
          else render_report(report))
    return max(code, _emit_export(check_body(report), out_path))


def _cmd_checklist(data_dir: str, ir_path: Optional[str],
                   answers_path: Optional[str], as_json: bool,
                   out_path: Optional[str] = None) -> int:
    report, code, error = checklist_command(data_dir, ir_path, answers_path)
    if report is None:
        _err(error)
        return code

    _emit(json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2) if as_json
          else checklist_module.render_text(report))
    return max(code, _emit_export(checklist_body(report, ir_path or ""), out_path))


def _cmd_gui(data_dir: str, screenshot: Optional[str]) -> int:
    """启动桌面界面（M5）。PySide6 缺席时说明装法并按「输入不可用」退出（口径 K9）。

    界面层是惰性导入的：`sdc` 的其它命令与 CLI exe 都不需要 PySide6。
    """
    try:
        from . import gui
    except ImportError as exc:
        _err("桌面界面不可用：%s\n安装 extras：pip install sdc[gui]"
                         "（Python 3.8 上实测可解析的最高版本是 PySide6 6.6.3.1）\n" % exc)
        return EXIT_BAD_INPUT
    if screenshot:
        return gui.capture(data_dir, screenshot)
    return gui.run(data_dir)


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return EXIT_BAD_INPUT

    try:
        data_dir = find_data_dir(args.data_dir)
    except DataDirNotFound as exc:
        _err("%s\n" % exc)
        return EXIT_BAD_INPUT

    if not os.path.isdir(os.path.join(data_dir, "clauses")):
        _err("数据目录不可用：%s（缺少 clauses/）\n" % data_dir)
        return EXIT_BAD_INPUT

    if args.command == "selfcheck":
        return _cmd_selfcheck(data_dir, args.as_json)
    if args.command == "synth":
        return _cmd_synth(data_dir, args.seed, args.check)
    if args.command == "run":
        return _cmd_run(data_dir, args.case, args.module, args.as_json)
    if args.command == "bench":
        chosen = [name for name, on in (
            ("cases", args.only_cases), ("parse", args.bench_parse),
            ("audit", args.bench_audit), ("sweep", args.bench_sweep),
            ("all", args.bench_all)) if on]
        if len(chosen) > 1:
            _err("bench：一次只能选一种基准，同时给了 %s\n"
                             % "、".join("--" + name for name in chosen))
            return EXIT_BAD_INPUT
        if chosen in (["sweep"], ["all"]):
            # 这两条自己把整批语料解析两遍（确定性回归的定义就在这里），所以不吃现成 IR
            if args.ir_dir:
                _err("bench --%s 不接受 --ir-dir：它自己跑两遍解析做字节比对，"
                                 "复用现成 IR 请用 --parse/--audit\n" % chosen[0])
                return EXIT_BAD_INPUT
            return _cmd_bench_suite(data_dir, args.workdir, chosen[0] == "sweep",
                                    args.as_json, args.as_markdown)
        if chosen in (["parse"], ["audit"]):
            return _cmd_bench_text(data_dir, chosen[0], args.ir_dir, args.as_json)
        if args.ir_dir or args.workdir:
            _err("bench：--ir-dir/--workdir 只对 --parse/--audit/--sweep/--all 有意义\n")
            return EXIT_BAD_INPUT
        return _cmd_bench(data_dir, args.only_cases, args.as_json)
    if args.command == "parse":
        return _cmd_parse(args.doc, args.doc_dir, args.out, args.ir_dir, args.module,
                          args.as_json)
    if args.command == "check":
        return _cmd_check(data_dir, args.ir, args.as_json, args.out_path)
    if args.command == "checklist":
        return _cmd_checklist(data_dir, args.ir_path, args.answers, args.as_json,
                              args.out_path)
    if args.command == "report":
        return _cmd_report(data_dir, args.case, args.module, args.out_path)
    if args.command == "gui":
        return _cmd_gui(data_dir, args.screenshot)

    _err("未知命令：%s\n" % args.command)
    return EXIT_BAD_INPUT


if __name__ == "__main__":
    sys.exit(main())
