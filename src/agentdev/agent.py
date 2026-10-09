"""Build the LangChain agent."""

from __future__ import annotations

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

from agentdev.config import Settings
from agentdev.tools import calculate, get_current_time

SYSTEM_PROMPT = """你是一个简洁的助手。
需要当前时间时调用 get_current_time。
需要精确计算时调用 calculate，不要心算。
回答使用简体中文。"""


def build_agent(settings: Settings):
    model_kwargs = {
        "model": settings.model,
        "model_provider": "openai",
        "api_key": settings.api_key,
        "temperature": settings.temperature,
    }
    if settings.base_url:
        model_kwargs["base_url"] = settings.base_url

    model = init_chat_model(**model_kwargs)
    return create_agent(
        model=model,
        tools=[get_current_time, calculate],
        system_prompt=SYSTEM_PROMPT,
    )


def message_text(message) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    return "".join(parts)
