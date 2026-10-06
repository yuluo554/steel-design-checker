"""知识库记录 schema 声明与校验（无第三方依赖）。

字段口径来自 plan/04 §三 与 plan/05 §二/§四。校验里包含两条"纪律"型硬约束：

- `status=verified` 的条款/表/公式/符号必须挂全 `verified_by`（渠道 + 日期 + URL），
  否则视为未核对；
- `status=verified` 的算例必须有完整来源（书名或标准名 + 版次/页 + 例题号），
  来源不完整的只能以 `pending` 留在 `data/cases/`，或降级进 `data/selfcheck/`（D10/D07）。
"""

from typing import Any, Dict, List, Optional

MODULES = (
    "butt_weld",
    "fillet_weld",
    "bolt_normal",
    "bolt_hsb_friction",
    "column_buckling",
)

STATUS_KB = ("pending", "located", "verified")
STATUS_CASE = ("pending", "verified", "selfcheck")

# 已核对到哪一档：located=条号/主题/表号已定位；verified=式体与数值也已核对
CHECKED_STATUSES = ("located", "verified")

# verified 记录必须挂的核对渠道字段
VERIFIED_BY_REQUIRED = ("channel", "date", "url")
VERIFIED_BY_CHANNELS = ("官方", "建标库", "纸质规范", "国标全文公开", "住建部公告")
# 算例作为真值必须有的来源字段
CASE_SOURCE_REQUIRED = ("title", "example_no")

_TYPES = {
    "str": str,
    "bool": bool,
    "int": int,
    "num": (int, float),
    "list": list,
    "dict": dict,
}

SPEC = {
    "clause": {
        "dir": "clauses",
        "id_field": "id",
        "required": {
            "id": "str",
            "standard": "str",
            "clause_no": "str",
            "kind": "str",
            "status": "str",
            "gist": "str",
        },
        "optional": {
            "standard_title": "str",
            "chapter": "str",
            "title": "str",
            "mandatory": "bool",
            "verified_by": "dict",
            "formulas": "list",
            "symbols": "list",
            "tables": "list",
            "limits": "list",
            "supersedes": "str",
            "notes": "str",
        },
        "enums": {
            "kind": ("formula", "table", "limit", "construct", "mandatory"),
            "status": STATUS_KB,
        },
        "refs": {},
        "list_refs": {"formulas": "formula", "symbols": "symbol", "tables": "table"},
    },
    "table": {
        "dir": "tables",
        "id_field": "id",
        "required": {
            "id": "str",
            "clause": "str",
            "axes": "list",
            "values": "list",
            "interpolation": "str",
            "status": "str",
        },
        "optional": {
            "title": "str",
            "unit": "str",
            "verified_by": "dict",
            "notes": "str",
            "source_table_no": "str",
        },
        "enums": {
            "interpolation": ("none", "group", "linear"),
            "status": STATUS_KB,
        },
        "refs": {"clause": "clause"},
        "list_refs": {},
    },
    "formula": {
        "dir": "formulas",
        "id_field": "id",
        "required": {
            "id": "str",
            "clause_id": "str",
            "expr": "str",
            "symbols": "list",
            "applies_to": "str",
            "status": "str",
        },
        "optional": {
            "direction": "str",
            "unit_system": "str",
            "notes": "str",
            "verified_by": "dict",
        },
        "enums": {
            "applies_to": MODULES + ("general",),
            "status": STATUS_KB,
        },
        "refs": {"clause_id": "clause"},
        "list_refs": {"symbols": "symbol"},
    },
    "symbol": {
        "dir": "symbols",
        "id_field": "symbol",
        "required": {"symbol": "str", "name_zh": "str", "unit": "str", "status": "str"},
        "optional": {
            "definition": "str",
            "clause_id": "str",
            "derivation": "str",
            "notes": "str",
            "verified_by": "dict",
        },
        "enums": {"status": STATUS_KB},
        "refs": {"clause_id": "clause"},
        "list_refs": {},
    },
    "case": {
        "dir": "cases",
        "id_field": "case_id",
        "required": {
            "case_id": "str",
            "module": "str",
            "inputs": "dict",
            "expected": "dict",
            "status": "str",
        },
        "optional": {
            "source": "dict",
            "tolerance": "dict",
            "applicability_checks": "list",
            "notes": "str",
        },
        "enums": {"module": MODULES, "status": STATUS_CASE},
        "refs": {},
        "list_refs": {},
    },
    # data/selfcheck/ 用近似算例结构，但只能 pending / selfcheck 两态，不得充当真值
    "selfcheck": {
        "dir": "selfcheck",
        "id_field": "case_id",
        "required": {"case_id": "str", "module": "str", "inputs": "dict"},
        "optional": {
            "expected": "dict",
            "assertions": "list",
            "source": "dict",
            "tolerance": "dict",
            "notes": "str",
            "status": "str",
        },
        "enums": {"module": MODULES, "status": ("pending", "selfcheck")},
        "refs": {},
        "list_refs": {},
    },
}


def _check_type(value: Any, expected: str) -> bool:
    if expected == "bool":
        return isinstance(value, bool)
    if expected == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "num":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, _TYPES[expected])


def validate_record(
    kind: str,
    rec: Any,
    where: str,
    known_ids: Optional[Dict[str, set]] = None,
) -> List[Dict[str, str]]:
    """单条记录 -> 问题列表；known_ids=None 时跳过引用完整性检查。"""
    spec = SPEC[kind]
    problems = []  # type: List[Dict[str, str]]

    if not isinstance(rec, dict):
        return [{"file": where, "kind": kind, "id": "", "field": "", "type": "schema",
                 "problem": "记录不是 JSON 对象"}]

    def add(field: str, problem: str, ptype: str = "schema") -> None:
        problems.append({
            "file": where,
            "kind": kind,
            "id": str(rec.get(spec["id_field"], "")),
            "field": field,
            "type": ptype,
            "problem": problem,
        })

    for field, expected in spec["required"].items():
        if field not in rec or rec[field] is None:
            add(field, "必填字段缺失（要求 %s）" % expected)
            continue
        if expected == "str" and rec[field] == "":
            add(field, "必填字符串为空（要求 %s）" % expected)
            continue
        if not _check_type(rec[field], expected):
            add(field, "类型应为 %s，实际 %s" % (expected, type(rec[field]).__name__))

    for field, expected in spec["optional"].items():
        if field in rec and rec[field] is not None and not _check_type(rec[field], expected):
            add(field, "类型应为 %s，实际 %s" % (expected, type(rec[field]).__name__))

    for field, allowed in spec["enums"].items():
        value = rec.get(field)
        if value is not None and value not in allowed:
            add(field, "取值 %r 不在枚举 %s 内" % (value, list(allowed)))

    unknown = sorted(set(rec) - set(spec["required"]) - set(spec["optional"]))
    if unknown:
        add("", "存在 schema 外字段：%s" % ", ".join(unknown))

    status = rec.get("status")
    if status == "verified":
        # pending 允许"条目已建、数据待核"（列表/对象为空）；一旦声称已核对就必须有内容
        for field, expected in spec["required"].items():
            if expected in ("list", "dict") and rec.get(field) in ([], {}, None):
                add(field, "status=verified 但 %s 为空（未核对到位不得声称已核对）" % field)
    if kind == "case" and status == "selfcheck":
        add("status", "status=selfcheck 的样例属 data/selfcheck/，不得放在 data/cases/（不参与通过率）")
    if kind in ("clause", "table", "formula", "symbol") and status in CHECKED_STATUSES:
        # located 与 verified 都必须说清"核对到哪一档"；算例的出处走 source（书名/标准名 + 版次 + 例题号）
        _check_verified_by(rec, add)
    if kind == "case" and status == "verified":
        _check_case_source(rec, add)

    if known_ids is not None:
        for field, ref_kind in spec["refs"].items():
            value = rec.get(field)
            if isinstance(value, str) and value and value not in known_ids.get(ref_kind, set()):
                add(field, "悬空引用：%s 指向不存在的 %s" % (value, ref_kind), "reference")
        for field, ref_kind in spec["list_refs"].items():
            for value in rec.get(field) or []:
                if isinstance(value, str) and value not in known_ids.get(ref_kind, set()):
                    add(field, "悬空引用：%s 指向不存在的 %s" % (value, ref_kind), "reference")

    return problems


def _check_verified_by(rec: Dict[str, Any], add) -> None:
    verified_by = rec.get("verified_by")
    if not isinstance(verified_by, dict):
        add("verified_by", "status=verified 但缺 verified_by（渠道+日期+URL）")
        return
    for field in VERIFIED_BY_REQUIRED:
        value = verified_by.get(field)
        if not value or value == "待补":
            add("verified_by." + field,
                "status=verified 必须填 %s（无出处不得核对通过）" % field)
    channel = verified_by.get("channel")
    if channel and channel not in VERIFIED_BY_CHANNELS:
        add("verified_by.channel", "渠道 %r 不在白名单内" % channel)


def _check_case_source(rec: Dict[str, Any], add) -> None:
    source = rec.get("source")
    if not isinstance(source, dict):
        add("source", "status=verified 的算例必须有来源（D07）")
        return
    for field in CASE_SOURCE_REQUIRED:
        if not source.get(field):
            add("source." + field, "真值算例来源缺 %s（无来源不得作真值）" % field)
    if not (source.get("edition") or source.get("page")):
        add("source.edition", "真值算例来源需版次或页码之一")
