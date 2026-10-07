"""文本解析层（M3）：docx/纯文本 → 段落 → 槽位证据 → 参数卡 IR。

与判定层的分工是**进程级**的（口径 K26，缘由见 plan/HANDOFF-M3 §六.2）：本层用正则，
判定层（`sdc.rules`）刻意不对文档执行正则（抽取式的**编译**随本层 import 发生，被隔离的是
执行与文档读取），两层之间只通过落盘的 IR JSON 交接。这样一次正则
相关的进程崩溃不会连带打挂整套评测。

三条纪律：

1. **只抽不改**：解析产物记录文档里写了什么（含原文位置），不判断是否合规——合规判定属规则表。
2. **白名单外丢弃，但留痕**：取值不在输入词表/数值域里就**不进参数卡**，同时把候选原文
   记进 `dropped`，让"文档写了但引擎不认"和"文档没写"在核查侧可区分（前者是 ambiguous，
   后者才是 missing）。
3. **不猜**：抽不到就是抽不到，不做同义推断、不做跨段回指消解（"前述要求" 不解析成具体值）。
"""

from .errors import IrError, ParseError
from .ir import (build_ir, card_gaps, default_ir_path, load_ir, validate_ir, write_ir)
from .slots import (SLOT_NAMES, canonical_value, extract_slots,
                    normalize_to_card_slots)
from .textio import read_document

__all__ = [
    "IrError",
    "ParseError",
    "SLOT_NAMES",
    "build_ir",
    "card_gaps",
    "canonical_value",
    "default_ir_path",
    "extract_slots",
    "load_ir",
    "normalize_to_card_slots",
    "read_document",
    "validate_ir",
    "write_ir",
]
