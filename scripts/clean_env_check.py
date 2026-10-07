"""干净环境验证（M5 DoD：不在仓库树内跑，剥离 PATH 与 Python 变量）。

跑法：`py -3.8 -X utf8 scripts/clean_env_check.py`，前提是已经构建出 `dist/sdc-cli` 与
`dist/sdc-gui`。脚本把两个包**复制到 %TEMP% 下的中立目录**再跑，理由有两条：

1. CWD 上溯是 `find_data_dir` 的最后一个分支，在仓库树里跑会让它命中仓库 `data/`，
   "内嵌数据"就验了个寂寞；
2. 复制一次同时验了"包是可搬迁的"（不依赖构建机路径）。

退出码全部单独取（不接管道，管道吃退出码是本项目记过账的坑）。任一违反 exit 1。
"""

import argparse
import os
import shutil
import subprocess
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLES = ("sdc-cli", "sdc-gui")
TIMEOUT = 600


def neutral_root():
    base = os.path.join(os.environ.get("TEMP") or os.environ.get("TMP") or os.getcwd(),
                        "sdc-clean-env")
    if os.path.isdir(base):
        shutil.rmtree(base)
    os.makedirs(base)
    return base


def copy_bundles(dist_dir, target):
    for name in BUNDLES:
        source = os.path.join(dist_dir, name)
        if not os.path.isdir(source):
            raise SystemExit("缺少构建产物：%s（先跑 pyinstaller sdc.spec）" % source)
        shutil.copytree(source, os.path.join(target, name))
    return target


def stripped_env(target, workdir):
    """只留 Windows 自身必需的变量；PATH 里没有 Python，也没有 PYTHONPATH。"""
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    env = {
        "SystemRoot": system_root,
        "WINDIR": system_root,
        "COMSPEC": os.path.join(system_root, "System32", "cmd.exe"),
        "PATHEXT": ".COM;.EXE;.BAT;.CMD",
        "PATH": os.pathsep.join([os.path.join(system_root, "System32"),
                                 os.path.join(system_root, "System32", "WindowsPowerShell",
                                              "v1.0"),
                                 os.path.join(target, "sdc-cli")]),
        "TEMP": workdir,
        "TMP": workdir,
        "USERPROFILE": workdir,
        "APPDATA": workdir,
        "LOCALAPPDATA": workdir,
        "HOME": workdir,
        "PYTHONIOENCODING": "utf-8",
    }
    for optional in ("SYSTEMDRIVE", "HOMEDRIVE", "HOMEPATH"):
        if optional in os.environ:
            env[optional] = os.environ[optional]
    return env


def assert_no_python_on_path(env):
    for name in ("python.exe", "python3.exe", "py.exe"):
        found = shutil.which(name, path=env["PATH"])
        if found:
            return "PATH 里居然有 %s（%s）——剥离不彻底" % (name, found)
    for name in ("PYTHONPATH", "PYTHONHOME", "SDC_DATA_DIR", "SDC_CLI_EXE"):
        if name in env:
            return "环境变量没剥干净：%s" % name
    return ""


def run_exe(env, cwd, argv, label, problems, stats):
    proc = subprocess.run(argv, cwd=cwd, env=env, timeout=TIMEOUT,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    text = proc.stdout.decode("utf-8", "replace")
    stats.append((label, proc.returncode, text))
    return proc.returncode, text


def output_for(stats, label):
    for name, _code, text in stats:
        if name == label:
            return text
    return ""


def expect(problems, stats, label, code, rc, markers=(), forbidden=()):
    if code != rc:
        problems.append("%s 退出码 %s，期望 %s" % (label, code, rc))
    text = output_for(stats, label)
    for marker in markers:
        if marker not in text:
            problems.append("%s 输出里没有 %r" % (label, marker))
    for marker in forbidden:
        if marker in text:
            problems.append("%s 输出里出现了不该有的 %r" % (label, marker))


def gui_alive_probe(env, cwd, target, problems):
    exe = os.path.join(target, "sdc-gui", "sdc-gui.exe")
    proc = subprocess.Popen([exe], cwd=cwd, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    time.sleep(6.0)
    alive = proc.poll() is None
    if not alive:
        output = proc.stdout.read().decode("utf-8", "replace") if proc.stdout else ""
        problems.append("GUI 进程已退出（码 %s）：%s" % (proc.returncode, output[:400]))
    proc.terminate()
    try:
        proc.wait(20)
    except subprocess.TimeoutExpired:
        proc.kill()
    return alive


def check(desktop_dir=None):
    dist_dir = desktop_dir or os.path.join(REPO_ROOT, "dist")
    target = os.path.join(neutral_root(), "bundles")
    workdir = os.path.join(os.path.dirname(target), "work")
    os.makedirs(workdir)
    copy_bundles(dist_dir, target)
    env = stripped_env(target, workdir)
    cli = os.path.join(target, "sdc-cli", "sdc-cli.exe")
    gui = os.path.join(target, "sdc-gui", "sdc-gui.exe")

    problems = []
    stats = []
    leak = assert_no_python_on_path(env)
    if leak:
        problems.append(leak)

    data_dir = os.path.join(target, "sdc-cli", "_internal", "data")
    if not os.path.isdir(data_dir):
        problems.append("CLI 包里没有内嵌数据：%s" % data_dir)
    examples = os.path.join(data_dir, "examples")
    docx = os.path.join(data_dir, "synth", "docx")

    # 六连：selfcheck / run / parse→check / checklist / report / bench --all
    code, text = run_exe(env, workdir, [cli, "selfcheck"], "selfcheck", problems, stats)
    expect(problems, stats, "selfcheck", code, 0,
           markers=["sdc selfcheck", "data_fingerprint", "推进看板", "核对队列"])
    if "仓库根" in text or REPO_ROOT in text:
        problems.append("selfcheck 输出里出现仓库路径，说明数据不是内嵌的")

    card = os.path.join(examples, "A2-fillet-weld.json")
    code, _text = run_exe(env, workdir, [cli, "run", "--case", card], "run", problems, stats)
    expect(problems, stats, "run", code, 1, markers=["拒算依据", "不出数值（blocked）",
                                                     "免责声明"])

    ir_path = os.path.join(workdir, "SYNTH-0013.ir.json")
    code, _text = run_exe(env, workdir, [cli, "parse", "--doc",
                                        os.path.join(docx, "SYNTH-0013.docx"),
                                        "--out", ir_path], "parse", problems, stats)
    expect(problems, stats, "parse", code, 0, markers=["IR 已写入"])

    code, _text = run_exe(env, workdir, [cli, "check", "--ir", ir_path], "check",
                          problems, stats)
    expect(problems, stats, "check", code, 1, markers=["文档级结论", "免责声明"])

    code, _text = run_exe(env, workdir, [cli, "checklist", "--ir", ir_path], "checklist",
                          problems, stats)
    expect(problems, stats, "checklist", code, 0, markers=["条目 107", "免责声明"])

    report_path = os.path.join(workdir, "验算书.docx")
    code, _text = run_exe(env, workdir, [cli, "report", "--case", card,
                                        "--out", report_path], "report", problems, stats)
    expect(problems, stats, "report", code, 1, markers=["验算书已导出"])
    if not os.path.isfile(report_path):
        problems.append("report 没写出交付物")

    suite_dir = os.path.join(workdir, "suite")
    code, text = run_exe(env, workdir, [cli, "bench", "--all", "--workdir", suite_dir],
                         "bench", problems, stats)
    expect(problems, stats, "bench", code, 1,
           markers=["确定性回归", "达标", "不可判", "分母 0"])
    # §三.4 的核心：打包版的一键基准不许把确定性回归降级成「不可用」
    determinism = [line for line in text.splitlines() if "确定性回归" in line]
    if not determinism or "不可用" in determinism[0]:
        problems.append("打包版确定性回归行不正常：%s" % (determinism or ["（没有这一行）"]))
    if "[sdc-cli.exe]" in text or "子进程不可用" in text:
        problems.append("bench --all 的子进程通路没打通")

    # 数据目录分支：环境变量优先（仍指向内嵌数据）
    env_override = dict(env)
    env_override["SDC_DATA_DIR"] = os.path.join(target, "sdc-gui", "_internal", "data")
    code, text = run_exe(env_override, workdir, [cli, "selfcheck"], "selfcheck(env)",
                         problems, stats)
    expect(problems, stats, "selfcheck(env)", code, 0, markers=["数据目录"])
    if "sdc-gui" not in output_for(stats, "selfcheck(env)"):
        problems.append("SDC_DATA_DIR 没有被 CLI exe 采纳")

    # GUI 存活探针 + 内嵌数据存在
    if not os.path.isdir(os.path.join(target, "sdc-gui", "_internal", "data", "clauses")):
        problems.append("GUI 包里没有内嵌数据")
    if os.path.isfile(gui):
        alive = gui_alive_probe(env, workdir, target, problems)
        if alive:
            stats.append(("gui-alive", 0, "alive"))
    else:
        problems.append("缺少 sdc-gui.exe")

    # `sdc gui` 在 CLI exe 里没有 PySide6 ⇒ 必须老实说明，不能假装启动了
    code, text = run_exe(env, workdir, [cli, "gui"], "cli-gui", problems, stats)
    expect(problems, stats, "cli-gui", code, 2, markers=["桌面界面不可用"])

    print("中立目录：%s" % os.path.dirname(target))
    for label, code, _text in stats:
        print("  %-16s rc=%s" % (label, code))
    if problems:
        print("干净环境验证违反 %d 项：" % len(problems))
        for problem in problems:
            print("  ！ %s" % problem)
        return 1
    print("CLEAN_ENV_OK")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="clean_env_check")
    parser.add_argument("--dist", default=os.path.join(REPO_ROOT, "dist"))
    args = parser.parse_args(argv)
    return check(args.dist)


if __name__ == "__main__":
    sys.exit(main())
