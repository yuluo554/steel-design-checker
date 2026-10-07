"""测试用数据目录构造：全部 pending 的合法最小知识库。

这里的条号、符号、数值都是**测试夹具**，不是规范知识；真实数据只在 data/ 下经核对后入库。
"""

import copy
import json
import os
import shutil

SUBDIRS = ("clauses", "tables", "symbols", "formulas", "rules", "checklist",
           "cases", "selfcheck")

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
    table["values"] = [{"axes": {"steel_grade": "Q235"}, "outputs": {"f_f_w": 1.0}}]
    return {
        "clauses": [with_verified_by(data["clauses"][0])],
        "formulas": [with_verified_by(data["formulas"][0])],
        "symbols": [with_verified_by(data["symbols"][0])],
        "tables": [table],
        "cases": [data["cases"][0]],
    }


HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE_KB_DIR = os.path.join(HERE, "fixtures", "kb")
# M3：核查规则/检查单的 verified 档夹具（口径 D17/K25 的文本侧对应物）。
# 真实 data/ 里规则依据只到 located ⇒ 最高只能判 suspicious，abnormal 这条路必须
# 有一份"依据已核对"的夹具来兑现，否则闸门表的另一半天长天没被跑过。
FIXTURE_RULES_DIR = os.path.join(HERE, "fixtures", "rules_kb")
REPO_DATA_DIR = os.path.normpath(os.path.join(HERE, os.pardir, "data"))


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


def fixture_copy(base):
    """把合成 verified 夹具 KB 复制到 tmp，供「降级某条记录」的门控测试使用。"""
    target = os.path.join(str(base), "kb")
    shutil.copytree(FIXTURE_KB_DIR, target)
    return target


def patch_status(data_dir, subdir, ids, status, id_field="id"):
    """只改 status，其余字段（含 values/expr）原样保留——用来制造「located 却带着数值」的陷阱。"""
    targets = set(ids)
    count = 0
    for name in sorted(os.listdir(os.path.join(data_dir, subdir))):
        if not name.endswith(".json"):
            continue
        path = os.path.join(data_dir, subdir, name)
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.loads(handle.read())
        records = payload if isinstance(payload, list) else [payload]
        for rec in records:
            if isinstance(rec, dict) and rec.get(id_field) in targets:
                rec["status"] = status
                count += 1
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    assert count, "没有命中任何记录：%s" % ", ".join(sorted(targets))
    return count


# ---------------------------------------------------------------------------
# 夹具参数卡：期望比值全部由人工独立算出（见每条注释），不是引擎回填。
# 夹具 KB 的数值是虚构的，这些期望只对夹具成立，不构成任何规范结论。
# ---------------------------------------------------------------------------

CARD_A1 = {
    "case_id": "CARD-A1", "module": "butt_weld",
    "steel_grade": "Q235", "thickness_group": "t<=16", "weld_quality_class": "二级",
    "weld_type": "直缝", "groove_form": "全熔透", "has_opening_gap": True,
    "b": 100.0, "t": 10.0, "l_w": 100.0,
    "forces": {"N": 100000.0, "V": 0.0}, "units": {"force": "N", "length": "mm"},
}
RATIO_A1 = 0.625  # A_w=100*10=1000 → 100000/1000=100 → 100/160

CARD_A2 = {
    "case_id": "CARD-A2", "module": "fillet_weld",
    "steel_grade": "Q235", "thickness_group": "t<=16", "load_direction": "侧面",
    "h_f": 10.0, "l_w": 100.0, "n_welds": 2, "t_min": 10.0,
    "forces": {"N": 100000.0}, "units": {"force": "N", "length": "mm"},
}
RATIO_A2 = 0.7142857142857143  # h_e=7, l_w_total=200 → 100000/1400=71.42857… → /100

CARD_A3 = {
    "case_id": "CARD-A3", "module": "bolt_normal",
    "steel_grade": "Q235", "thickness_group": "t<=16", "bolt_grade": "4.6",
    "bolt_type": "C级", "load_state": "受剪", "d": 20.0, "d_0": 21.5, "sum_t": 10.0,
    "bolt_count": 5, "group": {"n_x": 1, "n_y": 5, "pitch": 80.0},
    "forces": {"V": 100000.0}, "units": {"force": "N", "length": "mm"},
}
RATIO_A3 = 0.707355302630646  # 20000/A_s(314.1592653589793)=63.66197723675814 → /90

CARD_A4 = {
    "case_id": "CARD-A4", "module": "bolt_hsb_friction",
    "steel_grade": "Q235", "thickness_group": "t<=16", "bolt_grade": "10.9",
    "surface_treatment": "喷砂", "hole_type": "标准孔", "load_state": "受剪",
    "connection_type": "摩擦型", "n_f": 2, "bolt_count": 4,
    "group": {"n_x": 2, "n_y": 2, "pitch": 80.0},
    "forces": {"V": 80000.0}, "units": {"force": "N", "length": "mm"},
}
RATIO_A4 = 20000.0 / 48000.0  # k*n_f*mu*P=1.0*2*0.4*60000（P 表单位 kN → 入口换算 N）

CARD_A5 = {
    "case_id": "CARD-A5", "module": "column_buckling",
    "steel_grade": "Q345", "thickness_group": "t<=16", "section": "双轴对称工字形（夹具）",
    "section_class": "b", "l_0x": 1000.0, "l_0y": 800.0, "A": 1000.0,
    "i_x": 50.0, "i_y": 40.0,
    "forces": {"N": 97000.0}, "units": {"force": "N", "length": "mm", "area": "mm2"},
}
RATIO_A5 = 0.5  # λ=max(20,20)=20 → φ=0.97 → 97000/(0.97*1000)=100 → 100/200

BASE_CARDS = {
    "butt_weld": (CARD_A1, RATIO_A1),
    "fillet_weld": (CARD_A2, RATIO_A2),
    "bolt_normal": (CARD_A3, RATIO_A3),
    "bolt_hsb_friction": (CARD_A4, RATIO_A4),
    "column_buckling": (CARD_A5, RATIO_A5),
}


def scaled(card, factor):
    """把全部设计内力按同一系数放大（其余不变），用于制造边界档与超限档。"""
    out = copy.deepcopy(card)
    forces = out.get("forces") or {}
    for name in sorted(forces):
        if forces[name]:
            forces[name] = float(forces[name]) * factor
    return out
