"""合成语料的体例库：段落模板 + 槽位变体（plan/05 §五）。

这些文本是**自制合成样例**，不是规范内容；模板里的槽位取值来自 PARAMETER_POOL，
真值随每份文档一起落到 groundtruth.json，供解析与核查评测对账。
文档标题固定带"合成样例"标记，避免被误当真实工程说明。
"""

import re
from typing import Dict, List, Tuple

SECTIONS = ("material", "welding", "bolt", "protection", "construct")

SECTION_HEADINGS = {
    "material": "一、钢材",
    "welding": "二、焊接",
    "bolt": "三、螺栓连接",
    "protection": "四、涂装与防火",
    "construct": "五、构造与安装要求",
}

VARIANTS = {
    "material": [
        "承重钢结构钢材采用{grade}，质量等级{qclass}级，焊接材料应与主体材质相匹配。",
        "主体结构选用{grade}钢（质量等级{qclass}），其强度设计值按现行国家标准取值。",
        "本工程钢构件材质为{grade}，质量等级{qclass}级，进场时按批复验。",
    ],
    "welding": [
        "直接承受动力荷载且垂直于焊缝受力方向的对接焊缝质量等级为{weld_class}，"
        "其余对接焊缝不低于三级；角焊缝焊脚尺寸不小于{min_hf}mm。",
        "对接焊缝中受拉者按{weld_class}检验，受压及受剪者按三级检验；"
        "角焊缝焊脚取{min_hf}mm，焊缝长度满足构造要求。",
        "本工程对接焊缝质量等级取{weld_class}，焊后按相应等级进行无损检测；"
        "角焊缝最小焊脚{min_hf}mm。",
    ],
    "bolt": [
        "主受力连接采用{bolt_grade}级高强度螺栓摩擦型连接，摩擦面处理为{surface}，"
        "抗滑移系数取{mu}。",
        "高强螺栓摩擦型连接的性能等级为{bolt_grade}，摩擦面{surface}，"
        "设计抗滑移系数{mu}。",
        "连接螺栓选用{bolt_grade}级，摩擦面处理方式{surface}，抗滑移系数按{mu}采用。",
    ],
    "protection": [
        "钢构件防腐按{coating}体系施工；室外及隐蔽部位构件耐火极限不低于{fire_hour}h。",
        "涂装体系为{coating}，承重构件的防火保护按耐火极限{fire_hour}h 设计。",
        "表面除锈后采用{coating}；防火涂层厚度应满足{fire_hour}h 耐火极限要求。",
    ],
    "construct": [
        "受压构件长细比按规范限值控制，支撑系统与主框架的连接应满足构造要求。",
        "安装阶段应保证构件定位与临时支撑，焊缝与螺栓施工按前述要求执行。",
        "构件运输与拼装不得损伤摩擦面，摩擦面处理后应保持{surface}状态。",
    ],
}

# 缺陷注入专用表述：焊缝等级要求"未写明检验等级"
INJECT_TEMPLATES = {
    "weld_class_missing": "承重结构对接焊缝应保证焊接质量，焊缝检验按相关标准执行。",
    "steel_grade_contradiction": "次要构件及连接板采用{grade_alt}，其余要求同前述。",
    "bolt_grade_mismatch_main": "主受力连接采用{bolt_grade}级螺栓，普通C 级螺栓施工按常规要求。",
}

_INJECTION_SECTION = {
    "weld_class_missing": "welding",
    "steel_grade_contradiction": "construct",
    "bolt_grade_mismatch": "bolt",
}

INJECTION_TYPES = ("weld_class_missing", "steel_grade_contradiction", "bolt_grade_mismatch")

PARAMETER_POOL = {
    "grade": ("Q235B", "Q355B", "Q390C", "Q420D"),
    "grade_alt": ("Q235B",),
    "qclass": ("A", "B", "C", "D"),
    "weld_class": ("一级", "二级"),
    "min_hf": ("4", "6", "8", "10"),
    "bolt_grade": ("8.8", "10.9"),
    "surface": ("喷砂", "喷砂后涂富锌漆", "表面自然生红锈", "手工钢丝刷清理浮锈"),
    "mu": ("0.30", "0.35", "0.40", "0.45"),
    "coating": ("两道环氧富锌底漆加两道面漆", "热浸镀锌加两道面漆", "无机富锌底漆加环氧中间漆加面漆"),
    "fire_hour": ("1.00", "1.50", "2.00"),
}

# 螺栓等级不匹配注入时使用的等级（低于主受力连接常规取值）
MISMATCH_BOLT_GRADE = "4.6"

_SLOT_RE = re.compile(r"\{(\w+)\}")


def slots_used(template: str) -> List[str]:
    """模板引用的槽位名，排序后返回（禁 set 迭代序，口径 K8）。"""
    return sorted(set(_SLOT_RE.findall(template)))


def section_of_injection(injection_type: str) -> str:
    return _INJECTION_SECTION[injection_type]
