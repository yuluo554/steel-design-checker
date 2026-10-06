"""data_fingerprint 口径 K12：sha256(data/clauses + data/tables 规范化拼接)。"""

import json
import os

from sdc.kb import data_fingerprint

from _helpers import make_data_dir


def _read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.loads(handle.read())


def _write(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)


def _reserialized_copy(src, dst, indent):
    """同一份内容换排版写到 dst，只复制参与指纹的两个目录。"""
    os.makedirs(dst)
    for sub in ("clauses", "tables"):
        data = _read(os.path.join(src, sub, "records.json"))
        _write(os.path.join(dst, sub, "records.json"),
               json.dumps(data, ensure_ascii=False, indent=indent, sort_keys=True))
    return dst


def test_fingerprint_is_stable(tmp_path):
    data_dir = make_data_dir(tmp_path)
    assert data_fingerprint(data_dir) == data_fingerprint(data_dir)


def test_formatting_and_key_order_do_not_matter(tmp_path):
    src = make_data_dir(tmp_path)
    dst = _reserialized_copy(src, os.path.join(str(tmp_path), "other"), indent=None)
    assert data_fingerprint(src) == data_fingerprint(dst)


def test_value_change_changes_fingerprint(tmp_path):
    data_dir = make_data_dir(tmp_path)
    before = data_fingerprint(data_dir)
    tables = _read(os.path.join(data_dir, "tables", "records.json"))
    tables[0]["values"] = [{"steel_grade": "Q355", "value": 2.0}]
    _write(os.path.join(data_dir, "tables", "records.json"),
           json.dumps(tables, ensure_ascii=False, indent=2, sort_keys=True))
    assert data_fingerprint(data_dir) != before


def test_clause_number_change_changes_fingerprint(tmp_path):
    data_dir = make_data_dir(tmp_path)
    before = data_fingerprint(data_dir)
    clauses = _read(os.path.join(data_dir, "clauses", "records.json"))
    clauses[0]["clause_no"] = "7.6.4"
    _write(os.path.join(data_dir, "clauses", "records.json"),
           json.dumps(clauses, ensure_ascii=False, indent=2, sort_keys=True))
    assert data_fingerprint(data_dir) != before


def test_symbols_and_cases_are_not_signed(tmp_path):
    """K12 只签 clauses + tables；改其他目录不得改变指纹（改了会打挂全部基准）。"""
    data_dir = make_data_dir(tmp_path)
    before = data_fingerprint(data_dir)
    symbols = _read(os.path.join(data_dir, "symbols", "records.json"))
    symbols[0]["name_zh"] = "改了名"
    _write(os.path.join(data_dir, "symbols", "records.json"),
           json.dumps(symbols, ensure_ascii=False, indent=2, sort_keys=True))
    assert data_fingerprint(data_dir) == before


def test_is_hex_sha256(tmp_path):
    value = data_fingerprint(make_data_dir(tmp_path))
    assert len(value) == 64
    assert all(c in "0123456789abcdef" for c in value)
