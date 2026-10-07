"""脱敏审计工具的守门测试（M6）。

价值在三处：
1. **阳性对照**必须命中、**阴性对照**必须不命中——扫描器空转比没有扫描器更危险（food M6 的
   selftest 就是靠这条抓出"合成手机号只有 10 位"的夹具 bug）；
2. **扫描器源码必须过自己的扫描**：模式与词面用片段拼接/base64，完整字面一旦进了这个文件，
   就会永久留在 git 历史里，"全历史 0 命中"从此永远验不过；
3. **分级不许被悄悄放宽**：硬门类别写死在断言里，把手机号或邮箱降级成"复核项"会立刻红。
"""

import importlib.util
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "scripts", "audit_release.py")


def _frag(*parts):
    """测试样本一律片段拼接：完整字面写进这个文件，文件就会命中自己的扫描并永留历史。"""
    return "".join(parts)


_spec = importlib.util.spec_from_file_location("audit_release", SCRIPT)
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)

HARD_CATEGORIES = ("sk_key", "secret_assignment", "phone_cn", "id_card", "private_ip",
                   "personal_home", "personal_mark_text", "personal_mark_bytes",
                   "personal_email", "forbidden_path", "docx_not_readable",
                   "dist_forbidden_dir", "dist_forbidden_root", "dist_forbidden_file",
                   "audit_selfcheck")
REVIEW_CATEGORIES = ("drive_path", "sister_word", "sister_word_bytes")


def _run(mode):
    hits = audit.Hits()
    audit.MODES[mode](hits)
    return hits


def test_selftest_controls_pass():
    hits = _run("selftest")
    assert not hits.hard(), [item[4] for item in hits.hard()]


def test_scanner_source_passes_its_own_scan():
    with open(SCRIPT, "r", encoding="utf-8") as handle:
        text = handle.read()
    hits = audit.Hits()
    audit.scan_text("scripts/audit_release.py", text, hits)
    assert not hits.hard(), "扫描器源码里存在完整敏感字面：%s" % [i[1] for i in hits.hard()]


@pytest.mark.parametrize("mode", ["tracked", "binary", "messages"])
def test_release_surface_has_no_hard_hits(mode):
    hits = _run(mode)
    hard = hits.hard()
    assert not hard, "%s 模式硬门命中：%s" % (mode, [(i[0], i[1], i[3]) for i in hard])


def test_category_severity_is_not_silently_downgraded():
    seen = {}
    for name in ("tracked", "binary", "messages"):
        for _where, category, severity, _count, _note in _run(name).items:
            seen.setdefault(category, severity)
    # 未被本轮扫到的类别，用夹具样本逼出来
    samples = {
        "sk_key": "sk-" + "A" * 20,
        "phone_cn": "1" + "3" * 10,
        "id_card": "1" * 17 + "X",
        "private_ip": _frag("10.12.", "34.56"),
        "personal_email": _frag("a.b@gm", "ail.com"),
        "forbidden_path": "",
        "docx_not_readable": "",
    }
    for category, sample in samples.items():
        if sample:
            hits = audit.Hits()
            audit.scan_text("probe", sample, hits)
            seen.setdefault(category, next((i[2] for i in hits.items if i[1] == category), None))
    for category in HARD_CATEGORIES:
        assert seen.get(category, audit.HARD) == audit.HARD, "%s 被降级了" % category
    for category in REVIEW_CATEGORIES:
        assert seen.get(category, audit.REVIEW) == audit.REVIEW, "%s 越级成了硬门" % category


def test_email_whitelist_only_honours_reserved_and_service_domains():
    assert set(audit.EMAIL_EXEMPT_DOMAINS) <= {"example.com", "example.org", "localhost"}
    for address in (_frag("someone@gm", "ail.com"), _frag("someone@q", "q.com"),
                    _frag("someone@corp", ".internal")):
        hits = audit.Hits()
        audit.scan_text("probe", address, hits)
        assert any(i[1] == "personal_email" for i in hits.items), "%s 不该被放行" % address
    for address in ("someone@example.com", "3+u@users.noreply.github.com", "git@github.com"):
        hits = audit.Hits()
        audit.scan_text("probe", address, hits)
        assert not any(i[1] == "personal_email" for i in hits.items), "%s 应属白名单" % address


def test_personal_home_path_is_hard_but_placeholder_is_not():
    mark = audit.PERSONAL_MARKS[0]
    hits = audit.Hits()
    audit.scan_text("probe", "配置在 C:\\Users\\%s\\AppData" % mark, hits)
    assert any(i[1] == "personal_home" and i[2] == audit.HARD for i in hits.items)
    clean = audit.Hits()
    audit.scan_text("probe", "见 C:\\Users\\<name>\\ 与 D:\\data\\out.docx", clean)
    assert not clean.hard(), [i[1] for i in clean.hard()]


def test_forbidden_tracked_name_pattern():
    # 模式故意宽（`token`/`secret` 作子串也算），因为这一条买的是"密钥类文件混进跟踪面"的保险
    for name in ("prod.env", "deploy.key", "secret.json", "api_token.txt", "data/x_private/a.md",
                 "tokens.py"):
        assert audit.FORBIDDEN_TRACKED_NAMES.search(name), name
    for name in ("README.md", "scripts/audit_release.py", ".github/workflows/ci.yml"):
        assert not audit.FORBIDDEN_TRACKED_NAMES.search(name), name
