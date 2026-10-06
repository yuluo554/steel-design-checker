"""schema 校验与引用完整性（plan/04 §六 测试矩阵第一行）。"""

import copy
import os

from sdc.kb import load_kb

from _helpers import (CASE, VERIFIED_BY, make_data_dir, pending_records,
                      with_verified_by)


def _load(tmp_path, records=None, raw_files=None):
    return load_kb(make_data_dir(tmp_path, records, raw_files))


def _fields(problems):
    return set((p["kind"], p["field"]) for p in problems)


def test_pending_dataset_is_clean(tmp_path):
    kb = _load(tmp_path)
    assert kb.problems == []


def test_required_field_missing(tmp_path):
    records = pending_records()
    del records["clauses"][0]["gist"]
    problems = _load(tmp_path, records).problems
    assert ("clause", "gist") in _fields(problems)


def test_enum_violation(tmp_path):
    records = pending_records()
    records["clauses"][0]["status"] = "checked"
    problems = _load(tmp_path, records).problems
    assert ("clause", "status") in _fields(problems)


def test_type_mismatch(tmp_path):
    records = pending_records()
    records["clauses"][0]["mandatory"] = "true"
    problems = _load(tmp_path, records).problems
    assert ("clause", "mandatory") in _fields(problems)


def test_field_outside_schema(tmp_path):
    records = pending_records()
    records["clauses"][0]["remark"] = "多余字段"
    problems = _load(tmp_path, records).problems
    assert any(p["problem"].startswith("存在 schema 外字段") for p in problems)


def test_verified_clause_without_channel_is_rejected(tmp_path):
    records = pending_records()
    records["clauses"][0]["status"] = "verified"
    problems = _load(tmp_path, records).problems
    assert ("clause", "verified_by") in _fields(problems)


def test_verified_without_url_is_rejected(tmp_path):
    records = pending_records()
    verified_by = copy.deepcopy(VERIFIED_BY)
    del verified_by["url"]
    records["clauses"][0].update({"status": "verified", "verified_by": verified_by})
    problems = _load(tmp_path, records).problems
    assert ("clause", "verified_by.url") in _fields(problems)


def test_untrusted_channel_is_rejected(tmp_path):
    records = pending_records()
    verified_by = copy.deepcopy(VERIFIED_BY)
    verified_by["channel"] = "凭记忆"
    records["clauses"][0].update({"status": "verified", "verified_by": verified_by})
    problems = _load(tmp_path, records).problems
    assert ("clause", "verified_by.channel") in _fields(problems)


def test_verified_table_must_carry_values(tmp_path):
    records = pending_records()
    records["tables"][0] = with_verified_by(records["tables"][0])
    problems = _load(tmp_path, records).problems
    assert ("table", "values") in _fields(problems)


def test_dangling_reference(tmp_path):
    records = pending_records()
    records["formulas"][0]["clause_id"] = "GB50017-2017:9.9.9"
    problems = _load(tmp_path, records).problems
    refs = [p for p in problems if p["type"] == "reference"]
    assert len(refs) == 1
    assert refs[0]["field"] == "clause_id"


def test_dangling_list_reference(tmp_path):
    records = pending_records()
    records["clauses"][0]["tables"] = ["T-不存在的表"]
    problems = _load(tmp_path, records).problems
    assert any(p["type"] == "reference" and p["field"] == "tables" for p in problems)


def test_duplicate_id(tmp_path):
    records = pending_records()
    records["symbols"].append(copy.deepcopy(records["symbols"][0]))
    problems = _load(tmp_path, records).problems
    assert any(p["type"] == "duplicate" for p in problems)


def test_malformed_json_reported_not_crash(tmp_path):
    bad = '{"symbol": "h_e",,}'  # 少一个引号收尾的坏 JSON，验证不崩只报问题
    kb = _load(tmp_path, raw_files={"symbols/broken.json": bad})
    assert any(p["type"] == "parse" for p in kb.problems)


def test_record_must_be_object(tmp_path):
    kb = _load(tmp_path, raw_files={"symbols/list.json": '["a", "b"]'})
    assert any(p["problem"] == "记录不是 JSON 对象" for p in kb.problems)


def test_located_still_needs_a_channel(tmp_path):
    """located 也是"已核对到某一档"的声称，必须挂渠道+日期+URL。"""
    records = pending_records()
    records["clauses"][0]["status"] = "located"
    problems = _load(tmp_path, records).problems
    assert ("clause", "verified_by") in _fields(problems)


def test_located_clause_with_channel_is_clean(tmp_path):
    records = pending_records()
    records["clauses"][0].update(with_verified_by(records["clauses"][0]))
    records["clauses"][0]["status"] = "located"
    assert _load(tmp_path, records).problems == []


def test_verified_case_requires_source(tmp_path):
    records = pending_records()
    records["cases"] = [dict(CASE, status="verified")]
    problems = _load(tmp_path, records).problems
    assert ("case", "source") in _fields(problems)


def test_verified_case_with_full_source_is_clean(tmp_path):
    records = pending_records()
    source = {"type": "textbook", "title": "夹具书名", "edition": "第 1 版",
              "example_no": "例 1-1"}
    records["cases"] = [dict(CASE, status="verified", source=source)]
    assert _load(tmp_path, records).problems == []


def test_selfcheck_sample_cannot_live_in_cases(tmp_path):
    records = pending_records()
    records["cases"] = [dict(CASE, status="selfcheck")]
    problems = _load(tmp_path, records).problems
    assert any("不参与通过率" in p["problem"] for p in problems)


def test_unknown_module_rejected(tmp_path):
    records = pending_records()
    records["cases"][0]["module"] = "beam_deflection"
    problems = _load(tmp_path, records).problems
    assert ("case", "module") in _fields(problems)


def test_data_dir_without_subdirs_is_tolerated(tmp_path):
    empty = os.path.join(str(tmp_path), "data")
    os.makedirs(os.path.join(empty, "clauses"))
    kb = load_kb(empty)
    assert kb.problems == []
    assert kb.records["clause"] == []
