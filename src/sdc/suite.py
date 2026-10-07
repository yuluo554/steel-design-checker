"""一键基准（M4）：算例通过率 / 确定性回归 / 解析 F1 / 核查检出率与误报 → 一张指标表。

门槛来自 plan/05 §六，实测值由本模块产出、README 直接引用（`tests/test_suite.py` 逐行对账，
抄错的数字会被测试拦住）。指标行的状态四值：

- `pass` 达标；`fail` 未达标；
- `unmeasurable` 分母为 0 这类"这条指标现在量不了"——它是诚实结果，**不是通过**
  （真值算例 0 例时通过率就是这么显示的，口径 K43）；
- `unavailable` 前置条件不可用（子进程起不来、数据有结构问题），退出码 2。

确定性回归里"整批 IR 两次字节一致"必须把语料解析两遍，而解析层是本机 `sre_parse` 的已知
崩溃点，所以这一步**另起子进程**执行 `sdc parse`（口径 K39）：套件进程自己不定义、不编译、
不执行项目正则，子进程失败只让对应指标记 `unavailable`，不打挂整套基准。落盘的 IR 才是
判定层与评测之间唯一的交接物（K26）。
"""

import hashlib
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import __version__, bench
from .engine.core import DISCLAIMER, run_case
from .engine.errors import EngineError, ExprError, InputError
from .kb.fingerprint import data_fingerprint
from .kb.gate import all_module_gates
from .report import (check_body, checklist_body, docx_bytes, find_external_refs,
                     result_body)
from .rules import run_rules
from .synth.generator import DEFAULT_SEED, compare_corpus

RC_OK = 0
RC_DEGRADED = 1
RC_BAD_INPUT = 2

# F1 与检出率的门槛沿用 bench 的常量，两处各写一个 0.95 早晚会漂移
PARSE_GATE = bench.PARSE_F1_GATE
DETECTION_GATE = bench.DETECTION_GATE
SUBCOMMAND_TIMEOUT = 180

STATUS_LABEL = {"pass": "达标", "fail": "未达标",
                "unmeasurable": "不可判", "unavailable": "不可用"}
STATUS_ORDER = ("pass", "unmeasurable", "fail", "unavailable")
COLUMNS = ("指标", "门槛", "实测", "结论", "来源命令")
DEFAULT_WORKDIR = os.path.join(".tmp_parse", "suite")


def _row(name: str, gate: str, measured: str, status: str, source: str,
         definition: str = "") -> Dict[str, Any]:
    return {"name": name, "gate": gate, "measured": measured, "status": status,
            "source": source, "definition": definition}


# ---------------------------------------------------------------------------
# 子进程通路（口径 K39）
# ---------------------------------------------------------------------------

def _src_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_cli(args: Sequence[str], data_dir: str,
            timeout: int = SUBCOMMAND_TIMEOUT) -> Tuple[Optional[int], str]:
    """在独立进程里跑一条 `sdc` 子命令，返回 (退出码, 合并输出)；起不来时退出码为 None。

    `--data-dir` 一律显式传给子进程：套件的工作目录是 `src/`，让子进程靠
    `find_data_dir` 的 CWD 上溯去猜数据目录，夹具与仓库数据就会各认一处。
    """
    src = _src_dir()
    env = dict(os.environ)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = "%s%s%s" % (src, os.pathsep, existing) if existing else src
    env["PYTHONIOENCODING"] = "utf-8"
    argv = [sys.executable, "-X", "utf8", "-m", "sdc",
            "--data-dir", os.path.abspath(data_dir)] + list(args)
    try:
        proc = subprocess.run(argv, cwd=src, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, "子进程不可用：sdc %s —— %s（确定性回归的解析步骤无法执行，口径 K39）" % (
            " ".join(args[:1]), exc)
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


# ---------------------------------------------------------------------------
# 确定性回归：整批 IR 两次、报告两次、交付物两次、合成语料位级一致
# ---------------------------------------------------------------------------

def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _dir_digest(directory: str) -> Dict[str, str]:
    """{文件名: sha256}；只按文件名对齐——两次解析的输出目录本就不同，路径不该进比对。"""
    if not os.path.isdir(directory):
        return {}
    out = {}  # type: Dict[str, str]
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        if os.path.isfile(path):
            with open(path, "rb") as handle:
                out[name] = _sha(handle.read())
    return out


def _reset_ir_dir(directory: str) -> None:
    """清掉本套件工作目录里的旧 IR。

    上一轮留下的 `*.ir.json` 会让"这一轮解析失败了"看起来像成功：字节比对读的是目录，
    不是解析器的退出码。只删套件自己写的 `*.ir.json`，不递归、不碰别的文件。
    """
    if not os.path.isdir(directory):
        os.makedirs(directory, exist_ok=True)
        return
    for name in sorted(os.listdir(directory)):
        if name.endswith(".ir.json"):
            os.remove(os.path.join(directory, name))


def diff_digests(digest_a: Dict[str, str], digest_b: Dict[str, str]) -> List[str]:
    """两份 {文件名: sha256} 的差异清单；两侧都空 = 没差异（调用方另外判"没产出"）。"""
    return sorted(
        ["%s 只在一侧产出" % name for name in set(digest_a) ^ set(digest_b)] +
        ["%s 两次字节不一致" % name for name in sorted(set(digest_a) & set(digest_b))
         if digest_a[name] != digest_b[name]])


def parse_corpus_twice(data_dir: str, workdir: str) -> Dict[str, Any]:
    """整批语料解析两遍（两个独立进程），逐文件比字节。"""
    doc_dir = os.path.join(data_dir, "synth", "docx")
    dirs = dict((tag, os.path.join(workdir, tag)) for tag in ("ir-a", "ir-b"))
    for out_dir in dirs.values():
        _reset_ir_dir(out_dir)
    codes = {}
    for tag, out_dir in sorted(dirs.items()):
        rc, output = run_cli(["parse", "--dir", doc_dir, "--out-dir", out_dir], data_dir)
        codes[tag] = (rc, output)
    if any(rc is None for rc, _out in codes.values()):
        return {"status": "unavailable", "files": 0, "diffs": [],
                "note": codes["ir-a"][1] if codes["ir-a"][0] is None else codes["ir-b"][1],
                "ir_dir": ""}
    rc_a, rc_b = codes["ir-a"][0], codes["ir-b"][0]
    if rc_a != rc_b:
        return {"status": "unavailable", "files": 0, "diffs": [],
                "note": "两次解析退出码不同：%s / %s" % (rc_a, rc_b), "ir_dir": ""}

    digest_a = _dir_digest(dirs["ir-a"])
    digest_b = _dir_digest(dirs["ir-b"])
    diffs = diff_digests(digest_a, digest_b)
    if not digest_a:
        return {"status": "unavailable", "files": 0, "diffs": [],
                "note": "两次解析都没有产出 IR", "ir_dir": ""}
    return {"status": "fail" if diffs else "pass", "files": len(digest_a),
            "diffs": diffs, "note": "", "ir_dir": dirs["ir-a"]}


def reports_twice(data_dir: str, ir_dir: str) -> Dict[str, Any]:
    """核查报告与检查单各跑两遍（独立进程），比 stdout 字节。"""
    sample = _first_ir(ir_dir)
    if not sample:
        return {"status": "unavailable", "checks": [], "note": "IR 目录里没有 .ir.json"}
    checks = []  # type: List[Dict[str, Any]]
    for argv in (["check", "--ir", sample, "--json"],
                 ["checklist", "--ir", sample, "--json"]):
        first_rc, first = run_cli(argv, data_dir)
        second_rc, second = run_cli(argv, data_dir)
        name = "sdc %s" % argv[0]
        if first_rc is None:
            checks.append({"name": name, "ok": False, "note": first})
            continue
        same = first_rc == second_rc and first == second
        checks.append({"name": name, "ok": same,
                       "note": "" if same else "两次输出或退出码不同（%s / %s）" % (
                           first_rc, second_rc)})
    bad = [item for item in checks if not item["ok"]]
    return {"status": "fail" if bad else "pass",
            "note": "；".join("%s：%s" % (item["name"], item["note"]) for item in bad),
            "checks": checks}


def exports_twice(kb, data_dir: str, ir_dir: str) -> Dict[str, Any]:
    """三类交付物各渲染两遍比字节，并顺手做 0 外链扫描。

    这一步留在本进程内跑：报告层不对文档执行正则（K26/K39），没有什么需要隔离的崩溃点，
    而它要的 IR 已经落盘。
    """
    sample = _first_ir(ir_dir)
    if not sample:
        return {"status": "unavailable", "items": [], "note": "IR 目录里没有 .ir.json"}
    from .parse.ir import load_ir
    ir = load_ir(sample)

    from . import checklist as checklist_module
    sets = {
        "核查清单": check_body(run_rules(kb, ir)),
        "检查单": checklist_body(checklist_module.build_report(kb, ir), sample),
    }
    card_path = _first_example(data_dir)
    if card_path:
        with open(card_path, "r", encoding="utf-8") as handle:
            card = json.loads(handle.read())
        sets["验算书"] = result_body(run_case(kb, card),
                                    os.path.relpath(card_path, data_dir))
    items = []  # type: List[Dict[str, Any]]
    for name, body in sorted(sets.items()):
        payload = docx_bytes(body)
        violations = find_external_refs(payload)
        items.append({"name": name, "stable": payload == docx_bytes(body),
                      "link_violations": violations, "bytes": len(payload),
                      "sha256": _sha(payload)})
    bad = [item for item in items if not item["stable"] or item["link_violations"]]
    return {"status": "fail" if bad else "pass",
            "note": "；".join("%s：%s" % (item["name"],
                                          item["link_violations"] or "两次导出不一致")
                              for item in bad),
            "cards_skipped": "" if card_path else "无 examples/*.json，验算书一栏未导出",
            "items": items}


def _first_example(data_dir: str) -> str:
    directory = os.path.join(data_dir, "examples")
    if not os.path.isdir(directory):
        return ""
    for name in sorted(os.listdir(directory)):
        if name.endswith(".json"):
            return os.path.join(directory, name)
    return ""


def _first_ir(ir_dir: str) -> str:
    if not os.path.isdir(ir_dir):
        return ""
    for name in sorted(os.listdir(ir_dir)):
        if name.endswith(".ir.json"):
            return os.path.join(ir_dir, name)
    return ""


# ---------------------------------------------------------------------------
# 待核对闸门：引用未核对数据却出了数值 = 0 例（硬门）
# ---------------------------------------------------------------------------

def count_leaks(kb, runs: Sequence[Tuple[str, Dict[str, Any]]]) -> List[str]:
    """runs = [(module, Result)]；返回"模块依赖未核对却产出了数值"的模块名。

    未核对与否用的是引擎自己的门控视图（`all_module_gates`），不另数一遍依赖，
    所以这条探针与 `sdc run` 的拒算条件是同一个事实源（口径 D08）。
    """
    unready = dict((gate["module"], gate["status"] != "ready")
                   for gate in all_module_gates(kb))
    leaks = []  # type: List[str]
    for module, result in runs:
        if not unready.get(module):
            continue
        if result.get("ratio") is not None or result.get("steps") or result.get("limits"):
            leaks.append(module)
    return sorted(set(leaks))


def gate_probe(kb, data_dir: str) -> Dict[str, Any]:
    """把 `data/examples/` 的每张演示参数卡跑一遍，看有没有数值从 blocked 通路漏出来。"""
    directory = os.path.join(data_dir, "examples")
    names = sorted(name for name in os.listdir(directory)
                   if name.endswith(".json")) if os.path.isdir(directory) else []
    runs = []  # type: List[Tuple[str, Dict[str, Any]]]
    rows = []  # type: List[Dict[str, Any]]
    errors = []  # type: List[str]
    for name in names:
        with open(os.path.join(directory, name), "r", encoding="utf-8") as handle:
            card = json.loads(handle.read())
        module = str(card.get("module", ""))
        try:
            result = run_case(kb, card)
        except InputError as exc:
            errors.append("%s 参数卡不可用：%s" % (name, exc))
            continue
        except (EngineError, ExprError) as exc:
            errors.append("%s 引擎失败：%s" % (name, exc))
            continue
        runs.append((module, result))
        rows.append({"card": name, "module": module, "conclusion": result["conclusion"],
                     "blocked_items": len(result["blocked"])})
    return {"cards": rows, "runs": len(runs), "leaks": count_leaks(kb, runs),
            "errors": errors, "blocked_modules": sorted(
                set(row["module"] for row in rows if row["conclusion"] == "blocked"))}


# ---------------------------------------------------------------------------
# 套件
# ---------------------------------------------------------------------------

def _eval_or_none(build, label: str, notes: List[str], enabled: bool):
    """跑一项文本侧评测；语料/IR 缺失只让对应指标行不可用，不打挂整套（口径 K43）。

    夹具数据目录（`tests/fixtures/kb`）没有 `synth/` 与语料，一键基准在它上面跑就是
    "算例通过率能量、文本侧三行不可用"——这是数据的真实形状，不是套件坏了。
    """
    if not enabled:
        return None
    try:
        return build()
    except InputError as exc:
        notes.append("%s 的前置数据不可用：%s" % (label, exc))
        return None


def build_report(kb, data_dir: str, workdir: Optional[str] = None) -> Dict[str, Any]:
    """四基准合一：指标表 + 明细。`--all` 与 `--sweep` 共用这一份构建。"""
    workdir = os.path.abspath(workdir or DEFAULT_WORKDIR)
    determinism = {}  # type: Dict[str, Any]

    cases = bench.run_cases(kb)
    determinism["engine"] = bench.run_selfcheck_samples(kb)
    determinism["corpus"] = compare_corpus(data_dir, DEFAULT_SEED)

    ir = parse_corpus_twice(data_dir, workdir)
    determinism["ir"] = ir
    eval_dir = ir.get("ir_dir") or ""
    if eval_dir:
        determinism["reports"] = reports_twice(data_dir, eval_dir)
        determinism["exports"] = exports_twice(kb, data_dir, eval_dir)
    else:
        determinism["reports"] = {"status": "unavailable", "checks": [],
                                  "note": "没有可复用的 IR"}
        determinism["exports"] = {"status": "unavailable", "items": [],
                                  "note": "没有可复用的 IR"}

    notes = []  # type: List[str]
    have_ir = bool(eval_dir)
    parse_eval = _eval_or_none(lambda: bench.run_parse_eval(data_dir, eval_dir),
                               "解析 F1", notes, have_ir)
    audit_eval = _eval_or_none(lambda: bench.run_audit_eval(kb, data_dir, eval_dir),
                               "核查检出率", notes, have_ir)
    gate = gate_probe(kb, data_dir)
    trace = _traceability(data_dir)

    metrics = _metrics(cases, determinism, parse_eval, audit_eval, gate, trace, notes)
    exit_code = _exit_code(metrics)
    return {
        "data_dir": os.path.abspath(data_dir),
        "data_fingerprint": data_fingerprint(data_dir),
        "engine_version": __version__,
        "ir_dir": eval_dir,
        "workdir": workdir,
        "metrics": metrics,
        "notes": notes,
        "exit_code": exit_code,
        "ok": exit_code == RC_OK,
        "detail": {
            "cases": cases,
            "determinism": determinism,
            "parse": _slim(parse_eval),
            "audit": _slim(audit_eval),
            "gate": gate,
            "traceability": trace,
        },
    }


def _traceability(data_dir: str) -> Dict[str, int]:
    """条款可溯源率的**数据侧**分母：复用 selfcheck 的同一套计数（口径 D08）。"""
    from .selfcheck import build_report as selfcheck_report
    return selfcheck_report(data_dir)["traceability"]


def _slim(report: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """指标表只要汇总数；逐文档 rows 留在 `bench --parse/--audit` 里看。"""
    if not report:
        return {}
    return dict((key, value) for key, value in sorted(report.items()) if key != "rows")


def _metrics(cases, determinism, parse_eval, audit_eval, gate, trace,
             notes) -> List[Dict[str, Any]]:
    rows = []  # type: List[Dict[str, Any]]

    def why(label: str) -> str:
        matched = [note for note in notes if note.startswith(label)]
        return "；".join(matched) if matched else "两步解析都没产出 IR（见确定性回归明细）"

    definition_cases = "容差内算例数 / 已核对真值算例数（分母只含 status=verified，口径 K6）"
    denominator = cases["denominator"]
    if not denominator:
        rows.append(_row("算例通过率", "100%", "分母 0，样本待补", "unmeasurable",
                         "sdc bench --cases", definition_cases))
    else:
        rows.append(_row("算例通过率", "100%", "%d / %d" % (cases["passed"], denominator),
                         "pass" if cases["passed"] == denominator else "fail",
                         "sdc bench --cases", definition_cases))

    engine_bad = [row for row in determinism["engine"] if row["status"] != "ok"]
    corpus_bad = determinism["corpus"] or []
    ir = determinism["ir"]
    unstable = [label for label, key in (("报告", "reports"), ("交付物", "exports"))
                if determinism.get(key, {}).get("status") == "fail"]
    det_status = ("unavailable" if ir.get("status") == "unavailable" else
                  "fail" if (engine_bad or corpus_bad or unstable or ir.get("diffs")) else
                  "pass")
    det_measured = ("%d 份 IR 两次一致" % ir.get("files", 0) if det_status == "pass" else
                    "IR %d 份，差异 %d 项；引擎异常 %d 项；语料差异 %d 项；不稳定 %s" % (
                        ir.get("files", 0), len(ir.get("diffs") or []), len(engine_bad),
                        len(corpus_bad), ", ".join(unstable) or "-"))
    rows.append(_row("确定性回归", "100%，违反即未达标", det_measured, det_status,
                     "sdc bench --sweep",
                     "同输入两次运行一致 + 整批 IR 与三类交付物两次字节一致（口径 K8/K39）"))

    if parse_eval is None:
        rows.append(_row("解析 F1", "≥ %.2f" % PARSE_GATE, "无 IR", "unavailable",
                         "sdc bench --parse", why("解析 F1")))
    else:
        f1 = parse_eval["f1"]
        totals = parse_eval["totals"]
        rows.append(_row("解析 F1", "≥ %.2f" % PARSE_GATE,
                         "n/a" if f1 is None else "%.4f" % f1,
                         "pass" if parse_eval["ok"] else "fail", "sdc bench --parse",
                         "TP %d / FP %d / FN %d，语料 %d 份参与对账" % (
                             totals["tp"], totals["fp"], totals["fn"],
                             parse_eval["doc_evaluated"])))

    if audit_eval is None:
        rows.append(_row("缺陷检出率", "≥ %.2f" % DETECTION_GATE, "无 IR", "unavailable",
                         "sdc bench --audit", why("核查检出率")))
        rows.append(_row("误报", "0（硬门）", "无 IR", "unavailable", "sdc bench --audit",
                         "非注入项被判非 pass 的处数"))
    else:
        rate = audit_eval["detection_rate"]
        rows.append(_row("缺陷检出率", "≥ %.2f" % DETECTION_GATE,
                         "n/a" if rate is None else "%.4f" % rate,
                         "pass" if rate is not None and rate >= DETECTION_GATE
                         and not audit_eval["missed"] else "fail", "sdc bench --audit",
                         "注入 %d 处，检出 %d 处；suspicious 同样计为检出（口径 K4）" % (
                             audit_eval["injection_total"], audit_eval["injection_detected"])))
        fp = audit_eval["false_positives"]
        rows.append(_row("误报", "0（硬门）", "%d 处" % len(fp),
                         "pass" if not fp else "fail", "sdc bench --audit",
                         "非注入项被判非 pass 的处数"))
        rows.append(_row("条款可溯源率", "100%", "%d / %d 条 finding 带条款" % (
            audit_eval["findings_with_clause"], audit_eval["findings_total"]),
            "pass" if audit_eval["findings_with_clause"] == audit_eval["findings_total"]
            else "fail", "sdc selfcheck",
            "输出侧：finding 挂 clause_id；数据侧渠道完整率 %d / %d" % (
                trace["checked_with_channel"], trace["checked_total"])))

    if not gate["runs"]:
        rows.append(_row("待核对闸门", "0 例（必须 blocked）", "无演示参数卡", "unavailable",
                         "sdc run / sdc selfcheck",
                         "数据目录没有 examples/*.json，闸门探针无从跑起"))
    else:
        rows.append(_row("待核对闸门", "0 例（必须 blocked）",
                         "%d 例漏出数值" % len(gate["leaks"]),
                         "pass" if not gate["leaks"] else "fail", "sdc run / sdc selfcheck",
                         "演示参数卡 %d 张跑过，blocked 模块 %d 个%s" % (
                             gate["runs"], len(gate["blocked_modules"]),
                             "；" + "；".join(gate["errors"]) if gate["errors"] else "")))

    export_items = determinism["exports"].get("items") or []
    violations = sum(len(item["link_violations"]) for item in export_items)
    if not export_items:
        rows.append(_row("0 外链", "0（硬门）", "未导出", "unavailable", "sdc report",
                         "%s；部件白名单 + 关系目标 + 正文地址扫描（口径 K40）" % (
                             determinism["exports"].get("note") or "")))
    else:
        rows.append(_row("0 外链", "0（硬门）", "%d 处（%d 份交付物）" % (
            violations, len(export_items)),
            "pass" if not violations else "fail",
            "sdc report / check --out / checklist --out",
            "部件白名单 + 关系目标 + 正文地址与绝对路径扫描（口径 K40）"))

    if audit_eval is not None:
        rows.append(_row("可硬判 abnormal 的规则分母", "—",
                         "%d 条规则" % audit_eval["hard_judge_denominator"], "unmeasurable",
                         "sdc bench --audit", audit_eval["hard_judge_note"]))
    return rows


def _exit_code(metrics: List[Dict[str, Any]]) -> int:
    """口径 K43：不可用 = 2；任一未达标或不可判 = 1；全达标 = 0。"""
    if any(row["status"] == "unavailable" for row in metrics):
        return RC_BAD_INPUT
    if all(row["status"] == "pass" for row in metrics):
        return RC_OK
    return RC_DEGRADED


def sweep_exit_code(report: Dict[str, Any]) -> int:
    """`--sweep` 只看确定性回归自己达标与否（指标表里其他行与它无关）。"""
    det = report["detail"]["determinism"]
    statuses = [det.get(key, {}).get("status") for key in ("ir", "reports", "exports")]
    if any(status == "unavailable" for status in statuses):
        return RC_BAD_INPUT
    if any(status == "fail" for status in statuses):
        return RC_DEGRADED
    if any(row["status"] != "ok" for row in det["engine"]) or det["corpus"]:
        return RC_DEGRADED
    return RC_OK


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def render_metrics(report: Dict[str, Any]) -> str:
    rows = report["metrics"]
    fields = ("name", "gate", "measured", "status")
    # 中文按两个西文字符宽排版；%-Ns 只数字符数，终端里会歪，所以这里显式按显示宽度补齐
    widths = [max(_display_width(COLUMNS[index]), *[_display_width(str(row[field]))
                                                    for row in rows])
              for index, field in enumerate(fields)]

    def line(values: Sequence[str]) -> str:
        cells = [_pad(value, widths[index]) for index, value in enumerate(values[:4])]
        return " ".join(cells) + " " + values[4]

    out = [line(list(COLUMNS))]
    for row in rows:
        out.append(line([row["name"], row["gate"], row["measured"],
                         STATUS_LABEL[row["status"]], row["source"]]))
    return "\n".join(out)


def _display_width(text: str) -> int:
    return sum(2 if ord(char) > 0x2E7F else 1 for char in str(text))


def _pad(text: str, width: int) -> str:
    return str(text) + " " * max(0, width - _display_width(text))


def render_determinism(det: Dict[str, Any]) -> str:
    out = []
    engine = det.get("engine") or []
    bad = [row for row in engine if row["status"] != "ok"]
    out.append("  引擎两次运行 + 单位不变性：%d 项，异常 %d 项" % (len(engine), len(bad)))
    for row in bad[:5]:
        out.append("    ！ %s：%s" % (row["case_id"], "；".join(row["details"])))

    corpus = det.get("corpus") or []
    out.append("  合成语料位级一致（seed=%d）：%s" % (
        DEFAULT_SEED, "一致" if not corpus else
        "差异 %d 项：%s" % (len(corpus), ", ".join(corpus[:5]))))

    ir = det.get("ir") or {}
    out.append("  整批 IR 两次字节一致：[%s] %d 份，差异 %d 项%s" % (
        STATUS_LABEL.get(ir.get("status", ""), ir.get("status", "")),
        ir.get("files", 0), len(ir.get("diffs") or []),
        "（%s）" % ir["note"] if ir.get("note") else ""))
    for name in (ir.get("diffs") or [])[:5]:
        out.append("    ！ %s" % name)

    for item in (det.get("reports") or {}).get("checks") or []:
        out.append("  %s 两次输出一致：[%s]%s" % (
            item["name"], "达标" if item["ok"] else "未达标",
            "（%s）" % item["note"] if item["note"] else ""))

    exports = det.get("exports") or {}
    for item in exports.get("items") or []:
        out.append("  %s docx：两次导出字节一致 %s，外链违规 %d 处（%d 字节，sha256=%s）" % (
            item["name"], "是" if item["stable"] else "否", len(item["link_violations"]),
            item["bytes"], item["sha256"][:12]))
    if exports.get("cards_skipped"):
        out.append("    · %s" % exports["cards_skipped"])
    if exports.get("note"):
        out.append("    ！ %s" % exports["note"])
    return "\n".join(out)


def render_text(report: Dict[str, Any], sweep_only: bool = False,
                exit_code: Optional[int] = None) -> str:
    out = ["=" * 72]
    out.append("sdc bench %s" % ("--sweep（确定性回归）" if sweep_only else
                                 "--all（四基准合一，门槛见 plan/05 §六）"))
    out.append("=" * 72)
    out.append("数据目录：%s" % report["data_dir"])
    out.append("data_fingerprint：%s" % report["data_fingerprint"])
    out.append("IR 目录：%s" % (report["ir_dir"] or "（无，解析步骤不可用）"))
    out.append("套件工作目录：%s" % report["workdir"])
    out.append("")

    if not sweep_only:
        out.append("[1] 指标表")
        out.append(render_metrics(report))
        for note in report.get("notes") or []:
            out.append("  ！ %s" % note)
        out.append("")

    out.append("[%s] 确定性回归明细" % ("1" if sweep_only else "2"))
    out.append(render_determinism(report["detail"]["determinism"]))

    if not sweep_only:
        out.append("")
        out.append("[3] 待核对闸门")
        gate = report["detail"]["gate"]
        out.append("  演示参数卡 %d 张跑过，漏出数值 %d 例" % (gate["runs"], len(gate["leaks"])))
        for row in gate["cards"]:
            out.append("    - %-34s %s → %s（拒算项 %d）" % (
                row["card"], row["module"], row["conclusion"], row["blocked_items"]))
        for line in gate["errors"]:
            out.append("    ！ %s" % line)

        out.append("")
        tally = {}  # type: Dict[str, int]
        for row in report["metrics"]:
            tally[row["status"]] = tally.get(row["status"], 0) + 1
        out.append("汇总：%s" % "，".join(
            "%s %d 项" % (STATUS_LABEL[key], tally[key])
            for key in STATUS_ORDER if key in tally))
        unmeasurable = [row["name"] for row in report["metrics"]
                        if row["status"] == "unmeasurable"]
        if unmeasurable:
            out.append("不可判的指标（是诚实的分母 0，不是通过）：%s" % "、".join(unmeasurable))

    code = report["exit_code"] if exit_code is None else exit_code
    out.append("")
    out.append("退出码：%d（口径 K43：全达标 0 / 有未达标或不可判 1 / 不可用 2）" % code)
    out.append("")
    out.append("免责声明：%s" % DISCLAIMER)
    return "\n".join(out)


def metrics_markdown(report: Dict[str, Any]) -> str:
    """给 README 用的指标表：不可判与未达标分开写，不把分母 0 说成通过（口径 K43）。"""
    out = ["| 指标 | 门槛 | 实测 | 结论 | 来源命令 |", "|---|---|---|---|---|"]
    for row in report["metrics"]:
        out.append("| %s | %s | %s | %s | `%s` |" % (
            row["name"], row["gate"], row["measured"], STATUS_LABEL[row["status"]],
            row["source"]))
    return "\n".join(out)
