"""验算引擎公开 API（GUI 与 CLI 共用，口径 K10/D08）。"""

from ..kb import load_kb
from .core import DISCLAIMER, NEED_ADJUST_FLOOR, RATIO_TOL, result_exit_code, run_case
from .errors import EngineError, ExprError, InputError
from .params import normalize_card
from .render import render_result

__all__ = ["load_kb", "run_case", "normalize_card", "render_result", "result_exit_code",
           "InputError", "EngineError", "ExprError", "DISCLAIMER", "RATIO_TOL",
           "NEED_ADJUST_FLOOR"]
