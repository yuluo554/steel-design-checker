"""规则引擎：IR（参数卡槽位证据）+ 规则表 → 三级判定清单。

判定层**不对文档执行正则**（口径 K26：解析层与判定层分进程，正则崩溃不能连带打挂评测；
模式编译随 `parse.slots` 的 import 发生，实测见 `.tmp_verify/m4/k26-import-graph/`），
所以这里只有三种文本操作：子串命中、取值等值、数值比较。规则表的条件语言是闭集
（`kb.schema.CONDITION_OPS` / `ASSERT_KINDS`），未知算子在 schema 层就判数据不合法。

规则知识全部来自 `data/rules/`，代码里没有任何规范结论；档位由 `gate.py` 的矩阵决定
（口径 K5），本文件只负责"文档里到底有没有这件事"。
"""

from typing import Any, Dict, List, Optional

from .. import __version__
from ..engine.core import DISCLAIMER
from ..kb.fingerprint import data_fingerprint
from ..parse.slots import canonical_value
from .gate import effective_status, level_for

EVIDENCE_TEXT_LIMIT = 160


class RuleError(Exception):
    """规则表在运行期暴露的结构问题（schema 未拦住的那种）。"""


def _truncate(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= EVIDENCE_TEXT_LIMIT else text[:EVIDENCE_TEXT_LIMIT] + "…"


def _values(unit: Dict[str, Any], slot: str) -> List[str]:
    return sorted(set(item["value"] for item in unit["evidence"] if item["slot"] == slot))


def _dropped(unit: Dict[str, Any], slot: str) -> List[Dict[str, Any]]:
    return [item for item in unit["dropped"] if item.get("slot") == slot]


def build_units(ir: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """document 级与 paragraph 级作用域单元（同一份 IR 两种视角，规则各取其一）。"""
    evidence = ir["slot_evidence"]
    dropped = ir["dropped"]
    paragraphs = ir["paragraphs"]

    document = {
        "para": None,
        "text": "\n".join(p["text"] for p in paragraphs),
        "evidence": evidence,
        "dropped": dropped,
        "conflicts": sorted((c["slot"] for c in ir["conflicts"])),
    }

    by_para = {}  # type: Dict[int, Dict[str, Any]]
    for para in paragraphs:
        by_para[para["index"]] = {
            "para": para["index"],
            "text": para["text"],
            "evidence": [e for e in evidence if e["para"] == para["index"]],
            "dropped": [d for d in dropped if d.get("para") == para["index"]],
            "conflicts": [],
        }
    for unit in by_para.values():
        seen = {}  # type: Dict[str, List[str]]
        for item in unit["evidence"]:
            seen.setdefault(item["slot"], []).append(item["value"])
        unit["conflicts"] = sorted(slot for slot, values in seen.items()
                                   if len(set(values)) > 1)

    return {"document": [document], "paragraph": [by_para[key] for key in sorted(by_para)]}


def condition_ok(condition: Dict[str, Any], unit: Dict[str, Any]) -> bool:
    op = list(condition)[0]
    value = condition[op]

    if op == "keyword_any":
        return any(kw in unit["text"] for kw in value)
    if op == "keyword_all":
        return all(kw in unit["text"] for kw in value)
    if op == "slot_present":
        return bool(_values(unit, value))
    if op == "slot_absent":
        return not _values(unit, value)
    if op == "slot_in":
        return any(v in _values(unit, value["slot"]) for v in value["values"])
    if op == "all_of":
        return all(condition_ok(sub, unit) for sub in value)
    if op == "any_of":
        return any(condition_ok(sub, unit) for sub in value)
    if op == "not":
        return not condition_ok(value, unit)
    raise RuleError("未知条件算子 %r" % op)


def judge_assert(assert_spec: Dict[str, Any], unit: Dict[str, Any], status: str) -> Dict[str, Any]:
    """返回 {"outcome": ..., "detail": ...}；outcome=none 表示这一单元没问题。"""
    kind = assert_spec["kind"]

    if kind == "presence":
        # presence = 列出的槽位**全部**要写明（"牌号与质量等级缺标注"不能因为只写了牌号就算过）；
        # keyword_any 是备用的等价表述通道（文档用别的写法表达了同一件事，不算缺标注）。
        slots = assert_spec.get("slots") or []
        keywords = assert_spec.get("keyword_any") or []
        absent = [slot for slot in slots if not _values(unit, slot)]
        if not absent or any(kw in unit["text"] for kw in keywords):
            return {"outcome": "none", "detail": ""}
        ambiguous = [slot for slot in absent if _dropped(unit, slot)]
        if ambiguous:
            return {"outcome": "ambiguous",
                    "detail": "文档写了 %s，但取值不合法/不在词表（见 IR dropped），需人工确认"
                              % ", ".join(sorted(ambiguous))}
        return {"outcome": "missing",
                "detail": "应有标注未写明：%s" % ", ".join(sorted(absent))}

    if kind == "cross_param":
        # cross_param = 备选信息**至少给一项**（连接形式/摩擦面/抗滑移任一写明即不算缺）
        slots = assert_spec.get("require_any_slots") or []
        keywords = assert_spec.get("require_any_keywords") or []
        if any(_values(unit, slot) for slot in slots) or any(kw in unit["text"]
                                                            for kw in keywords):
            return {"outcome": "none", "detail": ""}
        wanted = ", ".join(sorted(slots + keywords))
        return {"outcome": "missing", "detail": "交叉参数未写明任一项：%s" % wanted}

    if kind == "consistency":
        slot = assert_spec["slot"]
        if slot in unit["conflicts"]:
            values = sorted(set(item["value"] for item in unit["evidence"]
                                if item["slot"] == slot))
            return {"outcome": "mismatch",
                    "detail": "同一参数前后取值不一致：%s = %s" % (slot, ", ".join(values))}
        return {"outcome": "none", "detail": ""}

    if kind == "ordinal_min":
        threshold = assert_spec.get("min")
        if threshold is None:
            return {"outcome": "disabled",
                    "detail": "阈值（%s）未核对，status=%s，规则不启用" % (
                        assert_spec["slot"], status)}
        order = assert_spec["order"]
        if threshold not in order:
            raise RuleError("ordinal_min 的 min=%r 不在 order=%s 内" % (threshold, order))
        values = _values(unit, assert_spec["slot"])
        unknown = [v for v in values if v not in order]
        if unknown:
            return {"outcome": "ambiguous",
                    "detail": "取值 %s 不在已定义的等级序内，无法比较" % ", ".join(unknown)}
        if not values:
            return {"outcome": "none", "detail": ""}
        worst = min(order.index(v) for v in values)
        if worst < order.index(threshold):
            return {"outcome": "mismatch",
                    "detail": "取值 %s 低于要求的 %s（等级序：%s）" % (
                        ", ".join(values), threshold, " < ".join(order))}
        return {"outcome": "none", "detail": ""}

    if kind in ("numeric_min", "numeric_max"):
        bound = assert_spec.get("bound")
        if bound is None:
            return {"outcome": "disabled",
                    "detail": "限值（%s）未核对，status=%s，规则不启用" % (
                        assert_spec["slot"], status)}
        values = _values(unit, assert_spec["slot"])
        if not values:
            return {"outcome": "none", "detail": ""}
        numbers = []
        for raw in values:
            canon = canonical_value(assert_spec["slot"], raw)
            if canon is None:
                return {"outcome": "ambiguous",
                        "detail": "取值 %r 不是可比较的数值" % raw}
            numbers.append((raw, canon))
        breaches = [raw for raw, canon in numbers
                    if (canon < float(bound) if kind == "numeric_min"
                        else canon > float(bound))]
        if breaches:
            op = "<" if kind == "numeric_min" else ">"
            return {"outcome": "mismatch",
                    "detail": "取值 %s %s 限值 %s（%s），未满足" % (
                        ", ".join(breaches), op, bound, assert_spec.get("unit", ""))}
        return {"outcome": "none", "detail": ""}

    raise RuleError("未知断言算子 %r" % kind)


def _rule_gate_hit(rule: Dict[str, Any], document_unit: Dict[str, Any]) -> bool:
    """类目隔离：规则声明的门控关键词一个都不在文档里 ⇒ 规则不参与本文档（不是漏检）。"""
    keywords = rule.get("gate_keywords") or []
    if not keywords:
        return True
    return any(kw in document_unit["text"] for kw in keywords)


def run_rules(kb, ir: Dict[str, Any]) -> Dict[str, Any]:
    """规则表 × IR → 核查报告（findings / not_activated / 计数 / 文档级结论）。"""
    units = build_units(ir)
    document_unit = units["document"][0]
    findings = []  # type: List[Dict[str, Any]]
    not_activated = []  # type: List[Dict[str, Any]]

    rules = [r for r in kb.records.get("rule", []) if isinstance(r, dict)]
    for rule in sorted(rules, key=lambda r: str(r.get("id", ""))):
        rule_id = str(rule.get("id", ""))

        if not _rule_gate_hit(rule, document_unit):
            not_activated.append({
                "rule_id": rule_id, "reason": "类目隔离：文档未出现规则关键词 %s"
                                              % list(rule.get("gate_keywords") or [])})
            continue

        when = rule.get("when")
        assert_spec = rule.get("assert") or {}
        if "kind" not in assert_spec:
            raise RuleError("规则 %s 的 assert 缺 kind" % rule_id)
        scope = rule.get("scope", "document")
        status, basis_detail = effective_status(kb, rule)

        hits = []  # type: List[Dict[str, Any]]
        disabled = None  # type: Optional[str]
        for unit in units["paragraph" if scope == "paragraph" else "document"]:
            if when is not None and not condition_ok(when, unit):
                continue
            verdict = judge_assert(assert_spec, unit, status)
            outcome = verdict["outcome"]
            if outcome == "none":
                continue
            if outcome == "disabled":
                disabled = verdict["detail"]
                continue
            level = level_for(rule.get("check_type", ""), outcome, status)
            if level is None:
                not_activated.append({"rule_id": rule_id,
                                      "reason": "闸门表规定 %s/%s 不出结论" % (
                                          rule.get("check_type"), status)})
                continue
            hits.append({"level": level, "outcome": outcome, "detail": verdict["detail"],
                         "para": unit["para"], "text": _truncate(unit["text"]),
                         "values": sorted(set(item["value"] for item in unit["evidence"]))})

        if disabled and not hits:
            not_activated.append({"rule_id": rule_id, "reason": disabled})
            continue

        if not hits:
            continue

        # 同一规则的多处命中合成一条 finding（重复检出会打挂误报口径，plan/05 §五"互斥坑"）
        clause_ids = sorted(set(b.get("clause_id", "") for b in (rule.get("basis") or [])
                                if isinstance(b, dict)))
        paras = sorted(set(hit["para"] for hit in hits if hit["para"] is not None))
        levels = sorted(set(hit["level"] for hit in hits))
        findings.append({
            "rule_id": rule_id,
            "name": rule.get("name", ""),
            "check_type": rule.get("check_type", ""),
            "outcome": hits[0]["outcome"],
            "level": "abnormal" if "abnormal" in levels else "suspicious",
            "status": status,
            "basis": basis_detail,
            "clause_ids": clause_ids,
            "mandatory": _mandatory_of(kb, clause_ids),
            "detail": "；".join(sorted(set(hit["detail"] for hit in hits))),
            "paras": paras,
            "evidence": [{"para": hit["para"], "text": hit["text"]} for hit in hits],
            "suggestion": rule.get("suggestion", ""),
            "also_expect": sorted(set(rule.get("also_expect") or [])),
        })

    findings.sort(key=lambda f: (f["level"] != "abnormal", f["rule_id"], f["paras"]))
    counts = {
        "abnormal": sum(1 for f in findings if f["level"] == "abnormal"),
        "suspicious": sum(1 for f in findings if f["level"] == "suspicious"),
    }
    conclusion = ("abnormal" if counts["abnormal"] else
                  "suspicious" if counts["suspicious"] else "pass")

    # 强制性条文联动提示（口径 K16：清单由数据侧 mandatory 标记驱动，代码不写死 7 条）
    mandatory_hits = sorted(set(cid for f in findings for cid in f["mandatory"]))

    return {
        "doc": ir["doc"],
        "rules_total": len(rules),
        "findings": findings,
        "not_activated": not_activated,
        "mandatory_clause_ids": mandatory_hits,
        "counts": counts,
        "conclusion": conclusion,
        "meta": {"engine_version": __version__,
                 "data_fingerprint": data_fingerprint(kb.data_dir)},
        "disclaimer": DISCLAIMER,
    }


def _mandatory_of(kb, clause_ids: List[str]) -> List[str]:
    index = kb.by_id("clause")
    return sorted(set(cid for cid in clause_ids
                      if isinstance(index.get(cid), dict)
                      and index[cid].get("mandatory") is True))


def findings_tokens(report: Dict[str, Any]) -> List[str]:
    """把报告摊成"文档全部非 pass 集合"（口径 K4 的对账单位）。

    一条 finding 贡献它的 rule_id 与 `also_expect` 文本：注入项的连带结论因此不会被
    当成误报（plan/05 §五 真值语义）。
    """
    tokens = []  # type: List[str]
    for finding in report["findings"]:
        tokens.append(finding["rule_id"])
        tokens.extend(finding.get("also_expect") or [])
    return sorted(set(tokens))
