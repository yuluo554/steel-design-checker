"""解析层：docx/文本读取、槽位抽取、IR 校验（M3）。

抽取侧的三条纪律都要有测试承接：类目隔离（K28）、白名单外丢弃但留痕、同义写法不做
猜测式归一；另外 IR 是判定层唯一的输入，被手改/截断必须拒收。
"""

import io
import json
import os
import zipfile

import pytest

from sdc.parse import build_ir, card_gaps, extract_slots, load_ir, write_ir
from sdc.parse.errors import IrError, ParseError
from sdc.parse.slots import normalize_to_card_slots
from sdc.parse.textio import docx_paragraphs, plain_text_paragraphs, read_document

HERE = os.path.dirname(os.path.abspath(__file__))
SYNTH_DOCX = os.path.join(HERE, os.pardir, "data", "synth", "docx")


def _paragraphs(*texts):
    return [{"index": i, "line": i + 1, "text": t} for i, t in enumerate(texts)]


# ---------------------------------------------------------------------------
# 文档读取
# ---------------------------------------------------------------------------

def test_read_synth_docx_paragraphs():
    doc = read_document(os.path.join(SYNTH_DOCX, "SYNTH-0000.docx"))
    assert doc["format"] == "docx"
    assert doc["paragraph_count"] == 11
    assert doc["paragraphs"][0]["text"].startswith("钢结构设计说明")
    assert len(doc["sha256"]) == 64


def test_docx_table_rows_become_paragraphs():
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           '<w:body><w:tbl><w:tr><w:tc><w:p><w:r><w:t>焊脚</w:t></w:r></w:p></w:tc>'
           '<w:tc><w:p><w:r><w:t>8mm</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
           '<w:p><w:r><w:t>正文段</w:t></w:r></w:p></w:body></w:document>')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", xml)
    assert docx_paragraphs(buffer.getvalue()) == ["焊脚 | 8mm", "正文段"]


def test_docx_without_document_part_or_broken_zip_is_rejected():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/footer.xml", "<x/>")
    with pytest.raises(ParseError):
        docx_paragraphs(buffer.getvalue())
    with pytest.raises(ParseError):
        docx_paragraphs(b"not a zip at all")


def test_text_falls_back_to_gb18030_and_records_encoding():
    payload = "钢材牌号Q355B，质量等级B级。\n".encode("gb18030")
    paragraphs, encoding = plain_text_paragraphs(payload)
    assert encoding == "gb18030"
    assert paragraphs == ["钢材牌号Q355B，质量等级B级。"]


def test_blank_lines_are_skipped_in_text_mode():
    paragraphs, encoding = plain_text_paragraphs("第一段\n\n\n第二段\n".encode("utf-8"))
    assert encoding == "utf-8-sig"
    assert paragraphs == ["第一段", "第二段"]


def test_unsupported_suffix_is_rejected(tmp_path):
    path = os.path.join(str(tmp_path), "x.pdf")
    with open(path, "wb") as handle:
        handle.write(b"%PDF-1.4")
    with pytest.raises(ParseError):
        read_document(path)


# ---------------------------------------------------------------------------
# 槽位抽取
# ---------------------------------------------------------------------------

def test_category_isolation_blocks_out_of_scope_numbers():
    ex = extract_slots(_paragraphs(
        "构件间距为 1.50h 时不影响判断。",       # 无防火/耐火关键词
        "螺栓间距 8.8 系列不作数。"))            # 无螺栓等级写法（"8.8 系"）
    slots = {item["slot"] for item in ex["slot_evidence"]}
    assert "fire_hour" not in slots
    assert "bolt_grade" not in slots


def test_secondary_weld_class_statement_is_not_merged_into_primary_slot():
    """"其余对接焊缝不低于三级"是另一条要求，收进 weld_class 会凭空造出前后矛盾。"""
    ex = extract_slots(_paragraphs(
        "直接承受动力荷载且垂直于焊缝受力方向的对接焊缝质量等级为一级，"
        "其余对接焊缝不低于三级；角焊缝焊脚尺寸不小于8mm。"))
    assert [i["value"] for i in ex["slot_evidence"] if i["slot"] == "weld_class"] == ["一级"]
    assert ex["conflicts"] == []


def test_unknown_steel_grade_is_kept_as_fact_and_dropped_from_card():
    ex = extract_slots(_paragraphs("次要构件采用Q460B。"))
    card, dropped = normalize_to_card_slots(ex)
    assert ex["slots"]["grade"] == "Q460B"
    assert "steel_grade" not in card
    assert any("Q460" in d["reason"] for d in dropped), dropped


def test_surface_synonyms_are_not_guessed():
    """喷砂后涂富锌漆 ≠ 涂富锌漆后喷砂（工序顺序不同），只做完全等值归一。"""
    mappable, dropped_a = normalize_to_card_slots(
        extract_slots(_paragraphs("摩擦面处理为涂富锌漆后喷砂。")))
    assert mappable.get("surface_treatment") == "涂富锌漆后喷砂"
    unmapped, dropped_b = normalize_to_card_slots(
        extract_slots(_paragraphs("摩擦面处理为喷砂后涂富锌漆。")))
    assert "surface_treatment" not in unmapped
    assert any("未做同义猜测" in d["reason"] for d in dropped_b), dropped_b


def test_data_side_quantity_never_reaches_card_slots():
    """抗滑移系数 μ 属数据侧量（口径 K19），抽到了也不能进参数卡。"""
    ex = extract_slots(_paragraphs("摩擦面处理为喷砂，抗滑移系数取0.40。"))
    card, _dropped = normalize_to_card_slots(ex)
    assert ex["slots"]["mu"] == "0.40"
    assert "mu" not in card and "slip_factor_mu" not in card


def test_numeric_domain_rejects_absurd_value_and_keeps_evidence():
    ex = extract_slots(_paragraphs("角焊缝最小焊脚4000mm。"))
    assert ex["slot_evidence"] == []
    assert any(d["slot"] == "min_hf" and "取值域外" in d["reason"] for d in ex["dropped"])


def test_grade_conflict_is_reported_and_removed_from_card():
    ex = extract_slots(_paragraphs("主体构件采用Q420D。", "连接板采用Q235B。"))
    conflict = ex["conflicts"][0]
    assert conflict["slot"] == "grade"
    assert conflict["values"] == ["Q235B", "Q420D"]
    assert conflict["paras"] == [0, 1]
    card, dropped = normalize_to_card_slots(ex)
    assert "steel_grade" not in card
    assert any("同槽位多值" in d["reason"] for d in dropped)


def test_extraction_is_deterministic_and_sorted():
    texts = ("主体钢材采用Q355B，质量等级B级。",
             "对接焊缝中受拉者按一级检验，受压及受剪者按三级检验；角焊缝焊脚取8mm。",
             "高强螺栓摩擦型连接的性能等级为10.9，摩擦面喷砂，设计抗滑移系数0.35。")
    first = json.dumps(extract_slots(_paragraphs(*texts)), sort_keys=True, ensure_ascii=False)
    second = json.dumps(extract_slots(_paragraphs(*texts)), sort_keys=True, ensure_ascii=False)
    assert first == second
    evidence = extract_slots(_paragraphs(*texts))["slot_evidence"]
    assert evidence == sorted(evidence, key=lambda r: (r["para"], r["slot"], r["value"]))


# ---------------------------------------------------------------------------
# IR 落盘与校验
# ---------------------------------------------------------------------------

def test_ir_round_trip_and_gap_list(tmp_path):
    source = os.path.join(SYNTH_DOCX, "SYNTH-0013.docx")
    ir = build_ir(source)
    target = write_ir(ir, os.path.join(str(tmp_path), "a.ir.json"))
    again = load_ir(target)
    assert again == ir
    assert "steel_grade" not in again["card_slots"]        # 牌号前后矛盾 ⇒ 不进卡
    gaps = card_gaps(again, "fillet_weld")
    assert len(gaps) == 1 and "thickness_group" in gaps[0]
    with pytest.raises(IrError):
        card_gaps(again, "no_such_module")


def test_ir_is_byte_stable(tmp_path):
    source = os.path.join(SYNTH_DOCX, "SYNTH-0012.docx")
    first = write_ir(build_ir(source), os.path.join(str(tmp_path), "1.ir.json"))
    second = write_ir(build_ir(source), os.path.join(str(tmp_path), "2.ir.json"))
    with open(first, "rb") as a, open(second, "rb") as b:
        assert a.read() == b.read()


def test_hand_edited_ir_is_rejected(tmp_path):
    ir = build_ir(os.path.join(SYNTH_DOCX, "SYNTH-0000.docx"))
    path = write_ir(ir, os.path.join(str(tmp_path), "x.ir.json"))

    broken = json.loads(json.dumps(ir))
    broken["paragraphs"] = broken["paragraphs"][:3]        # 截断后 index 与位置不一致
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(broken, ensure_ascii=False))
    with pytest.raises(IrError):
        load_ir(path)

    forged = json.loads(json.dumps(ir))
    forged["slot_evidence"].append({"slot": "made_up", "value": "x", "para": 1, "offset": 0})
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(forged, ensure_ascii=False))
    with pytest.raises(IrError):
        load_ir(path)

    missing = json.loads(json.dumps(ir))
    del missing["conflicts"]
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(missing, ensure_ascii=False))
    with pytest.raises(IrError):
        load_ir(path)
