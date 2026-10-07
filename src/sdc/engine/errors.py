"""引擎层异常。三类异常与 CLI 退出码的映射（口径 K9）：

- `InputError` → 参数卡或算例文件不可用 → 退出码 2；
- `EngineError` → 依赖已全 `verified` 但数据自身不自洽（缺符号、循环派生、无验算式）→ 退出码 1；
- `ExprError` → 式体字符串不合法，属数据问题 → 退出码 1（不静默按 0 计算）。
"""


class EngineFailure(Exception):
    """引擎层失败基类。"""

    exit_code = 1


class InputError(EngineFailure):
    """参数卡不可用：缺必填、枚举越界、单位未知、数值非法。"""

    exit_code = 2


class ExprError(EngineFailure):
    """式体不合法：无法解析、结构不被允许、除零、非有限值。"""

    exit_code = 1


class EngineError(EngineFailure):
    """数据不自洽导致无法完成计算。"""

    exit_code = 1
