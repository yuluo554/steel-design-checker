"""CI 门禁：读 `sdc bench --all --json` 的指标表，判红/绿——但不把「不可判」说成达标。

口径 K43 的四态里，CI 只为「未达标」和「不可用」红；「不可判」是诚实的分母 0。
本轮已知的不可判就那两项，名单写死在这里是故意的：冒出第三个说明有人改了数据却没登记，
CI 应该红一次，而不是默默放行。退出码与状态的一致性也在这里对账（`bench` 自己按 K43 取码）。

0.1.1 起 CI 用 `bench --all --allow-indeterminate`：带上它 `bench` 对"只有不可判"的指标表
返回 0（DEC2=A 的退出码粒度），所以 `_expected_rc` 必须知道本次带没带旗标，否则会把
合法的 0 判成"退出码不一致"。旗标只影响「不可判」这一档 —— 「未达标」与「不可用」
仍然一律红，这是本文件的核心断言（见 `_expected_rc` 与 tests/test_ci_workflow.py 的负控）。

用法：`python scripts/ci_bench_gate.py bench.json <bench 的退出码> [--allow-indeterminate]`
"""

import json
import sys

STATUS_LABEL = {"pass": "达标", "fail": "未达标",
                "unmeasurable": "不可判", "unavailable": "不可用"}
# 允许保持「不可判」的指标（解除通道见 data/cases/README.md 与 plan/06 的核对队列）
KNOWN_UNMEASURABLE = ("算例通过率", "可硬判 abnormal 的规则分母")


def gate(report, bench_rc, allow_indeterminate=False):
    """返回 (打印行, 违规行)：违规非空即 exit 1。"""
    lines = []
    problems = []
    rows = report.get("metrics") or []
    lines.append("指标表（data_fingerprint=%s…）" % report.get("data_fingerprint", "")[:12])
    for row in rows:
        status = row.get("status", "")
        label = STATUS_LABEL.get(status, status)
        lines.append("%-28s | 门槛 %-16s | %-10s | %s" %
                     (row.get("name", "?"), row.get("gate", ""), label, row.get("measured", "")))
        if status == "fail":
            problems.append("未达标：%s（%s）" % (row.get("name"), row.get("measured")))
        elif status == "unavailable":
            problems.append("不可用：%s（通路断了，不许当成达标）" % row.get("name"))
        elif status == "unmeasurable" and row.get("name") not in KNOWN_UNMEASURABLE:
            problems.append("新的不可判项未登记：%s" % row.get("name"))

    expected = _expected_rc(rows, allow_indeterminate)
    if bench_rc != expected:
        problems.append("退出码与指标表不一致：bench 返回 %s，按 K43%s 应为 %s" % (
            bench_rc, "（含 --allow-indeterminate）" if allow_indeterminate else "", expected))
    return lines, problems


def _expected_rc(rows, allow_indeterminate=False):
    """复刻 suite._exit_code 的口径 K43，用来对账而不是照抄它的结论。

    `allow_indeterminate` 只把 `unmeasurable` 从"非 0"里摘出来；`fail` 永远推成 1，
    `unavailable` 永远推成 2 —— 这三条不许被旗标连坐放行。
    """
    if any(row.get("status") == "unavailable" for row in rows):
        return 2
    if any(row.get("status") == "fail" for row in rows):
        return 1
    passing = ("pass", "unmeasurable") if allow_indeterminate else ("pass",)
    if rows and all(row.get("status") in passing for row in rows):
        return 0
    return 1


def main(argv):
    args = [a for a in argv[1:] if a != "--allow-indeterminate"]
    allow_indeterminate = len(args) != len(argv[1:])
    if len(args) != 2:
        sys.stderr.write("用法：ci_bench_gate.py <bench.json> <bench 退出码>"
                         " [--allow-indeterminate]\n")
        return 2
    try:
        with open(args[0], "r", encoding="utf-8") as handle:
            report = json.load(handle)
    except (OSError, ValueError) as exc:
        sys.stderr.write("读不到基准 JSON：%s\n" % exc)
        return 2
    try:
        bench_rc = int(args[1])
    except ValueError:
        sys.stderr.write("退出码不是整数：%s\n" % args[1])
        return 2

    lines, problems = gate(report, bench_rc, allow_indeterminate)
    for line in lines:
        sys.stdout.write(line + "\n")
    if problems:
        sys.stdout.write("\nCI 基准门禁不通过：\n")
        for problem in problems:
            sys.stdout.write("  - " + problem + "\n")
        return 1
    unmeasurable = [row["name"] for row in report.get("metrics", [])
                    if row.get("status") == "unmeasurable"]
    sys.stdout.write("\nBENCH_GATE_OK（未达标 0 / 不可用 0；不可判 %d 项如实留档：%s）\n" %
                     (len(unmeasurable), "、".join(unmeasurable) or "无"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
