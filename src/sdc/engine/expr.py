"""式体求值：对知识库里的 `expr` 字符串做 AST 白名单遍历，禁 `eval`、禁属性访问。

式体口径（M2 定稿，plan/04 §三）：

- `expr` 必须是机器可解析形式（ASCII 符号名、`*` `/` `**` 运算符），规范的原始记法留在
  `notes` 里，两者一起录入才能保证「逐字核对」的东西真是被计算的东西；
- 只含单个 `=` 的式子 → **派生式**：左端是唯一符号，右端是表达式；
- 含 `<=` 或 `>=` 的式子 → **验算式**：比值一律取「作用效应 / 抗力」，
  即 `A <= B` 取 `A/B`、`A >= B` 取 `B/A`；
- 链式比较、`<`/`>` 严格不等、未知函数、下标、属性访问、位运算等一律判为数据不合法，
  不做任何"看起来能用就行"的宽容处理。
"""

import ast
import math
from typing import Any, Dict, List, Optional, Tuple

from .errors import ExprError

# 允许的函数与常量：只到验算式需要的程度，新增即扩白名单（不引入 eval 兜底）
FUNCTIONS = {
    "sqrt": math.sqrt,
    "abs": abs,
    "min": min,
    "max": max,
    "exp": math.exp,
    "ln": math.log,
    "log10": math.log10,
}

CONSTANTS = {"pi": math.pi}

_COMPARATORS = (ast.LtE, ast.GtE)
_OP_TEXT = {ast.LtE: "<=", ast.GtE: ">="}
# 出现这些记号就不当作派生式的 `=`
_NON_ASSIGN_TOKENS = ("<=", ">=", "==", "!=", "<", ">", "+=", "-=", "*=", "/=")


class FormulaPlan(object):
    """一条 `expr` 的解释结果。"""

    def __init__(
        self,
        kind: str,
        target: Optional[str] = None,
        op: Optional[str] = None,
        left: Any = None,
        right: Any = None,
        names: Tuple[str, ...] = (),
    ):
        self.kind = kind          # derivation | check
        self.target = target      # 派生式左端符号
        self.op = op              # 验算式比较符原文
        self.left = left          # 派生式右端 / 验算式左端节点
        self.right = right        # 验算式右端节点（派生式为 None）
        self.names = list(names)

    def __repr__(self) -> str:
        return "FormulaPlan(kind=%s, target=%s, op=%s, names=%s)" % (
            self.kind, self.target, self.op, self.names)


def _parse(expr: str, where: str) -> ast.AST:
    if not isinstance(expr, str) or not expr.strip():
        raise ExprError("%s：expr 为空或非字符串，拒绝按默认值计算" % where)
    try:
        return ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ExprError("%s：式体无法按表达式解析（%s）：%s" % (where, exc.msg, expr))
    except ValueError as exc:  # 含 null 字节等
        raise ExprError("%s：式体解析失败：%s" % (where, exc))


def _split_assignment(expr: str) -> Optional[Tuple[str, str]]:
    for token in _NON_ASSIGN_TOKENS:
        if token in expr:
            return None
    parts = expr.split("=")
    if len(parts) != 2:
        return None
    target = parts[0].strip()
    rhs = parts[1].strip()
    if not target or not rhs:
        raise ExprError("派生式两端不完整：%s" % expr)
    if not target.isidentifier():
        raise ExprError("派生式左端必须是单个符号：%s" % expr)
    return target, rhs


def _free_names(node: ast.AST) -> List[str]:
    """收集需要赋值的符号名。Call 的函数名不算符号（sqrt/max/… 走白名单校验）。"""
    names = []  # type: List[str]

    def visit(current: ast.AST) -> None:
        if isinstance(current, ast.Call):
            for arg in current.args:
                visit(arg)
            for keyword in current.keywords:
                visit(keyword.value)
            return
        if isinstance(current, ast.Name):
            if current.id not in CONSTANTS and current.id not in names:
                names.append(current.id)
            return
        for child in ast.iter_child_nodes(current):
            visit(child)

    visit(node)
    return sorted(names)


def build_plan(expr: str, where: str = "formula") -> FormulaPlan:
    """`expr` → FormulaPlan；不合法直接抛 `ExprError`。"""
    assignment = _split_assignment(expr) if isinstance(expr, str) else None
    if assignment is not None:
        target, rhs = assignment
        if target in CONSTANTS or target in FUNCTIONS:
            raise ExprError("%s：派生目标 %s 与保留常量/函数同名" % (where, target))
        node = _parse(rhs, where)
        return FormulaPlan("derivation", target=target, left=node.body,
                           names=tuple(_free_names(node)))

    tree = _parse(expr, where)
    body = tree.body
    if isinstance(body, ast.Compare):
        if len(body.ops) != 1 or len(body.comparators) != 1:
            raise ExprError("%s：只接受两端比较式，链式比较请拆成多条公式：%s" % (where, expr))
        op = body.ops[0]
        if not isinstance(op, _COMPARATORS):
            raise ExprError("%s：比较符只允许 <= 与 >=（严格不等无容差语义）：%s" % (where, expr))
        left, right = body.left, body.comparators[0]
        # 比值恒为「作用效应 / 抗力」
        if isinstance(op, ast.LtE):
            demand, capacity = left, right
        else:
            demand, capacity = right, left
        names = sorted(set(_free_names(body)))
        return FormulaPlan("check", op=_OP_TEXT[type(op)], left=demand, right=capacity,
                           names=tuple(names))

    # 既不是派生式也不是比较式：把它当表达式求值没有判定语义
    raise ExprError("%s：式体必须是派生式（x = …）或 <=/>= 验算式：%s" % (where, expr))


def parse_expression(expr: str, where: str = "formula") -> Tuple[ast.AST, List[str]]:
    """纯表达式入口（不含 `=` 与比较符），供构造限值的 bound_expr 这类「只算不判」的式子用。"""
    tree = _parse(expr, where)
    node = tree.body
    if isinstance(node, ast.Compare):
        raise ExprError("%s：这里要的是表达式，不能带比较符（判定交给验算式）：%s" % (where, expr))
    return node, _free_names(node)


def _num(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExprError("%s：期望数值，实际 %r" % (where, value))
    return float(value)


def _eval(node: ast.AST, env: Dict[str, float], where: str) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body, env, where)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ExprError("%s：式体只允许数值常量，出现 %r" % (where, node.value))
        return float(node.value)

    # Python 3.7 及更早的 Num/Str 节点（保持 3.8 兼容，也防不同编译后端差异）
    num = getattr(ast, "Num", None)
    if num is not None and isinstance(node, num):
        return _num(node.value, where)

    if isinstance(node, ast.Name):
        if node.id in CONSTANTS:
            return CONSTANTS[node.id]
        if node.id in env:
            return _num(env[node.id], where)
        raise ExprError("%s：符号 %s 没有值（依赖的数据或输入缺失）" % (where, node.id))

    if isinstance(node, ast.BinOp):
        left = _eval(node.left, env, where)
        right = _eval(node.right, env, where)
        if isinstance(node.op, ast.Add):
            value = left + right
        elif isinstance(node.op, ast.Sub):
            value = left - right
        elif isinstance(node.op, ast.Mult):
            value = left * right
        elif isinstance(node.op, ast.Div):
            if right == 0.0:
                raise ExprError("%s：除数为 0" % where)
            value = left / right
        elif isinstance(node.op, ast.Pow):
            if right > 64 or right < -64:
                raise ExprError("%s：指数 %r 超出允许范围（防溢出）" % (where, right))
            value = left ** right
        else:
            raise ExprError("%s：不允许的运算符 %s" % (where, type(node.op).__name__))
    elif isinstance(node, ast.UnaryOp):
        operand = _eval(node.operand, env, where)
        if isinstance(node.op, ast.USub):
            value = -operand
        elif isinstance(node.op, ast.UAdd):
            value = operand
        else:
            raise ExprError("%s：不允许的一元运算符 %s" % (
                where, type(node.op).__name__))
    elif isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS:
            raise ExprError("%s：只允许调用白名单函数 %s" % (where, sorted(FUNCTIONS)))
        if node.keywords:
            raise ExprError("%s：函数不接受关键字参数" % where)
        args = [_eval(arg, env, where) for arg in node.args]
        if not args:
            raise ExprError("%s：函数 %s 至少需要一个参数" % (where, node.func.id))
        try:
            value = FUNCTIONS[node.func.id](*args)
        except (ValueError, OverflowError, ZeroDivisionError) as exc:
            raise ExprError("%s：函数调用失败：%s" % (where, exc))
    else:
        raise ExprError("%s：不允许的语法结构 %s" % (where, type(node).__name__))

    if not math.isfinite(value):
        raise ExprError("%s：结果不是有限值（%r）" % (where, value))
    return value


def evaluate(node: ast.AST, env: Dict[str, float], where: str = "formula") -> float:
    return _eval(node, env, where)


def plan_names(plan: FormulaPlan) -> List[str]:
    return list(plan.names)
