"""规则集复核元数据守门（阶段三 任务 5）。

字段规范 = ``10-6-scaffold-formwork-checker`` v2.0.0 的实测形态（``meta.review``：
``reviewed_on`` / ``cycle_months`` / ``next_review_due`` / ``reviewer`` / ``standards[]``）。

**本仓的落位差异（已登记）**：`data/<kind>/*.json` 是顶层 JSON **数组**，无法在同一文件里再承载
文件级 ``meta.review``；因此复核元数据落在 ``data/review/ruleset-review.json``（loader 只扫
``data/<kind>/`` 目录，不读这里，因此零判定影响），并在其中用 ``covered_files`` 覆盖每个知识文件。
README「判定依据」表与报告头 ``STANDARDS_LINE`` 与之三处一致。

6 个用例（scaffold 5 条 + 1 条报告头）：

1. 元数据齐全；
2. 日期可解析且 ``next_review_due > reviewed_on``，``cycle_months`` 与跨度相符；
3. 每部标准 ``authority_url`` 非空且为 URL；
4. 清单类一致性：``covered_files`` 覆盖全部知识文件，且每条引用的标准都在 ``standards`` 里；
5. 「本版本不依赖」声明：``declared_not_used`` 每项必须有非空 ``not_used_by``，
   且 ``used_by`` / ``not_used_by`` 里的模块都真实存在（依赖面吻合）；
6. 报告头可见依据版本与引擎版本（任务 5 验收第 1 项），且不含 URL / 生成时间。

任一判据被破坏必须报红 —— 负控记录见 plan/audits 的阶段三交接文档。
"""

import datetime
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_PATH = REPO_ROOT / "data" / "review" / "ruleset-review.json"
KNOWLEDGE_DIRS = ("clauses", "tables", "formulas", "symbols", "rules", "checklist")
REQUIRED_REVIEW_KEYS = ("reviewed_on", "cycle_months", "next_review_due", "reviewer",
                        "standards", "covered_files", "declared_not_used")
REQUIRED_STANDARD_KEYS = ("standard", "issued", "effective", "currency",
                          "authority_url", "conclusion")


def _review():
    payload = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
    return payload["meta"]["review"]


def _date(text):
    return datetime.datetime.strptime(text, "%Y-%m-%d").date()


def _module_exists(dotted):
    rel = dotted.replace(".", "/")
    return any((REPO_ROOT / "src" / (rel + suffix)).exists()
               for suffix in (".py", "/__init__.py"))


def _knowledge_files():
    found = []
    for kind in KNOWLEDGE_DIRS:
        for path in sorted((REPO_ROOT / "data" / kind).glob("*.json")):
            found.append("%s/%s" % (kind, path.name))
    return found


def test_review_metadata_is_complete():
    review = _review()
    for key in REQUIRED_REVIEW_KEYS:
        assert review.get(key) not in (None, "", [], {}), "meta.review 缺字段：%s" % key
    assert isinstance(review["cycle_months"], int) and review["cycle_months"] > 0


def test_review_dates_are_parsable_and_next_due_is_after_reviewed_on():
    review = _review()
    reviewed = _date(review["reviewed_on"])
    due = _date(review["next_review_due"])
    assert due > reviewed
    months = (due.year - reviewed.year) * 12 + (due.month - reviewed.month)
    assert abs(months - review["cycle_months"]) <= 1


def test_every_standard_carries_authority_url():
    for item in _review()["standards"]:
        for key in REQUIRED_STANDARD_KEYS:
            assert str(item.get(key) or "").strip(), (
                "标准 %r 缺 %s" % (item.get("standard"), key))
        for part in str(item["authority_url"]).split(";"):
            if part.strip():
                assert part.strip().startswith("http")


def test_covered_files_match_the_knowledge_tree():
    review = _review()
    declared = set(review["covered_files"])
    actual = set(_knowledge_files())
    assert declared == actual, (
        "covered_files 与 data/ 实际知识文件不一致：缺 %s / 多 %s"
        % (sorted(actual - declared), sorted(declared - actual)))
    known = {item["standard"] for item in review["standards"]}
    for name, entry in review["covered_files"].items():
        assert entry.get("standard"), "%s 未声明标准" % name
        unknown = set(entry["standard"]) - known
        assert not unknown, "%s 引用了未登记的标准：%s" % (name, sorted(unknown))


def test_unused_declarations_and_real_modules():
    review = _review()
    for name, entry in review["covered_files"].items():
        used_by = list(entry.get("used_by") or [])
        not_used_by = list(entry.get("not_used_by") or [])
        assert used_by or not_used_by, (
            "%s 既没声明 used_by 也没声明 not_used_by" % name)
        for module in used_by + not_used_by:
            assert _module_exists(module), "%s 声明的模块不存在：%s" % (name, module)
    assert review["declared_not_used"], "至少要有「本版本不依赖」的显式声明"
    for item in review["declared_not_used"]:
        assert item.get("not_used_by"), item.get("item")
        for module in item["not_used_by"]:
            assert _module_exists(module), "not_used_by 指向不存在的模块：%s" % module


def test_report_header_shows_standards_and_engine_version():
    from sdc import __version__
    from sdc.report.body import STANDARDS_LINE, _header

    head = "\n".join(_header("标题", "report", ["参数卡：x.json"]))
    assert "引擎版本：%s" % __version__ in head
    assert "依据规范" in head
    for standard in ("GB 50017-2017", "GB 55006-2021", "JGJ 82-2011"):
        assert standard in head
    assert STANDARDS_LINE in head
    # 交付物硬约束：不写 URL（0 外链）、不写生成时间（K42 无身份信息 + 逐字节一致）
    assert "http" not in head and "生成时间" not in head