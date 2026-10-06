"""CLI 命令面（plan/03 §五）。退出码 0 完成 / 1 降级完成 / 2 输入不可用（口径 K9）。"""

import argparse
import json
import os
import sys

from . import __version__
from .paths import DataDirNotFound, find_data_dir
from .selfcheck import build_report, render_text
from .synth.generator import DEFAULT_SEED, compare_corpus, generate_corpus

EXIT_OK = 0
EXIT_DEGRADED = 1
EXIT_BAD_INPUT = 2


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
    return parser


def _emit(text: str) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass  # stdout 被替换成不支持 reconfigure 的对象（测试捕获时）
    print(text)


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


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return EXIT_BAD_INPUT

    try:
        data_dir = find_data_dir(args.data_dir)
    except DataDirNotFound as exc:
        sys.stderr.write("%s\n" % exc)
        return EXIT_BAD_INPUT

    if not os.path.isdir(os.path.join(data_dir, "clauses")):
        sys.stderr.write("数据目录不可用：%s（缺少 clauses/）\n" % data_dir)
        return EXIT_BAD_INPUT

    if args.command == "selfcheck":
        return _cmd_selfcheck(data_dir, args.as_json)
    if args.command == "synth":
        return _cmd_synth(data_dir, args.seed, args.check)

    sys.stderr.write("未知命令：%s\n" % args.command)
    return EXIT_BAD_INPUT


if __name__ == "__main__":
    sys.exit(main())
