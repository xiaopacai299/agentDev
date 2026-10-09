"""Build the LangChain agent."""

from __future__ import annotations

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

from agentdev.config import Settings
from agentdev.tools import calculate, get_current_location, get_current_time, get_weather
from agentdev.workspace import bash, edit, read, write

# 步骤 1：约定助手何时调用工具
SYSTEM_PROMPT = """你是一个简洁的助手。
需要当前时间时调用 get_current_time。
需要精确计算时调用 calculate，不要心算。
需要用户当前位置时调用 get_current_location。
需要天气或未来出行参考时调用 get_weather。用户指定了城市就传入 place；问当前位置时不要传 place。问今天时 days 用 1；问未来某天或连续几天时传入 start_date（YYYY-MM-DD）和 days。
需要查看文件时调用 read，新建或重写文件时调用 write，修改一小段时调用 edit，执行命令时调用 bash。这些操作可以指向任意目录。删除文件必须通过 bash，并等待用户确认。
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
AGENT_TOOLS = [
    get_current_time,
    calculate,
    get_current_location,
    get_weather,
    read,
    write,
    edit,
    bash,
]


def tool_catalog() -> list[str]:
    return [f"- {item.name}: {item.description}" for item in AGENT_TOOLS]


# 步骤 5：用配置创建可调用工具的 Agent
def build_agent(settings: Settings):
    model = build_model(settings)
    return create_agent(
        model=model,
        tools=AGENT_TOOLS,
        system_prompt=SYSTEM_PROMPT,
    )
