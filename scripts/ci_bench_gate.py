"""CI 门禁：读 `sdc bench --all --json` 的指标表，判红/绿——但不把「不可判」说成达标。

口径 K43 的四态里，CI 只为「未达标」和「不可用」红；「不可判」是诚实的分母 0。
本轮已知的不可判就那两项，名单写死在这里是故意的：冒出第三个说明有人改了数据却没登记，
CI 应该红一次，而不是默默放行。退出码与状态的一致性也在这里对账（`bench` 自己按 K43 取码）。

用法：`python scripts/ci_bench_gate.py bench.json <bench 的退出码>`
"""

import json
import sys

STATUS_LABEL = {"pass": "达标", "fail": "未达标",
                "unmeasurable": "不可判", "unavailable": "不可用"}
# 允许保持「不可判」的指标（解除通道见 data/cases/README.md 与 plan/06 的核对队列）
KNOWN_UNMEASURABLE = ("算例通过率", "可硬判 abnormal 的规则分母")


def gate(report, bench_rc):
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

    expected = _expected_rc(rows)
    if bench_rc != expected:
        problems.append("退出码与指标表不一致：bench 返回 %s，按 K43 应为 %s" % (bench_rc, expected))
    return lines, problems


def _expected_rc(rows):
    """复刻 suite._exit_code 的口径 K43，用来对账而不是照抄它的结论。"""
    if any(row.get("status") == "unavailable" for row in rows):
        return 2
    if rows and all(row.get("status") == "pass" for row in rows):
        return 0
    return 1


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("用法：ci_bench_gate.py <bench.json 或 '-'> <bench 退出码>\n")
        return 2
    try:
        if argv[1] == "-":
            # CI 里从管道读：落地 scratch 文件会被仓库自己的 EOL 守门测试拦下
            # （Windows runner 的重定向写 CRLF，而 CI 首跑就是被这条抓住的）
            report = json.loads(sys.stdin.read())
        else:
            with open(argv[1], "r", encoding="utf-8") as handle:
                report = json.load(handle)
    except (OSError, ValueError) as exc:
        sys.stderr.write("读不到基准 JSON：%s\n" % exc)
        return 2
    try:
        bench_rc = int(argv[2])
    except ValueError:
        sys.stderr.write("退出码不是整数：%s\n" % argv[2])
        return 2

    lines, problems = gate(report, bench_rc)
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
