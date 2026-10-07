"""发布前脱敏审计（M6）：把脱敏四步 + 构建产物本体扫描固化成可复跑的工具。

设计约束（都来自实测教训，别改回去）：
- **输出掩码化**：只打印 `位置 [类别] xN`，不回显命中文本。留档会引用输出，输出本身不能成为
  二次泄漏源；
- **模式与词面分离**：个人标记/姊妹词用片段拼接或 base64 存进本文件，否则扫描器源码自己会命中
  自己的扫描，且那个字面会永久留在 git 历史里；
- **命中分级**：密钥/手机号/身份证/个人邮箱/个人目录/禁区路径 = 硬门（exit 1）；
  其余盘符路径、系统目录、已公开姊妹词、渠道 URL = 复核项（打印但需人工判定后留档）；
- **GitHub 账号名与 example.com / noreply / github.com 属白名单**：clone URL 必含账号名，
  测试夹具的示例邮箱按惯例用保留域；
- 扫描模式**不要用 `/` 起始的字面值**（MSYS 会静默把参数改写成 Windows 路径 → 假 0 命中），
  所以每个类别都靠 selftest 的阳性对照兜底：合成夹具必须命中，干净夹具必须不命中。

用法：
    py -3.8 -X utf8 scripts/audit_release.py selftest
    py -3.8 -X utf8 scripts/audit_release.py tracked
    py -3.8 -X utf8 scripts/audit_release.py binary
    py -3.8 -X utf8 scripts/audit_release.py messages
    py -3.8 -X utf8 scripts/audit_release.py metadata
    py -3.8 -X utf8 scripts/audit_release.py history
    py -3.8 -X utf8 scripts/audit_release.py dist
    py -3.8 -X utf8 scripts/audit_release.py all
"""

import base64
import io
import json
import os
import re
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# 词面：片段拼接，本文件里不存在完整字面（否则历史扫描永远洗不干净）
# ---------------------------------------------------------------------------

def _m(*frags):
    return "".join(frags)


# 本机账户名与工作区目录名：出现在跟踪内容里就是个人标记（硬门）
PERSONAL_MARKS = (_m("AS", "US"), _m("Qor", "der"))
# GitHub 账号名不进扫描名单：它是发布固有的公开元数据（clone URL 必含），
# noreply 邮箱 `<id>+<login>@users.noreply.github.com` 里也带着它，按白名单处理。
# 姊妹仓库/领域词：base64 存放，明文不入仓。公开性已按 gh api 核实（06 D09 复核），
# 所以这些词是"复核项"而非硬门；将来有未公开的同类项目要发布时，先按脱敏纪律处理再改档。
SISTER_WORDS_B64 = (
    "Y29uc3RydWN0aW9uLWRyYXdpbmctcGxhbi1jaGVja2VyLCBmb29kLWxhYmVsLWNvbXBsaWFu"
    "Y2UtY2hlY2tlciwgaW52b2ljZS1sZWRnZXItY2hlY2tlciwgcmVzdW1lLXRhbGVudC1wb29s"
    "LCBtZWRpY2FsLXJlY29yZC1xdWFsaXR5LWNoZWNrZXIsIHBvd2VyLW9wZXJhdGlvbi10aWNr"
    "ZXQtY2hlY2tlciwgYmlkZGluZy1kb2N1bWVudC1jaGVja2VyLCBzdHJ1Y3R1cmFsLXN0cmVu"
    "Z3RoZW5pbmctY2hlY2tlcg=="
)

HARD, REVIEW = "HARD", "REVIEW"

# 邮箱：首字符字母数字 + 域名至少两段（宽松版会把 `git log -p` 的 diff 前缀 `+` 吞进本地部分）
EMAIL_RE = re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9][A-Za-z0-9._%+-]*"
                      r"@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
EMAIL_EXEMPT_DOMAINS = ("example.com", "example.org", "localhost")
EMAIL_EXEMPT_LOCALS = ("git",)          # git@github.com 是服务地址形态，不是个人邮箱
NOREPLY_RE = re.compile(r"^[0-9]+\+[A-Za-z0-9._-]+@users\.noreply\.github\.com$")

PATTERNS = (
    ("sk_key", re.compile(r"\bsk-[A-Za-z0-9]{16,}"), HARD, "上游密钥"),
    ("secret_assignment",
     re.compile(r"(?i)\b(?:api[ _-]?)?(?:key|token|secret|passwd|password)\b\s*[:=]\s*"
                r"[\"']?[A-Za-z0-9+/_=-]{16,}"), HARD, "密钥赋值"),
    ("phone_cn", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), HARD, "手机号"),
    ("id_card", re.compile(r"(?<![0-9A-Za-z])\d{17}[0-9Xx](?![0-9A-Za-z])"), HARD, "身份证号"),
    ("private_ip",
     re.compile(r"(?<![\d.])(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}"
                r"|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})(?![\d.])"), HARD, "内网 IP"),
    # 盘符路径：`(?<![A-Za-z0-9])` 是为了不把 https:// 之类的 URL scheme 当成盘符
    ("drive_path", re.compile(r"(?<![A-Za-z0-9])(?i:[a-z]):[\\/][^\s\"'`|<>]{2,}"), REVIEW,
     "盘符路径"),
)

FORBIDDEN_TRACKED_NAMES = re.compile(r"(?i)\.env(\.|\b)|\.key$|secret|token|_private[\\/]")
CHANNEL_URL_RE = re.compile(r"(?i)https?://[^\s\"'<>)\]]+")


# ---------------------------------------------------------------------------
# 命中收集
# ---------------------------------------------------------------------------

class Hits(object):
    def __init__(self):
        self.items = []

    def add(self, where, category, severity, count, note=""):
        self.items.append((where, category, severity, count, note))

    def hard(self):
        return [item for item in self.items if item[2] == HARD]

    def review(self):
        return [item for item in self.items if item[2] == REVIEW]

    def __bool__(self):
        return bool(self.items)


def _sister_words():
    payload = base64.b64decode(SISTER_WORDS_B64.replace(" ", "").replace("\n", ""))
    return [word.strip().lower() for word in payload.decode("utf-8").strip("[]").split(",")]


def _mark_alt():
    return "|".join(re.escape(m) for m in PERSONAL_MARKS)


_MARK_TEXT = re.compile(r"(?<![A-Za-z0-9])(?:" + _mark_alt() + r")(?![A-Za-z0-9])", re.IGNORECASE)
_HOME_MARK = re.compile(r"(?i)(?:[a-z]:[\\/]|[/\\])(?:Users|home)[\\/]+(?:" + _mark_alt() +
                        r")(?![A-Za-z0-9])")
# 字节路用同一套词边界口径（`mid<mark>` / `<mark>OS` 这类子串不算命中）
_MARK_BYTES = re.compile(
    (r"(?<![A-Za-z0-9])(?:" + _mark_alt() + r")(?![A-Za-z0-9])").encode("ascii"), re.IGNORECASE)


def scan_text(where, text, hits, ignore_email_exempt=True):
    """扫一段文本，命中按类别聚合。掩码化：只记次数，不记原文。"""
    lowered = text.lower()
    for category, pattern, severity, _note in PATTERNS:
        count = len(pattern.findall(text))
        if category == "drive_path":
            # 个人目录形态单独判：Users/home 下挂个人标记 = 硬门，其余盘符路径 = 复核项
            personal = len(_HOME_MARK.findall(text))
            if personal:
                hits.add(where, "personal_home", HARD, personal)
            count = max(count - personal, 0)
        if count > 0:
            hits.add(where, category, severity, count)
    marks = len(_MARK_TEXT.findall(text))
    if marks:
        hits.add(where, "personal_mark_text", HARD, marks)
    for word in _sister_words():
        count = lowered.count(word)
        if count:
            hits.add(where, "sister_word", REVIEW, count)
    email_count = 0
    for match in EMAIL_RE.finditer(text):
        value = match.group(0)
        domain = value.split("@", 1)[1].lower()
        local = value.split("@", 1)[0].lower()
        if ignore_email_exempt and (
                any(domain == d or domain.endswith("." + d) for d in EMAIL_EXEMPT_DOMAINS)
                or domain in ("github.com", "users.noreply.github.com")
                or local in EMAIL_EXEMPT_LOCALS
                or NOREPLY_RE.match(value)):
            continue
        email_count += 1
    if email_count:
        hits.add(where, "personal_email", HARD, email_count)
    return text


def scan_bytes(where, data, hits):
    """二进制/字节通路：只跑强标记（个人标记 + 姊妹词），不跑邮箱与内网 IP 正则。

    原因（简历人才库 M6 实录）：上游 LICENSE/SBOM 里的公共邮箱会刷屏，压缩流里也没有可靠的
    文本边界；字节路只负责"构建机路径与个人标记有没有跟进产物"这一件事。
    """
    hay = data.lower()
    marks = len(_MARK_BYTES.findall(data))
    if marks:
        hits.add(where, "personal_mark_bytes", HARD, marks)
    for word in _sister_words():
        count = hay.count(word.encode("utf-8"))
        if count:
            hits.add(where, "sister_word_bytes", REVIEW, count)


# ---------------------------------------------------------------------------
# git 侧
# ---------------------------------------------------------------------------

def _git(args, cwd=None):
    proc = subprocess.run(["git", "-c", "core.quotepath=false"] + args, cwd=cwd or ROOT,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode not in (0, 1):        # git grep 无命中返回 1
        sys.stderr.write(proc.stderr.decode("utf-8", "replace") + "\n")
        raise SystemExit("git %s 失败（rc=%d）" % (" ".join(args), proc.returncode))
    return proc.stdout.decode("utf-8", "replace")


def tracked_files(cwd=None):
    out = _git(["ls-files", "-z"], cwd=cwd)
    return [name for name in out.split("\0") if name]


def is_probably_binary(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".docx", ".png", ".jpg", ".gif", ".ico", ".pdf", ".exe", ".dll", ".pyd",
               ".zip", ".ttf", ".pyc"):
        return True
    with open(path, "rb") as handle:
        chunk = handle.read(4096)
    return b"\0" in chunk


# ---------------------------------------------------------------------------
# 各扫描模式
# ---------------------------------------------------------------------------

def mode_tracked(hits, cwd=None):
    root = cwd or ROOT
    names = tracked_files(cwd)
    text_files = binary_files = 0
    for name in names:
        if FORBIDDEN_TRACKED_NAMES.search(name):
            hits.add(name, "forbidden_path", HARD, 1)
            continue
        path = os.path.join(root, name)
        if not os.path.isfile(path):
            continue
        if is_probably_binary(path):
            binary_files += 1
            continue
        text_files += 1
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            scan_text(name, handle.read(), hits)
    return "文本 %d 份 / 二进制 %d 份（二进制走 binary 模式）" % (text_files, binary_files)


def mode_binary(hits, cwd=None):
    """跟踪的二进制单独扫：docx 要展开**全部 zip 条目**，含 docProps 与 header/footer。"""
    root = cwd or ROOT
    scanned = 0
    for name in tracked_files(cwd):
        path = os.path.join(root, name)
        if not os.path.isfile(path) or not is_probably_binary(path):
            continue
        scanned += 1
        if name.lower().endswith(".docx"):
            try:
                with zipfile.ZipFile(path) as archive:
                    for entry in archive.infolist():
                        if entry.is_dir():
                            continue
                        stamp = "%s!%s" % (name, entry.filename)
                        data = archive.read(entry)
                        scan_bytes(stamp, data, hits)
                        # docProps 是真实姓名重灾区，文本条目还要过一遍文本规则
                        if entry.filename.startswith("docProps") or \
                                entry.filename.endswith(".xml"):
                            scan_text(stamp, data.decode("utf-8", "replace"), hits)
            except zipfile.BadZipFile:
                hits.add(name, "docx_not_readable", HARD, 1)
        else:
            with open(path, "rb") as handle:
                scan_bytes(name, handle.read(), hits)
    return "展开 %d 份跟踪二进制" % scanned


def mode_messages(hits):
    # 只扫正文：%an/%ae 属于元数据面，由 metadata 模式负责（混在这里会让"提交信息干净"永远验不过）
    body = _git(["log", "--all", "--format=%B%n<MSG>"])
    scan_text("<commit messages>", body, hits)
    return "全历史提交信息 %d 条" % body.count("<MSG>")


def mode_metadata(hits):
    out = _git(["log", "--format=%ae%x09%ce", "--all"])
    addresses = sorted({value for line in out.splitlines() for value in line.split("\t") if value})
    bad = []
    for address in addresses:
        domain = address.split("@", 1)[-1].lower()
        if NOREPLY_RE.match(address):
            continue
        if domain in ("github.com", "users.noreply.github.com"):
            continue
        bad.append(address)
    if bad:
        # 掩码化：只报数量，字面由执行人在仓外核对（留档引用输出时不得复述，否则"全历史 0 命中"
        # 这一条永远验不过——发票台账 M6 的第二轮重写就是栽在这里）
        hits.add("<git metadata>", "personal_email", HARD, len(bad),
                 "非 noreply/非白名单提交邮箱，涉及 %d 个不同域名"
                 % len({a.split("@", 1)[-1].lower() for a in bad}))
    return "作者/提交者邮箱 %d 个不同值" % len(addresses)


def mode_history(hits):
    # --format=commit %H 去掉作者头，否则提交邮箱必被邮箱正则误报（发票台账 M6 实录）
    patch = _git(["log", "--all", "-p", "--format=commit %H", "--no-color"])
    scan_text("<full history patch>", patch, hits)
    return "补丁全文 %d 字符" % len(patch)


def mode_dist(hits, cwd=None):
    """构建产物本体扫描：仓库内容级扫描证明不了**冻结产物**干净。

    与 `scripts/verify_dist.py` 是双保险：那边管白名单与逐份 sha256 对账，这边管"构建机路径
    与个人标记有没有跟着 exe 走"。字节读法、不跑邮箱正则（上游 LICENSE/SBOM 会刷屏）。
    """
    root = cwd or ROOT
    dist = os.path.join(root, "dist")
    if not os.path.isdir(dist):
        return "dist/ 不存在：先跑 py -3.8 -m PyInstaller sdc.spec"
    sys.path.insert(0, os.path.join(root, "scripts"))
    import bundle_rules  # noqa: E402  与构建红线同一份禁区名单

    files = 0
    for walk_root, dirs, names in os.walk(dist):
        dirs[:] = sorted(dirs)
        rel = os.path.relpath(walk_root, dist)
        parts = set(rel.split(os.sep))
        for banned in bundle_rules.FORBIDDEN_ANYWHERE:
            if banned in parts:
                hits.add(rel, "dist_forbidden_dir", HARD, 1, "禁区目录成分")
        if rel in (".", ) or rel.count(os.sep) <= 1:
            # 包根与 _internal 根：verify_dist 的同一层口径
            entries = set(dirs) | set(names)
            for banned in bundle_rules.FORBIDDEN_AT_ROOT:
                if banned in entries:
                    hits.add(rel, "dist_forbidden_root", HARD, 1, "禁区根成分 " + banned)
        for name in names:
            rel_name = os.path.join(rel, name)
            files += 1
            if name in bundle_rules.FORBIDDEN_FILE_NAMES:
                hits.add(rel_name, "dist_forbidden_file", HARD, 1)
            with open(os.path.join(walk_root, name), "rb") as handle:
                scan_bytes(rel_name.replace(os.sep, "/"), handle.read(), hits)
    return "遍历 dist 树 %d 个文件（字节强标记 + 禁区成分）" % files


# ---------------------------------------------------------------------------
# selftest：阳性对照（夹具程序化合成，仓库里没有字面假密钥/假手机号）
# ---------------------------------------------------------------------------

def mode_selftest(hits):
    """阳性对照不是形式：food M6 的首轮 selftest 抓出了"合成手机号只有 10 位"的夹具 bug。"""
    mark = PERSONAL_MARKS[0]
    # 夹具里的样本一律**片段拼接**：完整字面写进本文件，本文件就会命中自己的扫描，
    # 而它会进 git 历史 ⇒ "全历史 0 命中"永远验不过（简历人才库 M6 的审计器自引用坑）
    cases = [
        ("sk_key", "KEY sk-" + "A" * 24, "sk_key"),
        ("secret_assignment", "api_token = " + "b3" * 12, "secret_assignment"),
        ("phone_cn", "联系 1" + "3" * 10 + " 一下", "phone_cn"),
        ("id_card", "编号 " + "1" * 17 + "X 结束", "id_card"),
        ("private_ip", "网关 " + _m("192.168.", "31.254"), "private_ip"),
        ("personal_home", "配置在 C:\\Users\\" + mark + "\\AppData", "personal_home"),
        ("personal_email", "作者 " + _m("someone99@gm", "ail.com") + " 邮箱", "personal_email"),
        ("drive_path", "输出到 D:\\some" + _m("where\\", "out.docx"), "drive_path"),
    ]
    failures = []
    for name, sample, expected in cases:
        probe = Hits()
        scan_text("selftest:" + name, sample, probe)
        found = {item[1] for item in probe.items}
        if expected not in found:
            failures.append("阳性对照未命中：%s（期望 %s，实得 %s）" % (name, expected, sorted(found)))
    clean = Hits()
    scan_text("selftest:clean",
              "见 C:\\Users\\<name>\\ 与 someone@example.com，"
              "长编号 2024011500000000000000、7 位 1380010 与 10 位 1380010010，"
              "以及 https://example.gov.cn/x.pdf 与 20 位十六进制 sha256 abcdef0123456789abcd",
              clean)
    for item in clean.items:
        if item[2] == HARD:
            failures.append("阴性对照被误报：%s" % item[1])
    if failures:
        for line in failures:
            hits.add("selftest", "audit_selfcheck", HARD, 1, line)
    return "阳性/阴性对照 %d 组" % (len(cases) + 1)


MODES = {
    "selftest": mode_selftest,
    "tracked": mode_tracked,
    "binary": mode_binary,
    "messages": mode_messages,
    "metadata": mode_metadata,
    "history": mode_history,
    "dist": mode_dist,
}
FULL_ORDER = ("selftest", "tracked", "binary", "messages", "metadata", "history", "dist")


def main(argv):
    mode = argv[1] if len(argv) > 1 else "all"
    if mode == "all":
        names = FULL_ORDER
    elif mode in MODES:
        names = [mode]
    else:
        sys.stderr.write(__doc__)
        return 2

    hits = Hits()
    for name in names:
        scope = MODES[name](hits)
        sys.stdout.write("[%s] %s\n" % (name, scope))

    for where, category, severity, count, note in hits.items:
        sys.stdout.write("%s %s [%s] x%d %s\n" %
                         (severity, where, category, count, ("— " + note) if note else ""))
    hard, review = hits.hard(), hits.review()
    sys.stdout.write("\n汇总：%s；硬门 %d 类命中 / 复核项 %d 类命中\n" %
                     ("、".join(names), len(hard), len(review)))
    if hard:
        sys.stdout.write("脱敏审计不通过（硬门命中，先修再发布）\n")
        return 1
    if review:
        sys.stdout.write("复核项需人工判定并留档（类别见上，逐项写进 plan/RELEASE-M6.md）\n")
    sys.stdout.write("DESENSITIZE_AUDIT_OK\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
