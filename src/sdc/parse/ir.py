"""参数卡 IR：解析层与判定层之间唯一的交接物（落盘 JSON，口径 K26）。

结构稳定、无时间戳、排序键 —— 同一文档 + 同一解析器版本 ⇒ 字节一致（口径 K8），
所以 IR 可以进测试做回归基线，也可以被 `sdc check`/`sdc checklist` 反复消费而不再碰正则。

设计说明本身**不足以**构成可运行的参数卡（没有几何、没有内力、没有模块归属），
因此 IR 里是 `card_slots`（能等值落进引擎输入词表的那部分）+ `card_gaps`（缺什么），
而不是假装拼出一张完整卡去跑引擎。
"""

import json
import os
from typing import Any, Dict, List, Optional

from .. import __version__
from ..engine.params import MODULE_SLOTS
from ..kb.schema import MODULES
from .errors import IrError
from .slots import SLOT_NAMES, extract_slots, normalize_to_card_slots
from .textio import read_document

IR_KEYS = ("parser_version", "doc", "paragraphs", "slots", "slot_evidence",
           "dropped", "conflicts", "card_slots", "card_dropped")


def build_ir(path: str) -> Dict[str, Any]:
    document = read_document(path)
    extracted = extract_slots(document["paragraphs"])
    card_slots, card_dropped = normalize_to_card_slots(extracted)

    title = document["paragraphs"][0]["text"] if document["paragraphs"] else ""
    return {
        "parser_version": __version__,
        "doc": {
            "name": os.path.basename(path),
            "format": document["format"],
            "encoding": document["encoding"],
            "sha256": document["sha256"],
            "byte_size": document["byte_size"],
            "paragraph_count": document["paragraph_count"],
            "title": title,
        },
        "paragraphs": document["paragraphs"],
        "slots": extracted["slots"],
        "slot_evidence": extracted["slot_evidence"],
        "dropped": extracted["dropped"],
        "conflicts": extracted["conflicts"],
        "card_slots": card_slots,
        "card_dropped": card_dropped,
    }


def write_ir(ir: Dict[str, Any], out_path: str) -> str:
    directory = os.path.dirname(os.path.abspath(out_path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    payload = json.dumps(ir, ensure_ascii=False, indent=2, sort_keys=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload + "\n")
    return out_path


def default_ir_path(doc_path: str) -> str:
    stem = os.path.splitext(os.path.basename(doc_path))[0]
    return os.path.join(".tmp_parse", "%s.ir.json" % stem)


def load_ir(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            ir = json.loads(handle.read())
    except OSError as exc:
        raise IrError("IR 读取失败：%s" % exc)
    except ValueError as exc:
        raise IrError("IR 不是合法 JSON：%s（%s）" % (path, exc))
    validate_ir(ir, where=os.path.basename(path))
    return ir


def validate_ir(ir: Any, where: str = "ir") -> None:
    if not isinstance(ir, dict):
        raise IrError("%s：IR 必须是对象" % where)
    for key in IR_KEYS:
        if key not in ir:
            raise IrError("%s：IR 缺少 %s（请用当前解析层重新生成，判定层不吃手改 IR）" % (
                where, key))
    if not isinstance(ir["doc"], dict) or "sha256" not in ir["doc"]:
        raise IrError("%s：doc 字段不完整" % where)
    if not isinstance(ir["paragraphs"], list):
        raise IrError("%s：paragraphs 必须是列表" % where)
    if ir["doc"].get("paragraph_count") != len(ir["paragraphs"]):
        raise IrError("%s：doc.paragraph_count=%r 与 paragraphs 长度 %d 不一致"
                      "（IR 被截断或手工添加过段落）" % (
                          where, ir["doc"].get("paragraph_count"), len(ir["paragraphs"])))
    for index, para in enumerate(ir["paragraphs"]):
        if not isinstance(para, dict) or not isinstance(para.get("text"), str):
            raise IrError("%s：paragraphs[%d] 需要 {index,text} 结构" % (where, index))
        if para.get("index") != index:
            raise IrError("%s：paragraphs[%d].index=%r 与位置不一致（IR 被手改或截断）" % (
                where, index, para.get("index")))
    for record in ir["slot_evidence"]:
        if not isinstance(record, dict) or record.get("slot") not in SLOT_NAMES:
            raise IrError("%s：slot_evidence 含未知槽位 %r" % (where, record))
    if not isinstance(ir["slots"], dict) or not isinstance(ir["card_slots"], dict):
        raise IrError("%s：slots/card_slots 必须是对象" % where)
    for conflict in ir["conflicts"]:
        if not isinstance(conflict, dict) or not isinstance(conflict.get("values"), list):
            raise IrError("%s：conflicts 结构不合法：%r" % (where, conflict))


def card_gaps(ir: Dict[str, Any], module: Optional[str] = None) -> List[str]:
    """距离可运行参数卡还缺什么（逐模块列出；说明文档天然缺几何与内力）。"""
    modules = [module] if module else list(MODULES)
    have = set(ir["card_slots"])
    out = []  # type: List[str]
    for name in modules:
        if name not in MODULES:
            raise IrError("module %r 不是 5 个验算模块之一" % name)
        missing = sorted(set(MODULE_SLOTS[name]["required"]) - have - {"case_id", "module"})
        out.append("%s 缺少必填槽位：%s（另需 forces）" % (name, ", ".join(missing)))
    return out
