"""Turn a user goal into an ordered plan."""

from __future__ import annotations

import json

from agentdev.agent import message_text

# 步骤 1：约定规划器只返回 JSON，并参考对话历史
PLAN_INSTRUCTION = """你是规划器。根据对话历史、用户当前目标和可用工具，把任务拆成 1 到 3 个顺序步骤。
可用工具：
{tools}

代词和省略要结合对话历史解析。历史里已经出现的人物、地点和事实，不要再当成未知对象，也不要安排向用户追问。
只输出 JSON，不要其他文字：
{{"steps": ["步骤一", "步骤二"]}}
最后一步必须是面向用户的最终回答。"""


# 步骤 2：从模型文本里解析步骤
def parse_plan(text: str) -> list[str]:
    # 步骤 1：去掉代码块包裹
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.removesuffix("```").strip()
    # 步骤 2：读取 steps 列表
    data = json.loads(raw)
    steps = data.get("steps") if isinstance(data, dict) else data
    if not isinstance(steps, list):
        raise ValueError("计划不是列表")
    cleaned = [str(item).strip() for item in steps if str(item).strip()]
    if not cleaned:
        raise ValueError("计划为空")
    return cleaned[:3]


# 步骤 3：把最近对话整理成规划上下文
def format_history(messages: list[dict], limit: int = 6) -> str:
    recent = messages[-limit:]
    if not recent:
        return "无"
    lines: list[str] = []
    for item in recent:
        role = "用户" if item.get("role") == "user" else "助手"
        lines.append(f"{role}: {item.get('content', '')}")
    return "\n".join(lines)


# 步骤 4：调用模型生成计划，失败时退回单步
def build_plan(
    model,
    goal: str,
    tool_lines: list[str],
    history: list[dict] | None = None,
) -> list[str]:
    # 步骤 1：请求规划，带上当前句之前的对话
    try:
        response = model.invoke(
            [
                {
                    "role": "system",
                    "content": PLAN_INSTRUCTION.format(tools="\n".join(tool_lines)),
                },
                {
                    "role": "user",
                    "content": (
                        f"对话历史：\n{format_history(history or [])}\n\n"
                        f"当前目标：{goal}"
                    ),
                },
            ]
        )
        # 步骤 2：解析步骤
        return parse_plan(message_text(response))
    except (ValueError, TypeError, AttributeError):
        # 步骤 3：无法规划时把原话当成唯一步骤
        return [goal]
