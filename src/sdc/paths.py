"""数据目录定位。

优先级顺序（显式 > 环境变量 > 打包 > exe 同侧 > CWD 上溯）是项目口径 K11 的一部分：
GUI 与 CLI 共用本函数，改动会同时改变两者的数据寻址行为，属口径变更，需登记 plan/06。
"""

import os
import sys
from typing import Optional

ENV_VAR = "SDC_DATA_DIR"


class DataDirNotFound(RuntimeError):
    pass


def _looks_like_data_dir(path: str) -> bool:
    return os.path.isdir(os.path.join(path, "clauses"))


def find_data_dir(explicit: Optional[str] = None) -> str:
    """返回 data 目录绝对路径；显式参数与环境变量分支不做存在性校验（由调用方报错）。"""
    if explicit:
        return os.path.abspath(explicit)

    from_env = os.environ.get(ENV_VAR)
    if from_env:
        return os.path.abspath(from_env)

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidate = os.path.join(meipass, "data")
        if _looks_like_data_dir(candidate):
            return os.path.abspath(candidate)

    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    for candidate in (
        os.path.join(exe_dir, "_internal", "data"),
        os.path.join(exe_dir, "data"),
    ):
        if _looks_like_data_dir(candidate):
            return os.path.abspath(candidate)

    current = os.getcwd()
    while True:
        candidate = os.path.join(current, "data")
        if _looks_like_data_dir(candidate):
            return os.path.abspath(candidate)
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    raise DataDirNotFound(
        "未找到 data 目录（含 clauses/ 子目录）。用 --data-dir 或环境变量 %s 指定。" % ENV_VAR
    )
