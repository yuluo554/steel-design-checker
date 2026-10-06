"""合成设计说明生成器 v0（plan/05 §五，M1 交付物）。

产出（全部入仓为字节冻结 fixtures，禁止手改；改模板后用同一 seed 整目录重生成）：

    data/synth/groundtruth.json      每份文档的槽位真值 + 段落定位 + 注入期望
    data/synth/injections.json       注入清单汇总（按类型计数，供检出率/误报对账）
    data/synth/docx/SYNTH-xxxx.docx  合成设计说明本体

确定性纪律（口径 K8）：splitmix64 固定 seed、槽位抽取顺序固定、遍历一律 sorted、
产物无时间戳。期望语义（口径 K4）：注入项记 primary，同一注入隐含的连带结论记
also_expect，评测按"文档全部非 pass 集合"对账。
"""

import hashlib
import json
import os
import shutil
from typing import Any, Dict, List, Optional, Tuple

from .docx import build_docx
from .rng import SplitMix64
from .templates import (INJECT_TEMPLATES, INJECTION_TYPES, MISMATCH_BOLT_GRADE,
                        PARAMETER_POOL, SECTIONS, SECTION_HEADINGS, VARIANTS,
                        section_of_injection, slots_used)

DOC_COUNT = 24
CLEAN_COUNT = 12
TITLE = "钢结构设计说明（合成样例，非真实工程）"
DEFAULT_SEED = 20261006

# 每类注入的期望：primary 为直接判定，also_expect 为同一注入隐含的连带结论。
# 规则本体在 M3 落地，届时受 K5 约束（规则 status=pending 只能出 suspicious）。
INJECTION_EXPECT = {
    "weld_class_missing": {
        "rule": "R-WELD-CLASS-001",
        "slot": "weld_class",
        "expect": "abnormal",
        "also_expect": ["焊缝检验要求未写明对应质量等级"],
    },
    "steel_grade_contradiction": {
        "rule": "R-STEEL-GRADE-CONSISTENCY",
        "slot": "grade",
        "expect": "abnormal",
        "also_expect": ["连接板与主体材质不匹配需人工确认"],
    },
    "bolt_grade_mismatch": {
        "rule": "R-BOLT-GRADE-MISMATCH",
        "slot": "bolt_grade",
        "expect": "abnormal",
        "also_expect": ["主受力连接未采用摩擦型高强螺栓"],
    },
}


def _injections_for(index: int) -> List[str]:
    """前 CLEAN_COUNT 份干净，其余按注入类型轮转（顺序固定，可复现）。"""
    if index < CLEAN_COUNT:
        return []
    return [INJECTION_TYPES[(index - CLEAN_COUNT) % len(INJECTION_TYPES)]]


def _draw_values(rng: SplitMix64, injections: List[str]) -> Dict[str, str]:
    values = {}
    for name in sorted(PARAMETER_POOL):
        pool = PARAMETER_POOL[name]
        values[name] = pool[rng.below(len(pool))]

    if "steel_grade_contradiction" in injections:
        # 矛盾注入要求前后牌号不同：主体牌号只在非 grade_alt 候选中取
        candidates = [g for g in PARAMETER_POOL["grade"] if g != values["grade_alt"]]
        values["grade"] = candidates[rng.below(len(candidates))]
    if "bolt_grade_mismatch" in injections:
        values["bolt_grade"] = MISMATCH_BOLT_GRADE
    return values


def _template_for(section: str, rng: SplitMix64, injections: List[str]) -> str:
    if "weld_class_missing" in injections and section == "welding":
        return INJECT_TEMPLATES["weld_class_missing"]
    if "bolt_grade_mismatch" in injections and section == "bolt":
        return INJECT_TEMPLATES["bolt_grade_mismatch_main"]
    if "steel_grade_contradiction" in injections and section == "construct":
        return INJECT_TEMPLATES["steel_grade_contradiction"]
    variants = VARIANTS[section]
    return variants[rng.below(len(variants))]


def build_document(index: int, rng: SplitMix64) -> Tuple[str, List[str], Dict[str, Any]]:
    doc_id = "SYNTH-%04d" % index
    injections = _injections_for(index)
    values = _draw_values(rng, injections)

    paragraphs = [TITLE]
    evidence = []  # type: List[Dict[str, Any]]
    marks = []  # type: List[Dict[str, Any]]

    for section in SECTIONS:
        paragraphs.append(SECTION_HEADINGS[section])
        template = _template_for(section, rng, injections)
        text = template.format(**values)
        paragraphs.append(text)
        body_index = len(paragraphs) - 1

        for slot in slots_used(template):
            evidence.append({"slot": slot, "value": values[slot],
                             "para": body_index, "section": section})

        for injection in injections:
            if section_of_injection(injection) != section:
                continue
            expect = INJECTION_EXPECT[injection]
            marks.append({"type": injection, "para": body_index, "section": section,
                          "primary": dict(expect, para=body_index)})

    truth = {
        "doc_id": doc_id,
        "file": "docx/%s.docx" % doc_id,
        "title": TITLE,
        "clean": not injections,
        "paragraph_count": len(paragraphs),
        # slots 只收文档真正写明的取值；"缺标注"类注入下该槽位不出现在这里
        "slots": dict(sorted((e["slot"], e["value"]) for e in evidence)),
        "slot_evidence": sorted(evidence, key=lambda e: (e["para"], e["slot"])),
        "injections": marks,
        "expected_non_pass": sorted(set(
            [m["primary"]["rule"] for m in marks]
            + [text for m in marks for text in m["primary"]["also_expect"]]
        )),
    }
    return doc_id, paragraphs, truth


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _dump(payload: Any) -> bytes:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    return (text + "\n").encode("utf-8")


def _build_all(seed: int) -> List[Tuple[str, bytes, Dict[str, Any]]]:
    rng = SplitMix64(seed)
    produced = []
    for index in range(DOC_COUNT):
        _doc_id, paragraphs, truth = build_document(index, rng)
        payload = build_docx(paragraphs)
        truth["sha256"] = _sha256(payload)
        produced.append((truth["file"], payload, truth))
    return produced


def _injection_summary(produced) -> Dict[str, Any]:
    counts = dict((t, 0) for t in INJECTION_TYPES)
    injected = 0
    for _rel, _payload, truth in produced:
        if truth["injections"]:
            injected += 1
        for mark in truth["injections"]:
            counts[mark["type"]] += 1
    return counts, injected


def corpus_payloads(seed: int) -> Dict[str, bytes]:
    """语料的唯一构造入口：相对路径 -> 字节。生成与对账共用，避免两套逻辑漂移。"""
    produced = _build_all(seed)
    counts, injected = _injection_summary(produced)

    files = dict((rel, payload) for rel, payload, _truth in produced)
    files["groundtruth.json"] = _dump({
        "seed": seed,
        "doc_count": len(produced),
        "documents": sorted((truth for _rel, _p, truth in produced),
                            key=lambda t: t["doc_id"]),
    })
    files["injections.json"] = _dump({
        "seed": seed,
        "doc_count": len(produced),
        "clean_count": len(produced) - injected,
        "injected_count": injected,
        "injection_counts": counts,
        "generator": "sdc.synth v0",
        "documents": sorted([{
            "doc_id": truth["doc_id"],
            "file": truth["file"],
            "sha256": truth["sha256"],
            "clean": truth["clean"],
            "injection_types": sorted(m["type"] for m in truth["injections"]),
            "expected_non_pass": truth["expected_non_pass"],
        } for _rel, _p, truth in produced], key=lambda d: d["doc_id"]),
    })
    return files


def generate_corpus(out_dir: str, seed: int = DEFAULT_SEED) -> Dict[str, Any]:
    """整目录重生成：先清掉旧的 docx 与 json，再按固定顺序写回。"""
    if os.path.isdir(out_dir):
        for name in sorted(os.listdir(out_dir)):
            path = os.path.join(out_dir, name)
            if name.endswith(".json") and os.path.isfile(path):
                os.remove(path)
            elif name == "docx" and os.path.isdir(path):
                shutil.rmtree(path)
    os.makedirs(os.path.join(out_dir, "docx"), exist_ok=True)

    files = corpus_payloads(seed)
    for rel in sorted(files):
        target = os.path.join(out_dir, *rel.split("/"))
        with open(target, "wb") as handle:
            handle.write(files[rel])

    with open(os.path.join(out_dir, "injections.json"), "rb") as handle:
        return json.loads(handle.read().decode("utf-8"))


def corpus_files(data_dir: str) -> List[str]:
    """synth 目录下已有产物的相对路径（排序）。"""
    root = os.path.join(data_dir, "synth")
    found = []
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(dirs)
        for name in sorted(files):
            rel = os.path.relpath(os.path.join(current, name), root)
            found.append(rel.replace(os.sep, "/"))
    return sorted(found)


def compare_corpus(data_dir: str, seed: Optional[int] = None) -> List[str]:
    """固定 seed 重新生成的语料与仓内冻结语料逐字节对账，返回不一致清单。"""
    seed = DEFAULT_SEED if seed is None else seed
    root = os.path.join(data_dir, "synth")
    expected = corpus_payloads(seed)

    present = set(corpus_files(data_dir))
    wanted = set(expected)
    problems = []

    for missing in sorted(wanted - present):
        problems.append("缺失产物：synth/%s" % missing)
    for extra in sorted(present - wanted):
        problems.append("语料目录有未登记文件（不得手改或手工添加）：synth/%s" % extra)
    for rel in sorted(wanted & present):
        with open(os.path.join(root, *rel.split("/")), "rb") as handle:
            on_disk = handle.read()
        if on_disk != expected[rel]:
            problems.append("字节不一致：synth/%s（应由生成器重生成，不要手改）" % rel)
    return problems
