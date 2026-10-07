"""打包规则单源：spec 与构建后断言读的是同一份名单（口径 K46）。

放在 `scripts/` 而不是 `src/` 里：它是构建期工具的配置，不参与运行时导入。
名字不叫 `packaging.py`，避免与 PyPA 的 `packaging` 撞名（PyInstaller 自己依赖它）。

白名单的理由：
- `DATA_SUBDIRS` 只收 `sdc.kb.loader` 与 `sdc.suite` 运行必需的数据目录；
- `data/README.md`（取证台账，含渠道 URL）与 `data/cases/`（0 例真值，只有说明文档）
  **不入包**：交付物里不写渠道 URL（口径 K42），而缺 `cases/` 时 `load_kb` 得到 0 条记录
  ⇒ 算例通过率照旧显示"分母 0，样本待补 / 不可判"，正好与仓库实况一致；
- `FORBIDDEN_COMPONENTS` 是禁止事项那一节的机器化：取证缓存、计划文档、测试、源码目录、
  以及明令不引的第三方库（python-docx / numpy / scipy / faiss / 网络库）都不得出现在 dist 树里。
"""

import os

BUNDLES = {
    "sdc-cli": {"exe": "sdc-cli.exe", "console": True},
    "sdc-gui": {"exe": "sdc-gui.exe", "console": False},
}

# 进包的数据目录（相对 data/）
DATA_SUBDIRS = ("clauses", "tables", "formulas", "symbols", "rules", "checklist",
                "selfcheck", "examples", "synth")

# 明确不入包的 data 成员
DATA_EXCLUDED = ("README.md", "cases")

# 任何深度都不得出现的路径成分（本项目自己的取证/计划/会话产物与本地环境目录）
FORBIDDEN_ANYWHERE = (".git", ".tmp_verify", ".tmp_parse", ".venv", "venv", "plan",
                      "__pycache__")

# 只在包根与 `_internal` 根检查的目录名：Qt/Python 运行时里可能碰巧有同名子目录，
# 但第三方库只会躺在 `_internal` 这一层，所以这两层足够抓住"禁区成分入包"。
FORBIDDEN_AT_ROOT = ("tests", "src", "scripts", "code", "docs", ".github")

# 禁止事项里明令不引入的依赖（导出侧不新增第三方库，python-docx 会写真实时间与用户名）
FORBIDDEN_PACKAGES = ("numpy", "scipy", "faiss", "docx", "python_docx", "requests",
                      "urllib3", "pdfplumber", "pypdf", "torch", "pandas")

# dist 树里不得出现的文件名
FORBIDDEN_FILE_NAMES = ("README.md", "sdc.spec", ".gitignore", ".gitattributes")

# GUI 依赖不得漏进 CLI 包（PySide6 只该出现在 sdc-gui 里）
GUI_ONLY_COMPONENTS = ("PySide6", "shiboken6")

CLI_EXE_NAME = "sdc-cli.exe"
GUI_EXE_NAME = "sdc-gui.exe"


def data_pairs(data_dir):
    """返回 spec 用的 (源路径, 包内目标) 列表；只收真实存在的白名单目录。"""
    pairs = []
    for name in DATA_SUBDIRS:
        source = os.path.join(data_dir, name)
        if not os.path.isdir(source):
            raise SystemExit("数据白名单里的目录不存在：%s" % source)
        pairs.append((source, os.path.join("data", name)))
    return pairs
