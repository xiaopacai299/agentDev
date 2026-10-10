"""Validate tool arguments and ask before a risky call."""

from __future__ import annotations

import re
from contextvars import ContextVar

from pydantic import ValidationError

# 步骤 1：高风险确认标记，以及不能回传给模型的内容
RISK_CONFIRM = "confirm"
_CONFIRMED: ContextVar[bool] = ContextVar("tool_confirmed", default=False)
_SENSITIVE = re.compile(r"(?i)(https?://|traceback|\\+|src/|\.py\b)")


def deletion_already_confirmed() -> bool:
    return _CONFIRMED.get()


# 步骤 2：把校验失败收成字段和错误类型
def _field_name(location: tuple) -> str:
    parts = [str(part) for part in location if part != "body"]
    return ".".join(parts)


def _field_problem(item: dict) -> str:
    kind = str(item.get("type") or "invalid")
    ctx = item.get("ctx") or {}
    if kind == "string_pattern_mismatch":
        return f"必须符合格式 {ctx.get('pattern', '')}"
    if kind in {"greater_than_equal", "less_than_equal", "greater_than", "less_than"}:
        return "超出允许范围"
    if kind in {"int_parsing", "int_type", "float_parsing", "float_type"}:
        return "类型不符合"
    if kind in {"string_too_short", "string_too_long", "too_short", "too_long"}:
        return "长度不符合"
    return kind


def clean_validation_error(exc: ValidationError) -> str:
    parts = [f"{_field_name(tuple(item.get('loc') or ()))} {_field_problem(item)}".strip() for item in exc.errors()]
    return "参数不符合约定：" + "；".join(parts)


def public_failure(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return clean_validation_error(exc)
    text = str(exc).strip()
    if isinstance(exc, ValueError) and text and _SENSITIVE.search(text) is None:
        return f"工具执行失败：{text}"
    return "工具执行失败：参数或调用无效"


def _schema_error(tool, args: dict) -> str | None:
    schema = getattr(tool, "args_schema", None)
    if schema is None or isinstance(schema, dict):
        return None
    try:
        schema.model_validate(args)
    except ValidationError as exc:
        return clean_validation_error(exc)
    return None


def _risk_text(tool, args: dict) -> str:
    extras = getattr(tool, "extras", None) or {}
    if extras.get("risk") != RISK_CONFIRM:
        return ""
    risk_of = extras.get("risk_of")
    if callable(risk_of):
        return str(risk_of(args) or "")
    name = str(getattr(tool, "name", "") or "工具")
    return f"{name} {args}"


def _ask(text: str) -> bool:
    print("\n即将执行高风险操作：")
    print(text)
    try:
        answer = input("确认执行请输入 yes 或 确认：").strip().lower()
    except EOFError:
        return False
    return answer in {"yes", "确认"}


# 步骤 3：执行前安检，通过后才允许真正调用工具
def screen_call(tool, args: dict) -> tuple[str | None, bool]:
    # 步骤 1：参数不符合 schema 时直接退回
    invalid = _schema_error(tool, args)
    if invalid:
        return invalid, False
    # 步骤 2：只有标了确认的操作才询问用户
    text = _risk_text(tool, args)
    if not text:
        return None, False
    if not _ask(text):
        return "用户未确认，操作已取消", False
    return None, True


def begin_confirmed(approved: bool):
    return _CONFIRMED.set(approved)


def end_confirmed(token) -> None:
    _CONFIRMED.reset(token)
