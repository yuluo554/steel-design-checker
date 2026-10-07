"""夹具边界守卫：合成 verified 夹具只能待在 tests/ 里。

这条测试存在的理由是 M2 的数值通路必须被 verified 档数据驱动，而仓内规范数据一条都没核对完。
两件事一旦被混淆（夹具值被复制进 data/，或者 data/ 记录了「合成夹具」渠道），
本项目的整个纪律卖点就没了，所以把它做成硬断言而不是文档承诺。
"""

import json
import os

from _helpers import FIXTURE_KB_DIR, REPO_DATA_DIR
from sdc.kb import load_kb
from sdc.kb.gate import module_gate
from sdc.kb.schema import MODULES, VERIFIED_BY_CHANNELS

DATA_DIRS = ("clauses", "tables", "symbols", "formulas", "rules", "checklist",
           "cases", "selfcheck")


def _iter_records(root):
    for subdir in DATA_DIRS:
        directory = os.path.join(root, subdir)
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if not name.endswith(".json"):
                continue
            with open(os.path.join(directory, name), encoding="utf-8") as handle:
                payload = json.loads(handle.read())
            records = payload if isinstance(payload, list) else [payload]
            for rec in records:
                if isinstance(rec, dict):
                    yield subdir, name, rec


def test_fixture_kb_is_schema_clean_and_all_modules_ready():
    kb = load_kb(FIXTURE_KB_DIR)
    assert kb.problems == [], kb.problems
    for module in MODULES:
        gate = module_gate(module, kb)
        assert gate["status"] == "ready", (module, gate["unready"])


def test_synthetic_channel_is_whitelisted_only_for_fixtures():
    assert "合成夹具" in VERIFIED_BY_CHANNELS


def test_repo_data_never_uses_the_synthetic_fixture_channel():
    offenders = []
    for subdir, name, rec in _iter_records(REPO_DATA_DIR):
        verified_by = rec.get("verified_by")
        if isinstance(verified_by, dict) and verified_by.get("channel") == "合成夹具":
            offenders.append("%s/%s:%s" % (subdir, name, rec.get("id") or rec.get("symbol")))
        text = json.dumps(rec, ensure_ascii=False)
        if "fixture://synthetic" in text:
            offenders.append("%s/%s:%s 含夹具 URL" % (subdir, name, rec.get("id")))
    assert offenders == [], "夹具数据泄漏进 data/：%s" % offenders


def test_repo_data_has_no_fixture_ids():
    offenders = []
    for subdir, name, rec in _iter_records(REPO_DATA_DIR):
        for key in ("id", "symbol", "case_id"):
            value = rec.get(key)
            if isinstance(value, str) and (value.startswith("FX-") or value.startswith("F-FX-")):
                offenders.append("%s/%s:%s" % (subdir, name, value))
    assert offenders == []


def test_fixture_values_are_deliberately_unlike_real_normative_values():
    """夹具的**数值本体**不许与规范/渠道转述值撞车（notes 里作为对照说明提到是允许的）。

    撞车的危险是：以后有人翻到夹具 JSON，看到 1.22 就以为是核对过的 β_f 真值。
    """
    tokens = []
    for _, _, rec in _iter_records(FIXTURE_KB_DIR):
        for key in ("expr", "bound_expr", "bound"):
            if key in rec:
                tokens.append(str(rec[key]))
        for entry in rec.get("values") or []:
            if not isinstance(entry, dict):
                continue
            tokens.extend(str(value)
                          for value in (entry.get("outputs") or {}).values())
            if "x" in entry:
                tokens.append(str(entry["x"]))
    blob = " ".join(tokens)
    for suspicious in ("1.22", "0.85", "1.111", "215", "125", "305", "0.42"):
        assert suspicious not in blob, \
            "夹具数值 %s 与渠道转述值撞车，容易被误当成核对结果" % suspicious
