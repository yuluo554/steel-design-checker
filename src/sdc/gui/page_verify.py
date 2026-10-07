"""页签①验算台：模块选择 + 参数卡表单 + 验算结果与逐步计算。

表单**只**做输入装配，不做任何校验：槽位集合来自 `engine.params.MODULE_SLOTS`，
枚举候选来自 `ENUM_SLOTS`，单位候选来自 `engine.units.UNIT_TABLE`。填了非法值时
界面显示的是 `normalize_card` 抛出的那句原文（与 CLI 一字不差），而不是界面自己
编的说法（口径 D08/K41）。

计算走 `sdc.cli.run_card_command`：与 `sdc run`/`sdc report` 同一个函数、同一批异常
映射、同一个退出码。
"""

import json
import os
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPlainTextEdit, QPushButton,
                               QSplitter, QVBoxLayout, QWidget)

from ..cli import run_card_command
from ..engine.params import ENUM_SLOTS, MODULE_SLOTS, POSITIVE_INT_SLOTS
from ..engine.render import render_result
from ..engine.units import DEFAULT_UNITS, UNIT_TABLE
from ..kb import load_kb
from ..kb.schema import MODULES
from .labels import MODULE_LABELS
from .widgets import (HEADERS_BASIS, HEADERS_BLOCKED, HEADERS_RESULT, BasePage,
                      button_row, fill_table, make_table, make_text_view,
                      scroll_form, text_group)

NOT_SET = "（未填）"
UNSET = ""
FORCED_SLOTS = ("N", "V", "M", "T")
# 表单里出现的量纲族：只列用户会声明的那几个，取值直接来自 UNIT_TABLE
UNIT_FAMILIES = ("force", "moment", "length", "area", "second_moment")
TRISTATE = (NOT_SET, "true", "false")


def example_cards(data_dir: str) -> List[str]:
    directory = os.path.join(data_dir, "examples")
    if not os.path.isdir(directory):
        return []
    return sorted(name for name in os.listdir(directory) if name.endswith(".json"))


class CardForm(QWidget):
    """按模块定义生成表单；`to_card()` 交出的对象直接进 `normalize_card`。"""

    def __init__(self, symbol_names: Optional[Dict[str, str]] = None, parent=None):
        QWidget.__init__(self, parent)
        self.symbol_names = dict(symbol_names or {})
        self.fields = {}  # type: Dict[str, Any]
        self.unit_fields = {}  # type: Dict[str, QComboBox]
        self.force_fields = {}  # type: Dict[str, QLineEdit]

        layout = QVBoxLayout(self)
        head = QComboBox()
        head.addItems([MODULE_LABELS.get(name, name) for name in MODULES])
        head.currentTextChanged.connect(self._rebuild)
        self.module_combo = head
        layout.addWidget(QLabel("验算模块（5 个，来自 kb.schema.MODULES）"))
        layout.addWidget(head)

        self.case_id = QLineEdit("GUI-CASE")
        layout.addWidget(QLabel("case_id"))
        layout.addWidget(self.case_id)

        self.body = QWidget()
        QVBoxLayout(self.body)
        layout.addWidget(scroll_form(self.body))

        units = QWidget()
        unit_layout = QHBoxLayout(units)
        for family in UNIT_FAMILIES:
            combo = QComboBox()
            combo.addItems(sorted(UNIT_TABLE[family]))
            combo.setCurrentText(DEFAULT_UNITS[family])
            unit_layout.addWidget(QLabel(family))
            unit_layout.addWidget(combo)
            self.unit_fields[family] = combo
        layout.addWidget(QLabel("单位声明（engine.units.UNIT_TABLE）"))
        layout.addWidget(units)

        forces = QWidget()
        force_layout = QHBoxLayout(forces)
        for name in FORCED_SLOTS:
            field = QLineEdit()
            field.setPlaceholderText(name)
            force_layout.addWidget(QLabel(name))
            force_layout.addWidget(field)
            self.force_fields[name] = field
        layout.addWidget(QLabel("设计内力 forces（荷载组合由外部给定，本工具不生成组合）"))
        layout.addWidget(forces)

        self._rebuild(MODULE_LABELS.get(MODULES[0], MODULES[0]))

    # -- 表单构建 -----------------------------------------------------------
    def module(self) -> str:
        index = self.module_combo.currentIndex()
        return MODULES[index]

    def _label(self, slot: str, required: bool) -> str:
        zh = self.symbol_names.get(slot, "")
        text = slot if not zh else "%s（%s）" % (slot, zh)
        return text + (" *" if required else "")

    def _rebuild(self, _ignored: str) -> None:
        layout = self.body.layout()
        while layout is not None and layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.fields = {}
        spec = MODULE_SLOTS[self.module()]
        required = set(spec["required"])
        grid = QWidget()
        form = QFormLayout(grid)
        for slot in list(spec["required"]) + list(spec["optional"]):
            field = self._make_field(slot)
            self.fields[slot] = field
            form.addRow(self._label(slot, slot in required), field)
        self.body.layout().addWidget(grid)

    def _make_field(self, slot: str):
        if slot in ENUM_SLOTS:
            combo = QComboBox()
            combo.addItems([NOT_SET] + list(ENUM_SLOTS[slot]))
            return combo
        if slot == "has_opening_gap":
            combo = QComboBox()
            combo.addItems(list(TRISTATE))
            return combo
        if slot == "group":
            field = QPlainTextEdit()
            field.setPlaceholderText('{"n_x": 2, "n_y": 2, "pitch": 80}')
            field.setMaximumHeight(64)
            return field
        field = QLineEdit()
        field.setPlaceholderText(slot)
        return field

    # -- 读写卡片 -----------------------------------------------------------
    def to_card(self) -> Dict[str, Any]:
        card = {"case_id": self.case_id.text().strip(), "module": self.module()}
        for slot, field in sorted(self.fields.items()):
            value = self._field_value(slot, field)
            if value is UNSET or value is None:
                continue
            card[slot] = value
        forces = {}
        for name, field in sorted(self.force_fields.items()):
            text = field.text().strip()
            if text:
                forces[name] = _number_or_text(text)
        if forces:
            card["forces"] = forces
        card["units"] = dict((family, combo.currentText())
                             for family, combo in sorted(self.unit_fields.items())
                             if combo.currentText() != NOT_SET)
        return card

    def _field_value(self, slot: str, field):
        if isinstance(field, QComboBox):
            text = field.currentText()
            if text == NOT_SET:
                return UNSET
            if slot == "has_opening_gap":
                return text == "true"
            return text
        if isinstance(field, QPlainTextEdit):
            text = field.toPlainText().strip()
            if not text:
                return UNSET
            try:
                return json.loads(text)
            except ValueError:
                # 交给引擎判：参数卡里的 group 不是对象时，报错原文来自 normalize_card
                return text
        text = field.text().strip()
        if not text:
            return UNSET
        if slot in ENUM_SLOTS or slot == "section" or slot.startswith("thickness_group"):
            return text
        if slot in POSITIVE_INT_SLOTS:
            return _int_or_text(text)
        return _number_or_text(text)

    def load_card(self, card: Dict[str, Any]) -> None:
        module = card.get("module")
        if module in MODULES:
            self.module_combo.setCurrentIndex(MODULES.index(module))
        self.case_id.setText(str(card.get("case_id", "")))
        for slot, value in sorted(card.items()):
            field = self.fields.get(slot)
            if field is None:
                continue
            if isinstance(field, QComboBox):
                if slot == "has_opening_gap":
                    field.setCurrentText("true" if value else "false")
                else:
                    field.setCurrentText(str(value))
            elif isinstance(field, QPlainTextEdit):
                field.setPlainText(json.dumps(value, ensure_ascii=False, sort_keys=True))
            else:
                field.setText("" if value is None else str(value))
        for name, value in sorted((card.get("forces") or {}).items()):
            if name in self.force_fields:
                self.force_fields[name].setText(str(value))
        for family, unit in sorted((card.get("units") or {}).items()):
            combo = self.unit_fields.get(family)
            if combo is not None and unit in UNIT_TABLE.get(family, {}):
                combo.setCurrentText(unit)


def _number_or_text(text: str):
    try:
        return float(text)
    except ValueError:
        return text


def _int_or_text(text: str):
    try:
        return int(text)
    except ValueError:
        return _number_or_text(text)


class VerifyPage(BasePage):
    """①验算台。"""

    def __init__(self, data_dir: str, parent: Optional[QWidget] = None):
        BasePage.__init__(self, data_dir, parent)
        self.symbol_names = _symbol_names(data_dir)
        self.result = None
        self.exit_code = None

        layout = QVBoxLayout(self)
        self.form = CardForm(self.symbol_names)
        layout.addWidget(self.form)

        self.cards = QComboBox()
        self.cards.addItems([""] + example_cards(data_dir))
        buttons = (QPushButton("载入示例参数卡"), QPushButton("从文件载入…"),
                   QPushButton("验算"), QPushButton("清空结果"))
        self.load_button, self.open_button, self.run_button, self.clear_button = buttons
        self.load_button.clicked.connect(self.load_example)
        self.open_button.clicked.connect(self.load_file)
        self.run_button.clicked.connect(self.run)
        self.clear_button.clicked.connect(self.clear)
        row = QHBoxLayout()
        row.addWidget(QLabel("data/examples/"))
        row.addWidget(self.cards)
        row.addLayout(button_row(*buttons))
        layout.addLayout(row)

        self.summary = QLabel("尚未验算。引用未核对的数据时按门控拒算，拒算结果里一个数值都没有。")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self.steps = make_table(HEADERS_RESULT)
        self.basis = make_table(HEADERS_BASIS)
        self.blocked = make_table(HEADERS_BLOCKED)
        self.text = make_text_view("结果原文（与 `sdc run` 同一批行）")

        tables = QSplitter()
        tables.addWidget(text_group("逐步计算 steps", self.steps))
        tables.addWidget(text_group("依据条款 basis", self.basis))
        tables.addWidget(text_group("拒算项 blocked", self.blocked))
        panes = QSplitter(Qt.Vertical)
        panes.addWidget(tables)
        panes.addWidget(text_group("结果原文", self.text))
        layout.addWidget(panes)

    def run(self) -> Dict[str, Any]:
        card = self.form.to_card()
        result, code, error = run_card_command(self.data_dir, card, None)
        self.result = result
        self.exit_code = code
        if result is None:
            fill_table(self.steps, HEADERS_RESULT, [])
            fill_table(self.basis, HEADERS_BASIS, [])
            fill_table(self.blocked, HEADERS_BLOCKED, [])
            self.text.setPlainText(error)
            self.summary.setText("未完成（退出码 %d）：%s" % (code, error.strip()))
            self.notify(error.strip(), "error")
            return {}
        self.render(result, code)
        return result

    def render(self, result: Dict[str, Any], code: int) -> None:
        fill_table(self.steps, HEADERS_RESULT, [
            (step["no"], step["formula_id"], step["expr"],
             _substituted(step.get("substituted")), step["value"],
             step.get("unit"), step.get("symbol_zh"))
            for step in result["steps"]])
        fill_table(self.basis, HEADERS_BASIS, [
            (item["clause_id"], item["title"], item["kind"], item["status"],
             "是" if item.get("mandatory") else "")
            for item in result["basis"]])
        fill_table(self.blocked, HEADERS_BLOCKED, [
            (item["kind"], item["id"], item["status"], item["reason"])
            for item in result["blocked"]])
        # 原文 = 命令面用的同一个渲染函数，界面不另排一版
        self.text.setPlainText(render_result(result))
        ratio = ("不出数值（blocked）" if result["conclusion"] == "blocked"
                 else repr(round(result["ratio"], 6)))
        self.summary.setText("结论：%s｜比值：%s｜退出码：%d｜数据指纹：%s" % (
            result["conclusion"], ratio, code, result["meta"]["data_fingerprint"][:12]))

    def clear(self) -> None:
        self.result = None
        self.exit_code = None
        self.text.setPlainText("")
        self.summary.setText("已清空。")

    def load_example(self) -> None:
        name = self.cards.currentText().strip()
        if not name:
            self.notify("先在下拉框里选一份 data/examples/ 参数卡", "warn")
            return
        self._load(os.path.join(self.data_dir, "examples", name))

    def load_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择参数卡 JSON", "",
                                              "JSON (*.json)")
        if path:
            self._load(path)

    def _load(self, path: str) -> bool:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                card = json.loads(handle.read())
        except (OSError, ValueError) as exc:
            self.notify("参数卡读取失败：%s" % exc, "error")
            return False
        if not isinstance(card, dict):
            self.notify("参数卡必须是 JSON 对象", "error")
            return False
        self.form.load_card(card)
        self.notify("已载入参数卡：%s（%s）" % (os.path.basename(path), card.get("module")))
        return True


def _symbol_names(data_dir: str) -> Dict[str, str]:
    """槽位的中文名来自知识库符号表；数据缺席就退回槽位名，不自己编名字。"""
    try:
        kb = load_kb(data_dir)
    except Exception:  # noqa: BLE001 - 界面不该因为数据问题崩，标签回落到槽位名
        return {}
    out = {}
    for symbol, rec in sorted(kb.by_id("symbol").items()):
        name = rec.get("name_zh")
        if isinstance(name, str) and name:
            out[symbol] = name
    return out


def _substituted(values: Optional[Dict[str, Any]]) -> str:
    if not values:
        return ""
    return ", ".join("%s=%s" % (name, values[name]) for name in sorted(values))
