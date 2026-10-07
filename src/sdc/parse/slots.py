"""槽位抽取：正则 + 输入词表 + 取值域校验（白名单外丢弃，但留痕）。

这里是**文档体例**知识（设计说明里槽位通常怎么写），不是规范事实，所以词表与式体
留在代码里而不是 `data/`：`data/` 只放"已与渠道核对的规范内容"（口径 D06/K15）。
输入词表复用 `sdc.engine.params`，避免解析侧与引擎侧各长一套枚举（口径 K24）。

两条容易踩的坑（plan/05 §五"互斥坑"）已在设计上处理：

- **作用域限定的等级表述不进主槽位**：如"其余对接焊缝不低于三级""受压及受剪者按三级检验"
  是另一条要求，若一起收进 `weld_class` 就会凭空造出"前后矛盾"。抽取式因此只认
  主语明确的写法（"对接焊缝质量等级为/取 X""受拉者按 X 检验"）。
- **同义写法不做猜测式归一**：`喷砂后涂富锌漆` 与引擎词表的 `涂富锌漆后喷砂` 字面顺序不同、
  工序也不同，绝不归一；归一只做**完全等值**映射，其余进 `dropped` 留痕。
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from ..engine.params import (BOLT_GRADES, QUALITY_CLASSES, STEEL_GRADES,
                             SURFACE_TREATMENTS, WELD_QUALITY)
from .errors import ParseError

# ---------------------------------------------------------------------------
# 输入词表：文档侧取值
# ---------------------------------------------------------------------------

GRADE_RE = re.compile(r"Q\s*(\d{3})\s*([A-E])?")
WELD_CLASS_VALUES = WELD_QUALITY
BOLT_GRADE_VALUES = BOLT_GRADES
QUALITY_CLASS_VALUES = QUALITY_CLASSES
STEEL_GRADE_VALUES = STEEL_GRADES
SURFACE_VALUES = SURFACE_TREATMENTS

# 数值槽位的**取值域**只做格式/物理合理性检查（是不是一个像样的焊脚尺寸），
# 不含任何规范限值判断——规范限值属规则表（data/rules/），未核对一律不出数值（D11/K14）。
NUMERIC_DOMAIN = {
    "min_hf": (0.0, 1000.0, "mm"),
    "mu": (0.0, 1.0, "无量纲"),
    "fire_hour": (0.0, 100.0, "h"),
}

# 文本型槽位的长度上限：超过这个数基本就是整句被吞进来了，丢弃并留痕，不当作取值。
MAX_TEXT_LEN = 24

# 抽取式：(槽位, 编译后正则)。正则只在段落命中该槽位 `only_if_text` 关键词后才会被采纳。
PATTERNS = (
    ("grade", GRADE_RE),
    ("qclass", re.compile(r"质量等级\s*([A-E])\s*级|（质量等级\s*([A-E])\s*）")),
    ("weld_class", re.compile(
        r"对接焊缝(?:的)?质量等级\s*[为取是]\s*(一级|二级|三级)"
        r"|受拉者按\s*(一级|二级|三级)\s*(?:检验|执行)"
        r"|对接焊缝中受拉者按\s*(一级|二级|三级)")),
    ("min_hf", re.compile(r"焊脚[^0-9\n]{0,8}(\d+(?:\.\d+)?)\s*mm")),
    ("bolt_grade", re.compile(
        r"(?<![\d.])(\d{1,2}\.\d)\s*级(?=\s*(?:高强度|高强|螺栓|普通|C))"
        r"|螺栓(?:选用|采用|等级为)\s*(\d{1,2}\.\d)\s*级?"
        r"|(?:性能等级|螺栓等级|等级)为\s*(\d{1,2}\.\d)(?![\d.])")),
    ("surface", re.compile(r"摩擦面[^，；。]{0,30}")),
    ("mu", re.compile(r"抗滑移系数[^0-9\n]{0,8}(\d+(?:\.\d+)?)")),
    ("coating", re.compile(
        r"(?:防腐按|涂装体系为|涂装为|除锈后采用)\s*([^，；。]{3,60}?)(?=体系|，|；|。)")),
    ("fire_hour", re.compile(
        r"耐火极限[^0-9\n]{0,8}(\d+(?:\.\d+)?)\s*(?:h|小时)"
        r"|(\d+(?:\.\d+)?)\s*(?:h|小时)[^，；。\n]{0,6}耐火极限")),
)

# 类目隔离（口径 K28）：段落必须命中关键词，该槽位的抽取式才被采纳。
# 空元组表示"取值形式本身已足够特定"（Q345 这种串不会别处出现）。
ONLY_IF_TEXT = {
    "grade": ("钢", "构件", "牌号", "材质", "连接板", "螺栓", "焊缝", "节点"),
    "qclass": ("钢", "质量等级", "构件", "材质"),
    "weld_class": ("焊缝", "焊接"),
    "min_hf": ("焊脚", "角焊缝"),
    "bolt_grade": ("螺栓",),
    "surface": ("摩擦面", "抗滑移"),
    "mu": ("抗滑移", "摩擦面"),
    "coating": ("防腐", "涂装", "涂层", "除锈"),
    "fire_hour": ("防火", "耐火"),
}

SLOT_NAMES = tuple(sorted(ONLY_IF_TEXT))

# 文档槽位 → 参数卡槽位。只有能**完全等值**落进引擎输入词表的才映射；
# mu（抗滑移系数）属数据侧量（口径 K19），永不进参数卡。
CARD_SLOT_MAP = {
    "weld_class": "weld_quality_class",
    "bolt_grade": "bolt_grade",
    "surface": "surface_treatment",
}

_SURFACE_PREFIXES = ("处理方式为", "处理方式", "处理为", "处理后应保持", "处理状态为",
                     "状态为", "方式为", "处理", "为", "取", "采用", "是")
_SURFACE_SUFFIXES = ("状态", "处理", "要求")


def canonical_value(slot: str, raw: str) -> Optional[float]:
    """数值槽位的可比取值；非数值槽位返回 None（按字符串等值比较）。

    真值侧与解析侧共用这一个口径，避免"两边各套规范化"造成假的字段不匹配。
    """
    if slot not in NUMERIC_DOMAIN:
        return None
    text = raw.strip()
    match = re.match(r"^(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    return float(match.group(1))


def _strip_surface(clause: str) -> str:
    text = clause.split("摩擦面", 1)[-1] if "摩擦面" in clause else clause
    for prefix in _SURFACE_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    for suffix in _SURFACE_SUFFIXES:
        if text.endswith(suffix) and len(text) > len(suffix):
            text = text[:-len(suffix)]
            break
    return text.strip("，；。、 ")


def _matches_for(slot: str, pattern: "re.Pattern", text: str) -> List[Tuple[str, int]]:
    """一个段落里该槽位的所有候选 (取值文本, 起始偏移)。"""
    out = []  # type: List[Tuple[str, int]]
    for match in pattern.finditer(text):
        if slot == "surface":
            value = _strip_surface(match.group(0))
            start = match.start()
        elif slot == "grade":
            value = "Q%s%s" % (match.group(1), match.group(2) or "")
            start = match.start()
        elif slot == "qclass":
            value = match.group(1) or match.group(2) or ""
            start = match.start()
        else:
            value, start = "", match.start()
            for group_index, group in enumerate(match.groups(), start=1):
                if group:
                    value, start = group, match.start(group_index)
                    break
        if value:
            out.append((value, start))
    return out


def _domain_ok(slot: str, value: str) -> bool:
    if slot not in NUMERIC_DOMAIN:
        return True
    low, high, _unit = NUMERIC_DOMAIN[slot]
    canon = canonical_value(slot, value)
    return canon is not None and low < canon < high


def extract_slots(paragraphs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """段落 → 槽位证据 / 丢弃留痕 / 同槽位多值冲突。

    返回值全部排序，同一输入必得同一输出（口径 K8）。
    """
    evidence = []  # type: List[Dict[str, Any]]
    dropped = []  # type: List[Dict[str, Any]]

    for para in paragraphs:
        index = para["index"]
        text = para["text"]
        for slot, pattern in PATTERNS:
            keywords = ONLY_IF_TEXT[slot]
            if keywords and not any(kw in text for kw in keywords):
                continue  # 类目隔离：段落不含该主题的用词，该槽位的抽取式不参与（K28）
            for value, offset in _matches_for(slot, pattern, text):
                record = {"slot": slot, "value": value, "para": index,
                          "offset": offset}
                if slot == "grade" and not GRADE_RE.match(value):
                    dropped.append(dict(record, reason="牌号取值形式无法解析"))
                    continue
                if not _domain_ok(slot, value):
                    _low, high, unit = NUMERIC_DOMAIN[slot]
                    dropped.append(dict(record, reason="取值域外（格式检查：0<值<%g %s）" % (
                        high, unit)))
                    continue
                if slot not in NUMERIC_DOMAIN and len(value) > MAX_TEXT_LEN:
                    dropped.append(dict(record, reason="取值超过 %d 字，疑似整句误抽，"
                                                      "不作为槽位值" % MAX_TEXT_LEN))
                    continue
                evidence.append(record)

    evidence.sort(key=lambda r: (r["para"], r["slot"], r["value"], r["offset"]))

    by_slot = {}  # type: Dict[str, List[Dict[str, Any]]]
    for item in evidence:
        by_slot.setdefault(item["slot"], []).append(item)

    conflicts = []  # type: List[Dict[str, Any]]
    for slot in sorted(by_slot):
        values = sorted(set(item["value"] for item in by_slot[slot]))
        if len(values) > 1:
            conflicts.append({
                "slot": slot,
                "values": values,
                "paras": sorted(set(item["para"] for item in by_slot[slot])),
            })

    slots = dict((slot, by_slot[slot][0]["value"]) for slot in sorted(by_slot))
    return {"slots": slots, "slot_evidence": evidence,
            "dropped": dropped, "conflicts": conflicts}


# ---------------------------------------------------------------------------
# 参数卡槽位归一（只认完全等值；其余记 dropped）
# ---------------------------------------------------------------------------

def _split_grade(value: str) -> Tuple[Optional[str], Optional[str]]:
    match = GRADE_RE.match(value)
    if not match:
        return (None, None)
    grade = "Q%s" % match.group(1)
    return (grade, match.group(2))


def normalize_to_card_slots(
    extracted: Dict[str, Any],
) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
    """文档槽位 → 参数卡槽位；不能等值落进词表的进 `dropped`（不猜、不改写）。"""
    card = {}  # type: Dict[str, str]
    dropped = []  # type: List[Dict[str, Any]]

    for slot in sorted(extracted["slots"]):
        value = extracted["slots"][slot]

        if slot == "grade":
            grade, quality = _split_grade(value)
            if grade is None:
                dropped.append({"slot": slot, "value": value,
                                "reason": "牌号取值形式无法解析"})
                continue
            if grade not in STEEL_GRADE_VALUES:
                dropped.append({"slot": slot, "value": value,
                                "reason": "牌号 %s 不在输入词表（V5 牌号体系未定案，"
                                          "词表只是输入界面，不代表该值可用）" % grade})
                continue
            card["steel_grade"] = grade
            if quality and quality in QUALITY_CLASS_VALUES:
                card["quality_class"] = quality
            continue

        if slot == "qclass":
            if value in QUALITY_CLASS_VALUES:
                card.setdefault("quality_class", value)
            else:
                dropped.append({"slot": slot, "value": value,
                                "reason": "质量等级不在输入词表 %s" % list(QUALITY_CLASS_VALUES)})
            continue

        target = CARD_SLOT_MAP.get(slot)
        if target is None:
            continue  # min_hf/mu/coating/fire_hour 不是参数卡槽位（mu 属数据侧量，K19）
        allowed = {"weld_quality_class": WELD_CLASS_VALUES,
                   "bolt_grade": BOLT_GRADE_VALUES,
                   "surface_treatment": SURFACE_VALUES}[target]
        if value in allowed:
            card[target] = value
        else:
            dropped.append({"slot": slot, "value": value,
                            "reason": "文档写法 %r 不等于输入词表任何一项，未做同义猜测"
                                      "（词表：%s）" % (value, list(allowed))})

    conflicts = extracted.get("conflicts") or []
    for conflict in conflicts:
        if conflict["slot"] == "grade" and "steel_grade" in card:
            card.pop("steel_grade")
    if conflicts:
        dropped.extend({"slot": item["slot"], "value": "|".join(item["values"]),
                        "paras": item["paras"], "reason": "同槽位多值，取值不唯一，"
                                                          "不进参数卡（歧义判定交规则层）"}
                       for item in conflicts if item["slot"] in
                       ("grade", "weld_class", "bolt_grade", "surface"))

    return dict(sorted(card.items())), dropped


def require_string_slot(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise ParseError("%s 需要非空字符串，实际 %r" % (where, value))
    return value
