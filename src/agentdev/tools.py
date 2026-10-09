"""Tools the agent can call."""

from __future__ import annotations

import ast
import operator
from datetime import datetime

from langchain.tools import tool

_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 8:
            raise ValueError("指数过大")
        return _BINARY_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("只支持数字和 + - * / // % ** 以及括号")


def evaluate_expression(expression: str) -> str:
    tree = ast.parse(expression, mode="eval")
    value = _eval_node(tree.body)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


@tool
def get_current_time() -> str:
    """返回当前本地日期和时间，格式为 ISO 8601。"""
    return datetime.now().astimezone().isoformat(timespec="seconds")


@tool
def calculate(expression: str) -> str:
    """计算算术表达式。支持 + - * / // % ** 和括号，例如 (2 + 3) * 4。"""
    return evaluate_expression(expression)
