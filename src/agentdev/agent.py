"""Build the LangChain agent."""

from __future__ import annotations

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

from agentdev.config import Settings
from agentdev.tools import calculate, get_current_location, get_current_time, get_weather

# 步骤 1：约定助手何时调用工具
SYSTEM_PROMPT = """你是一个简洁的助手。
需要当前时间时调用 get_current_time。
需要精确计算时调用 calculate，不要心算。
需要用户当前位置时调用 get_current_location。
需要天气时调用 get_weather。用户指定了城市就传入城市名；问当前位置的天气时不要传 place。
回答使用简体中文。"""


# 步骤 2：把模型回复提取成纯文本
def message_text(message) -> str:
    # 步骤 1：取出消息正文
    content = getattr(message, "content", message)
    # 步骤 2：纯文本直接返回
    if isinstance(content, str):
        return content
    # 步骤 3：从内容块里收集文本
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    return "".join(parts)


# 步骤 3：按配置创建聊天模型
def build_model(settings: Settings):
    # 步骤 1：组装模型参数
    model_kwargs = {
        "model": settings.model,
        "model_provider": "openai",
        "api_key": settings.api_key,
        "temperature": settings.temperature,
    }
    # 步骤 2：使用兼容接口时传入地址
    if settings.base_url:
        model_kwargs["base_url"] = settings.base_url
    return init_chat_model(**model_kwargs)


# 步骤 4：列出规划器可见的工具
def tool_catalog() -> list[str]:
    tools = [get_current_time, calculate, get_current_location, get_weather]
    return [f"- {item.name}: {item.description}" for item in tools]


# 步骤 5：用配置创建可调用工具的 Agent
def build_agent(settings: Settings):
    model = build_model(settings)
    return create_agent(
        model=model,
        tools=[get_current_time, calculate, get_current_location, get_weather],
        system_prompt=SYSTEM_PROMPT,
    )
