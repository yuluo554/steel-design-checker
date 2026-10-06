"""测试用数据目录构造：全部 pending 的合法最小知识库。

这里的条号、符号、数值都是**测试夹具**，不是规范知识；真实数据只在 data/ 下经核对后入库。
"""

import copy
import json
import os

SUBDIRS = ("clauses", "tables", "symbols", "formulas", "cases", "selfcheck")

VERIFIED_BY = {
    "channel": "建标库",
    "url": "https://example.invalid/gb50017/7.6.3",
    "date": "2026-10-06",
    "note": "测试夹具：模拟已核对",
}

CLAUSE = {
    "id": "GB50017-2017:7.6.3",
    "standard": "GB 50017-2017",
    "standard_title": "钢结构设计标准",
    "clause_no": "7.6.3",
    "title": "角焊缝强度计算",
    "kind": "formula",
    "status": "pending",
    "gist": "角焊缝承载力按有效截面计算（测试夹具要点，非规范原文）",
    "symbols": ["h_e"],
    "tables": ["T-fillet-weld-value"],
}

FORMULA = {
    "id": "F-FILLET-POSITIVE",
    "clause_id": "GB50017-2017:7.6.3",
    "expr": "N / (h_e * l_w) <= beta_f * f_f_w",
    "symbols": ["h_e"],
    "applies_to": "fillet_weld",
    "status": "pending",
}

SYMBOL = {
    "symbol": "h_e",
    "name_zh": "角焊缝有效厚度",
    "unit": "mm",
    "definition": "h_e = 0.7 * h_f",
    "clause_id": "GB50017-2017:7.6.3",
    "status": "pending",
}

TABLE = {
    "id": "T-fillet-weld-value",
    "clause": "GB50017-2017:7.6.3",
    "title": "角焊缝强度设计值",
    "axes": ["steel_grade"],
    "values": [],
    "interpolation": "group",
    "status": "pending",
}

CASE = {
    "case_id": "CASE-A2-FILLET-001",
    "module": "fillet_weld",
    "inputs": {"h_f": 8.0, "l_w": 240.0, "N": 420000.0},
    "expected": {"ratio": 0.83, "conclusion": "satisfied"},
    "status": "pending",
}


def pending_records():
    """返回一份引用闭环、全部 pending 的合法数据集。"""
    return {
        "clauses": [copy.deepcopy(CLAUSE)],
        "formulas": [copy.deepcopy(FORMULA)],
        "symbols": [copy.deepcopy(SYMBOL)],
        "tables": [copy.deepcopy(TABLE)],
        "cases": [copy.deepcopy(CASE)],
    }


def with_verified_by(record):
    record = copy.deepcopy(record)
    record["status"] = "verified"
    record["verified_by"] = copy.deepcopy(VERIFIED_BY)
    return record


def verified_records():
    """全部升 verified 的同一条数据集（表值用占位数值，仅测门控逻辑）。"""
    data = pending_records()
    table = with_verified_by(data["tables"][0])
    table["values"] = [{"steel_grade": "Q235", "value": 1.0}]
    return {
        "clauses": [with_verified_by(data["clauses"][0])],
        "formulas": [with_verified_by(data["formulas"][0])],
        "symbols": [with_verified_by(data["symbols"][0])],
        "tables": [table],
        "cases": [data["cases"][0]],
    }


def write_json(data_dir, subdir, records):
    path = os.path.join(data_dir, subdir, "records.json")
    payload = json.dumps(records, ensure_ascii=False, indent=2, sort_keys=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
    return path


def make_data_dir(base, records=None, raw_files=None):
    """在 base 下建 data/ 六目录并写入 records；raw_files={subdir/filename: text}。"""
    data_dir = os.path.join(str(base), "data")
    for subdir in SUBDIRS:
        os.makedirs(os.path.join(data_dir, subdir), exist_ok=True)

    for subdir, items in (records or pending_records()).items():
        write_json(data_dir, subdir, items)

    for rel, text in (raw_files or {}).items():
        path = os.path.join(data_dir, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    return data_dir
