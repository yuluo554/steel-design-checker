"""界面用的显示名。

这里只有**标签**，没有任何判定信息：模块 id 一律取自 `kb.schema.MODULES`，
槽位名取自 `engine.params.MODULE_SLOTS`，槽位中文名单取自主窗口的知识库（符号表
`name_zh`）。`tests/test_gui_pages.py` 断言本文件的模块键与 `MODULES` 逐项相等，
防止它长成第二套枚举。
"""

MODULE_LABELS = {
    "butt_weld": "A1 对接焊缝",
    "fillet_weld": "A2 角焊缝",
    "bolt_normal": "A3 普通螺栓",
    "bolt_hsb_friction": "A4 高强度螺栓摩擦型",
    "column_buckling": "A5 轴心受压构件整体稳定",
}
