"""
calculator 内置工具：执行数学表达式计算。

支持基本运算：+ - * / ** () sqrt log
安全：使用 Python ast.literal_eval-like 的安全求值，禁止 exec/eval 任意代码。
"""

import ast
import math
import operator
from typing import Any, Dict


# 允许的操作符白名单
_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}

# 允许的数学函数白名单
_ALLOWED_FUNCTIONS = {
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "abs": abs,
    "ceil": math.ceil,
    "floor": math.floor,
    "round": round,
    "pi": math.pi,
    "e": math.e,
}


def _safe_eval(node: ast.AST) -> float:
    """递归安全求值 AST 节点"""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError(f"不支持的常量类型: {type(node.value)}")
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_OPERATORS:
            raise ValueError(f"不支持的运算符: {op_type.__name__}")
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        return _ALLOWED_OPERATORS[op_type](left, right)
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_OPERATORS:
            raise ValueError(f"不支持的一元运算符: {op_type.__name__}")
        operand = _safe_eval(node.operand)
        return _ALLOWED_OPERATORS[op_type](operand)
    elif isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("不允许调用非内置函数")
        func_name = node.func.id
        if func_name not in _ALLOWED_FUNCTIONS:
            raise ValueError(f"不允许的函数: {func_name}")
        func = _ALLOWED_FUNCTIONS[func_name]
        args = [_safe_eval(arg) for arg in node.args]
        return func(*args)
    elif isinstance(node, ast.Name):
        # 支持 pi, e 等常量
        if node.id in _ALLOWED_FUNCTIONS:
            val = _ALLOWED_FUNCTIONS[node.id]
            if callable(val):
                raise ValueError(f"{node.id} 是函数，需要加括号调用")
            return float(val)
        raise ValueError(f"不支持的变量: {node.id}")
    else:
        raise ValueError(f"不支持的 AST 节点类型: {type(node).__name__}")


def calculate(expression: str) -> Dict[str, Any]:
    """
    安全计算数学表达式。

    Args:
        expression: 数学表达式字符串，例如 "2 + 3 * 4" 或 "sqrt(16)"

    Returns:
        {"result": 数值结果, "expression": 原始表达式}

    Raises:
        ValueError: 表达式非法或计算失败
    """
    expression = expression.strip()
    if not expression:
        raise ValueError("表达式不能为空")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"表达式语法错误: {e}") from e

    result = _safe_eval(tree.body)

    # 避免浮点精度问题，整数结果以 int 返回
    if result == int(result) and abs(result) < 1e15:
        return {"expression": expression, "result": int(result)}
    return {"expression": expression, "result": result}


# ── 工具元数据（OpenAI function calling schema）──────────────────────────────

TOOL_DEFINITION = {
    "name": "calculator",
    "description": (
        "执行数学表达式计算，支持加减乘除、幂运算、括号、以及 sqrt/log/sin/cos/tan/abs/ceil/floor/round 等数学函数。"
        "例如：'2+3*4'、'sqrt(16)'、'log(100, 10)'、'(1+2)*3'。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "要计算的数学表达式字符串，例如 '2+3*4' 或 'sqrt(16)'",
            }
        },
        "required": ["expression"],
    },
}
