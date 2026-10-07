"""构建后红线断言（plan/03 §七，口径 K46）。

跑法：`py -3.8 -X utf8 scripts/verify_dist.py [dist 目录]`，默认 `dist/`。
任一违反即 exit 1，通过打印 `DIST_AUDIT_OK`。

四组断言：
1. **禁区成分**：取证缓存/计划文档/测试/源码目录/明令不引的第三方库不得出现在 dist 树里；
2. **内嵌数据逐份对账**：白名单里每个文件的 sha256 必须与仓库一致，且不许多出文件；
3. **两个包的依赖面**：PySide6 只许出现在 GUI 包里，CLI 包里必须没有（界面依赖不许漏进控制台包）；
4. **打包版子进程通路**：GUI 包旁边必须找得到 `sdc-cli.exe`（口径 K45，
   没有它，桌面版的确定性回归那一行只能显示「不可用」）。
"""

import argparse
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bundle_rules import (BUNDLES, CLI_EXE_NAME, DATA_SUBDIRS, FORBIDDEN_AT_ROOT,
                          FORBIDDEN_FILE_NAMES, FORBIDDEN_PACKAGES,
                          FORBIDDEN_ANYWHERE, GUI_ONLY_COMPONENTS)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def bundle_data_dir(bundle_dir):
    for candidate in (os.path.join(bundle_dir, "_internal", "data"),
                      os.path.join(bundle_dir, "data")):
        if os.path.isdir(candidate):
            return candidate
    return ""


def _dir_names_at_root(bundle_dir):
    roots = [bundle_dir]
    internal = os.path.join(bundle_dir, "_internal")
    if os.path.isdir(internal):
        roots.append(internal)
    out = set()
    for root in roots:
        for name in os.listdir(root):
            out.add(name)
    return out


def scan_forbidden(bundle_dir):
    """返回 (违反清单, 扫描文件数)。"""
    problems = []
    scanned = 0
    root_names = _dir_names_at_root(bundle_dir)
    for name in sorted(root_names & set(FORBIDDEN_AT_ROOT + FORBIDDEN_PACKAGES)):
        problems.append("包根/_internal 根出现禁区目录 %s" % name)
    for current, dirnames, filenames in os.walk(bundle_dir):
        dirnames.sort()
        for dirname in dirnames:
            if dirname in FORBIDDEN_ANYWHERE:
                problems.append("树内出现禁区目录 %s（%s）" % (
                    dirname, os.path.relpath(os.path.join(current, dirname), bundle_dir)))
        for filename in sorted(filenames):
            scanned += 1
            if filename in FORBIDDEN_FILE_NAMES:
                problems.append("树内出现禁区文件 %s（%s）" % (
                    filename, os.path.relpath(os.path.join(current, filename), bundle_dir)))
    return problems, scanned


def _rel_files(root):
    """目录树里的 {相对路径: 绝对路径}；`data/synth/docx/` 这类子目录必须一起对账。"""
    out = {}
    for current, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for filename in sorted(filenames):
            path = os.path.join(current, filename)
            out[os.path.relpath(path, root).replace("\\", "/")] = path
    return out


def reconcile_data(bundle_name, embedded, repo_data_dir):
    """内嵌数据与仓库逐份对账：缺文件、多文件、字节不一致都算违反。"""
    problems = []
    checked = 0
    if not embedded:
        return ["%s 包里没有内嵌 data 目录" % bundle_name], checked
    for subdir in DATA_SUBDIRS:
        repo_dir = os.path.join(repo_data_dir, subdir)
        target = os.path.join(embedded, subdir)
        if not os.path.isdir(repo_dir):
            problems.append("仓库侧白名单目录缺失：%s" % subdir)
            continue
        if not os.path.isdir(target):
            problems.append("%s/%s 整目录未入包" % (bundle_name, subdir))
            continue
        repo_files = _rel_files(repo_dir)
        packed_files = _rel_files(target)
        for name in sorted(set(repo_files) - set(packed_files)):
            problems.append("%s/data/%s/%s 未入包" % (bundle_name, subdir, name))
        for name in sorted(set(packed_files) - set(repo_files)):
            problems.append("%s/data/%s/%s 是白名单外的多出文件" % (bundle_name, subdir, name))
        for name in sorted(set(repo_files) & set(packed_files)):
            checked += 1
            repo_sha = sha256(repo_files[name])
            packed_sha = sha256(packed_files[name])
            if repo_sha != packed_sha:
                problems.append("%s/data/%s/%s 与仓库字节不一致（%s… ≠ %s…）" % (
                    bundle_name, subdir, name, repo_sha[:12], packed_sha[:12]))
    return problems, checked


def check_dependency_face(bundle_name, bundle_dir):
    problems = []
    root_names = _dir_names_at_root(bundle_dir)
    leaked = sorted(root_names & set(GUI_ONLY_COMPONENTS))
    if bundle_name == "sdc-cli":
        if leaked:
            problems.append("sdc-cli 包里混进了界面依赖：%s" % ", ".join(leaked))
    else:
        if "PySide6" not in root_names:
            problems.append("sdc-gui 包里没有 PySide6，界面不可能起得来")
    return problems


def check_cli_channel(bundle_name, bundle_dir):
    """GUI 包必须能在同目录或邻接目录找到 CLI exe（口径 K45 的打包态通路）。"""
    if bundle_name != "sdc-gui":
        return []
    exe_dir = os.path.dirname(os.path.abspath(bundle_dir))
    candidates = [
        os.path.join(bundle_dir, CLI_EXE_NAME),
        os.path.join(exe_dir, "sdc-cli", CLI_EXE_NAME),
    ]
    if any(os.path.isfile(path) for path in candidates):
        return []
    return ["sdc-gui 找不到配套的 sdc-cli.exe（试过的路径：%s）；"
            "打包版的一键基准与页签②的解析通路只能显示「不可用」"
            % "、".join(candidates)]


def audit(dist_dir, repo_data_dir):
    """返回 (problems, 统计信息)。"""
    problems = []
    stats = []
    for name in sorted(BUNDLES):
        bundle_dir = os.path.join(dist_dir, name)
        if not os.path.isdir(bundle_dir):
            problems.append("缺少包目录：%s" % bundle_dir)
            continue
        exe = os.path.join(bundle_dir, BUNDLES[name]["exe"])
        if not os.path.isfile(exe):
            problems.append("缺少可执行文件：%s" % exe)
        found, scanned = scan_forbidden(bundle_dir)
        embedded = bundle_data_dir(bundle_dir)
        data_problems, checked = reconcile_data(name, embedded, repo_data_dir)
        face = check_dependency_face(name, bundle_dir)
        channel = check_cli_channel(name, bundle_dir)
        problems.extend(found + data_problems + face + channel)
        stats.append("%s：%d 个文件、内嵌数据 %d 份对账、禁区成分 %d 处" % (
            name, scanned, checked, len(found)))
    return problems, stats


def main(argv=None):
    parser = argparse.ArgumentParser(prog="verify_dist")
    parser.add_argument("--dist", default=os.path.join(REPO_ROOT, "dist"))
    parser.add_argument("--data", default=os.path.join(REPO_ROOT, "data"))
    args = parser.parse_args(argv)

    problems, stats = audit(args.dist, args.data)
    print("dist：%s" % args.dist)
    for line in stats:
        print("  · %s" % line)
    if problems:
        print("构建红线违反 %d 项：" % len(problems))
        for problem in problems:
            print("  ！ %s" % problem)
        return 1
    print("白名单目录：%s" % ", ".join(DATA_SUBDIRS))
    print("DIST_AUDIT_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
