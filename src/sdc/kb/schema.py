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

# 需要挂 `verified_by` 的知识记录类型（算例走 source，selfcheck 样例不挂）
KB_RECORD_KINDS = ("clause", "table", "formula", "symbol", "rule", "checklist")

# verified 记录必须挂的核对渠道字段
VERIFIED_BY_REQUIRED = ("channel", "date", "url")
# 「合成夹具」只允许出现在 tests/fixtures/ 下（tests/test_engine_fixtures.py 断言它进 data/ 即失败），
# 加进白名单是为了让引擎的数值通路能被 verified 档数据测试到，而不必假装那是规范值。
# 「双主机文字层」= 两个独立主机的**文字层**逐字命中同一表述（M3 的 GB 55006 全 8 章即此档，
# 107/107 条双源命中，见 .tmp_verify/m3/gb55006-full/_crosscheck.tsv）。
# 「电子版PDF文字层」= 出版社**电子版 PDF 的矢量文字层**（不是扫描图的 OCR，也不是页面图），
# M3 的附录 D φ 表与 D.0.5 式体走这一档：电子版文字层 + 镜像页面图逐格转录 + 原书 OCR 三路互证，
# 并按 D22 的 ±0.001 容差与 D.0.5 公式反算同点同值。
# 注意：表体/式体的镜像图片**不算**双源——M3 实测两站表体图片解码后像素完全相同（同一批底图的
# 不同容器），"双镜像逐格一致"只等于一次读图（.tmp_verify/m3/residual/CONCLUSION.md §三）。
VERIFIED_BY_CHANNELS = ("官方", "建标库", "纸质规范", "国标全文公开", "住建部公告",
                        "双主机文字层", "电子版PDF文字层", "合成夹具")
# 算例作为真值必须有的来源字段
CASE_SOURCE_REQUIRED = ("title", "example_no")

# 三档 status 的序（口径 D15）：规则的判定档位不得高于它的依据条款，取 min 用
STATUS_RANK = {"pending": 0, "located": 1, "verified": 2}

# 核查规则的条件语言（闭集，判定层不对文档执行正则——口径 K26/K28/K39）。未知算子直接判数据不合法。
CONDITION_OPS = ("keyword_any", "keyword_all", "slot_present", "slot_absent", "slot_in",
                 "all_of", "any_of", "not")

# 断言算子的字段要求：`all` 必须全有，`any_of` 至少一项非空，`threshold` 键必须存在
# （值可以是 null —— 未核对的阈值一律写 null，见口径 K14/D11 在规则表上的形态）。
ASSERT_KINDS = {
    "presence": {"any_of": ("slots", "keyword_any")},
    "cross_param": {"any_of": ("require_any_slots", "require_any_keywords")},
    "consistency": {"all": ("slot",)},
    "ordinal_min": {"all": ("slot", "order"), "threshold": ("min",)},
    "numeric_min": {"all": ("slot",), "threshold": ("bound",)},
    "numeric_max": {"all": ("slot",), "threshold": ("bound",)},
}
THRESHOLD_KINDS = ("ordinal_min", "numeric_min", "numeric_max")
THRESHOLD_FIELDS = ("min", "bound")

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
            "expect_input_error": "bool",
            "source": "dict",
            "tolerance": "dict",
            "notes": "str",
            "status": "str",
        },
        "enums": {"module": MODULES, "status": ("pending", "selfcheck")},
        "refs": {},
        "list_refs": {},
    },
    # M3 文本核查规则表（plan/04 §四）。等级不在规则里写：见 CHECK_TYPE_COLUMNS 与 rules/gate.py，
    # 规则自带 level_rules 会让"依据只是 located 的规则"有能力自称 abnormal。
    "rule": {
        "dir": "rules",
        "id_field": "id",
        "required": {
            "id": "str",
            "name": "str",
            "check_type": "str",
            "status": "str",
            "basis": "list",
            "assert": "dict",
        },
        "optional": {
            "gate_keywords": "list",
            "scope": "str",
            "when": "dict",
            "also_expect": "list",
            "suggestion": "str",
            "notes": "str",
            "verified_by": "dict",
        },
        "enums": {
            "check_type": ("consistency", "presence", "limit", "construct", "cross_param"),
            "scope": ("document", "paragraph"),
            "status": STATUS_KB,
        },
        "refs": {},
        "list_refs": {},
        "dict_refs": {"basis": ("clause_id", "clause")},
    },
    # M3 GB 55006 检查单条目（plan/04 §五）
    "checklist": {
        "dir": "checklist",
        "id_field": "id",
        "required": {
            "id": "str",
            "standard": "str",
            "chapter": "str",
            "gist": "str",
            "requirement_type": "str",
            "status": "str",
        },
        "optional": {
            "clause_id": "str",
            "title": "str",
            "check_hint": "str",
            "check_type": "str",
            "linked_slots": "list",
            "supersedes": "str",
            "mandatory": "bool",
            "check": "dict",
            "verified_by": "dict",
            "notes": "str",
        },
        "enums": {
            "requirement_type": ("must", "should", "may"),
            "check_type": ("consistency", "presence", "limit", "construct", "cross_param"),
            "status": STATUS_KB,
        },
        "refs": {"clause_id": "clause"},
        "list_refs": {},
        "dict_refs": {},
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
    if kind in KB_RECORD_KINDS and status in CHECKED_STATUSES:
        # located 与 verified 都必须说清"核对到哪一档"；算例的出处走 source（书名/标准名 + 版次 + 例题号）
        _check_verified_by(rec, add)
    if kind == "case" and status == "verified":
        _check_case_source(rec, add)
        tolerance = rec.get("tolerance")
        if not isinstance(tolerance, dict) or not tolerance:
            add("tolerance", "status=verified 的算例必须逐条登记真值比对容差（口径 K3）")
    if kind == "rule":
        _check_rule(rec, add)

    if known_ids is not None:
        for field, ref_kind in spec["refs"].items():
            value = rec.get(field)
            if isinstance(value, str) and value and value not in known_ids.get(ref_kind, set()):
                add(field, "悬空引用：%s 指向不存在的 %s" % (value, ref_kind), "reference")
        for field, ref_kind in spec["list_refs"].items():
            for value in rec.get(field) or []:
                if isinstance(value, str) and value not in known_ids.get(ref_kind, set()):
                    add(field, "悬空引用：%s 指向不存在的 %s" % (value, ref_kind), "reference")
        for field, (inner, ref_kind) in (spec.get("dict_refs") or {}).items():
            for entry in rec.get(field) or []:
                if not isinstance(entry, dict):
                    add(field, "%s 的每项必须是对象" % field, "reference")
                    continue
                value = entry.get(inner)
                if not isinstance(value, str) or not value:
                    add(field, "%s 的每项需要非空 %s" % (field, inner), "reference")
                elif value not in known_ids.get(ref_kind, set()):
                    add(field, "悬空引用：%s 指向不存在的 %s" % (value, ref_kind), "reference")

    return problems


def _check_condition(condition: Any, where: str, add) -> None:
    """条件语言闭集校验（递归）。未知算子＝数据不合法，不做"忽略继续"。"""
    if not isinstance(condition, dict) or len(condition) != 1:
        add(where, "条件必须是只含一个算子的对象，实际 %r" % (condition,))
        return
    op = list(condition)[0]
    if op not in CONDITION_OPS:
        add(where, "未知条件算子 %r（可用：%s）" % (op, list(CONDITION_OPS)))
        return
    value = condition[op]
    if op in ("all_of", "any_of"):
        if not isinstance(value, list) or not value:
            add(where + "." + op, "all_of/any_of 需要非空条件列表")
            return
        for index, sub in enumerate(value):
            _check_condition(sub, "%s.%s[%d]" % (where, op, index), add)
        return
    if op == "not":
        _check_condition(value, where + ".not", add)
        return
    if op in ("keyword_any", "keyword_all"):
        ok = isinstance(value, list) and value and all(isinstance(v, str) and v for v in value)
    elif op in ("slot_present", "slot_absent"):
        ok = isinstance(value, str) and bool(value)
    else:  # slot_in
        ok = (isinstance(value, dict) and isinstance(value.get("slot"), str)
              and isinstance(value.get("values"), list) and bool(value.get("values")))
    if not ok:
        add(where + "." + op, "算子 %s 的操作数不合法：%r" % (op, value))


def _check_rule(rec: Dict[str, Any], add) -> None:
    when = rec.get("when")
    if when is not None:
        _check_condition(when, "when", add)

    basis = rec.get("basis")
    if not basis:
        add("basis", "规则必须挂依据条款（basis 为空＝无出处，不得进核查路径）")
    if isinstance(basis, list):
        for index, entry in enumerate(basis):
            if not isinstance(entry, dict):
                add("basis", "basis[%d] 必须是对象（含 clause_id 与 gist）" % index)
                continue
            if not entry.get("clause_id") or not entry.get("gist"):
                add("basis", "basis[%d] 缺 clause_id 或 gist（无依据的规则不得进核查）" % index)

    assert_spec = rec.get("assert")
    if not isinstance(assert_spec, dict):
        add("assert", "assert 必须是对象")
        return
    kind = assert_spec.get("kind")
    if kind not in ASSERT_KINDS:
        add("assert.kind", "未知断言算子 %r（可用：%s）" % (kind, sorted(ASSERT_KINDS)))
        return
    require = ASSERT_KINDS[kind]
    for field in require.get("all") or ():
        if not assert_spec.get(field):
            add("assert." + field, "%s 断言需要非空 %s" % (kind, field))
    for field in require.get("threshold") or ():
        if field not in assert_spec:
            add("assert." + field,
                "%s 断言必须显式写出 %s（未核对就写 null，不要省略键）" % (kind, field))
    any_of = require.get("any_of")
    if any_of and not any(assert_spec.get(field) for field in any_of):
        add("assert", "%s 断言需要 %s 至少一项非空" % (kind, " / ".join(any_of)))

    # 阈值纪律：未核对的规则不得携带数值/等级阈值（D11/K14 在规则表上的形态），
    # 反过来声称已核对的规则必须把阈值填上，否则等于空跑。
    if kind in THRESHOLD_KINDS:
        for field in THRESHOLD_FIELDS:
            if field not in assert_spec:
                continue
            value = assert_spec[field]
            if rec.get("status") == "verified":
                if value is None:
                    add("assert." + field,
                        "status=verified 的规则必须给出核对过的 %s" % field)
            elif value is not None:
                add("assert." + field,
                    "status=%s 的规则不得携带 %s=%r：未核对的阈值一律写 null，"
                      "由判定层记「规则不启用」而不是猜一个数" % (
                          rec.get("status"), field, value))


def _check_verified_by(rec: Dict[str, Any], add) -> None:
    status = rec.get("status")
    verified_by = rec.get("verified_by")
    if not isinstance(verified_by, dict):
        add("verified_by", "status=%s 但缺 verified_by（渠道+日期+URL）" % status)
        return
    for field in VERIFIED_BY_REQUIRED:
        value = verified_by.get(field)
        if not value or value == "待补":
            add("verified_by." + field,
                "status=%s 必须填 %s（无出处不得登记为已定位/已核对）" % (status, field))
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
