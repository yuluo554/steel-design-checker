"""解析层专用异常：文档读不出来 / IR 不合法。

与 `engine.errors.InputError`（参数卡不可用，退出码 2）分开，是为了让"输入文档不可读"
和"参数卡不合 schema"在 CLI 里能各自说明原因，不混成一句"输入不可用"。
"""


class ParseError(Exception):
    """文档抽取失败。"""


class IrError(Exception):
    """参数卡 IR 结构不合法（判定层拒收）。"""
