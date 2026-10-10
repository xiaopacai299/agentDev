"""Assemble this assistant's prompt, tools, and LangChain agent."""

from __future__ import annotations

from langchain.agents import create_agent

from agentdev.agents.assistant.tools import calculate, get_current_location, get_current_time, get_weather
from agentdev.agents.assistant.workspace import bash, edit, read, write
from agentdev.runtime.config import Settings
from agentdev.runtime.model import build_model

# 步骤 1：约定助手何时调用工具
SYSTEM_PROMPT = """你是一个简洁的助手。
需要当前时间时调用 get_current_time。
需要精确计算时调用 calculate，不要心算。
需要用户当前位置时调用 get_current_location。
需要天气或未来出行参考时调用 get_weather。用户指定了城市就传入 place；问当前位置时不要传 place。问今天时 days 用 1；问未来某天或连续几天时传入 start_date（YYYY-MM-DD）和 days。
需要查看文件时调用 read，新建或重写文件时调用 write，修改一小段时调用 edit，执行命令时调用 bash。这些操作可以指向任意目录。删除文件必须通过 bash，并等待用户确认。
回答使用简体中文。"""


# 步骤 2：列出这个助手可以使用的工具
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


# 步骤 3：用配置创建可调用工具的 Agent
def build_agent(settings: Settings):
    model = build_model(settings)
    return create_agent(
        model=model,
        tools=AGENT_TOOLS,
        system_prompt=SYSTEM_PROMPT,
    )
