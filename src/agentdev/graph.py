"""Multi-agent graph: plan, retrieve, calculate, write, then review."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from agentdev.agent import message_text
from agentdev.loop import run_agent_loop, run_model_round, run_registered_tool
from agentdev.state import AgentState, PlanStep
from agentdev.tools import calculate, get_current_location, get_current_time, get_weather
from agentdev.workspace import bash, edit, read, write

# 步骤 1：约定每个子 Agent 的职责
RETRIEVAL_TOOLS = [get_current_time, get_current_location, get_weather]
CALCULATION_TOOLS = [calculate]
WORKSPACE_TOOLS = [read, write, edit, bash]
PLANNER_INSTRUCTION = """你是规划 Agent。把用户目标分给检索 Agent、计算 Agent、工程 Agent 和写作 Agent。
检索 Agent 负责时间、位置和天气。计算 Agent 只负责算术。工程 Agent 负责读取、写入、编辑项目文件和执行命令。写作 Agent 负责最终回答。
没有对应需求时，该任务用空字符串。
代词要结合对话历史。只输出 JSON：
{"retrieval_task": "", "calculation_task": "", "workspace_task": "", "writing_task": "写给用户的任务"}"""
REVIEW_INSTRUCTION = """你是审校 Agent。检查草稿是否完成用户目标，并且没有编造检索结果、计算结果和工程结果里不存在的事实。
只输出 JSON：{"pass": true, "reason": "通过原因"} 或 {"pass": false, "reason": "缺少什么"}"""


@dataclass(frozen=True)
class AgentTask:
    retrieval_task: str
    calculation_task: str
    writing_task: str
    workspace_task: str = ""


# 步骤 2：解析规划 Agent 和审校 Agent 的 JSON
def _strip_fence(text: str) -> str:
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.removesuffix("```").strip()
    return raw


def parse_agent_task(text: str, goal: str) -> AgentTask:
    try:
        data = json.loads(_strip_fence(text))
    except json.JSONDecodeError:
        return AgentTask("", "", goal, "")
    if not isinstance(data, dict):
        return AgentTask("", "", goal, "")
    writing = str(data.get("writing_task") or "").strip() or goal
    return AgentTask(
        retrieval_task=str(data.get("retrieval_task") or "").strip(),
        calculation_task=str(data.get("calculation_task") or "").strip(),
        writing_task=writing,
        workspace_task=str(data.get("workspace_task") or "").strip(),
    )


def parse_review(text: str) -> tuple[bool, str]:
    try:
        data = json.loads(_strip_fence(text))
    except json.JSONDecodeError:
        return True, "审校结果无法解析，放行当前草稿"
    if not isinstance(data, dict):
        return True, "审校结果无法解析，放行当前草稿"
    return bool(data.get("pass")), str(data.get("reason") or "").strip()


# 步骤 3：让一个子 Agent 在自己的工具循环里完成任务
def run_tool_agent(model, tools, system: str, task: str, on_tool=None) -> str:
    transcript = [
        {"role": "system", "content": system},
        {"role": "user", "content": task},
    ]
    return run_agent_loop(
        transcript,
        lambda messages: run_model_round(model, tools, messages),
        lambda call: run_registered_tool(tools, call),
        on_tool=on_tool,
    )


def ask_model(model, system: str, user: str) -> str:
    response = model.invoke(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
    )
    return message_text(response)


def stream_model(model, system: str, user: str, on_token=None) -> str:
    parts: list[str] = []
    for chunk in model.stream(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
    ):
        text = getattr(chunk, "text", "")
        text = text if isinstance(text, str) else str(text or "")
        if not text:
            continue
        parts.append(text)
        if on_token:
            on_token(text)
    return "".join(parts).strip()


# 步骤 4：按规划、检索、计算、写作、审校的顺序协作
def run_graph(
    state: AgentState,
    plan_fn: Callable[[str, str], AgentTask],
    retrieval_fn: Callable[[str], str],
    calculation_fn: Callable[[str], str],
    workspace_fn: Callable[[str], str],
    write_fn: Callable[[str, str, str, str, str], str],
    review_fn: Callable[[str, str, str, str, str], tuple[bool, str]],
    save_fn: Callable[[AgentState], None],
    on_event: Callable[[str, str], None] | None = None,
    max_reviews: int = 1,
) -> AgentState:
    # 步骤 1：从用户目标开始，审校不通过就带着意见回到规划
    goal = str(state.messages[-1]["content"])
    review_note = ""
    draft = ""
    attempts = 0
    state.status = "planning"
    while True:
        attempts += 1
        task = plan_fn(goal, review_note)
        state.plan = [
            PlanStep(text=f"检索: {task.retrieval_task or '不需要'}"),
            PlanStep(text=f"计算: {task.calculation_task or '不需要'}"),
            PlanStep(text=f"工程: {task.workspace_task or '不需要'}"),
            PlanStep(text=f"写作: {task.writing_task}"),
        ]
        save_fn(state)
        if on_event:
            on_event("planning", task.writing_task)

        # 步骤 2：检索和计算互相独立，都完成后再写作
        retrieval = ""
        if task.retrieval_task:
            retrieval = retrieval_fn(task.retrieval_task)
            state.observations.append(
                {"tool": "retrieval_agent", "args": {"task": task.retrieval_task}, "result": retrieval}
            )
            if on_event:
                on_event("retrieval", retrieval)
        calculation = ""
        if task.calculation_task:
            calculation = calculation_fn(task.calculation_task)
            state.observations.append(
                {
                    "tool": "calculation_agent",
                    "args": {"task": task.calculation_task},
                    "result": calculation,
                }
            )
            if on_event:
                on_event("calculation", calculation)
        workspace = ""
        if task.workspace_task and workspace_fn:
            workspace = workspace_fn(task.workspace_task)
            state.observations.append(
                {"tool": "workspace_agent", "args": {"task": task.workspace_task}, "result": workspace}
            )
            if on_event:
                on_event("workspace", workspace)
        state.status = "running"
        if on_event:
            on_event("writing", task.writing_task)
        draft = write_fn(goal, retrieval, calculation, workspace, review_note)
        passed, reason = review_fn(goal, draft, retrieval, calculation, workspace)
        if on_event:
            on_event("review", "通过" if passed else f"未通过：{reason}")
        for step in state.plan:
            step.status = "done"
            step.result = draft
        save_fn(state)
        if passed or attempts > max_reviews:
            break
        review_note = reason
        state.status = "planning"

    # 步骤 3：审校通过后把草稿写回会话
    state.messages.append({"role": "assistant", "content": draft})
    state.status = "done"
    state.step_count += attempts
    save_fn(state)
    return state


def build_graph_runners(model, on_tool=None, on_token=None):
    # 步骤 1：规划 Agent 决定要不要检索和计算
    def plan_fn(goal: str, review_note: str) -> AgentTask:
        user = f"用户目标：{goal}"
        if review_note:
            user += f"\n上一稿未通过审校：{review_note}\n请重新分配任务。"
        return parse_agent_task(ask_model(model, PLANNER_INSTRUCTION, user), goal)

    # 步骤 2：检索 Agent 和计算 Agent 各自使用自己的工具
    def retrieval_fn(task: str) -> str:
        return run_tool_agent(
            model,
            RETRIEVAL_TOOLS,
            "你是检索 Agent。只能使用时间、位置和天气工具，查完后用简体中文列出事实。",
            task,
            on_tool,
        )

    def calculation_fn(task: str) -> str:
        return run_tool_agent(
            model,
            CALCULATION_TOOLS,
            "你是计算 Agent。所有算术都必须调用 calculate，不要心算。只返回算式和结果。",
            task,
            on_tool,
        )

    def workspace_fn(task: str) -> str:
        return run_tool_agent(
            model,
            WORKSPACE_TOOLS,
            "你是工程 Agent。用 read 查看文件，用 write 新建或重写文件，用 edit 替换唯一的一小段，用 bash 执行命令。可以操作任意目录。删除文件时只能使用 bash 发出删除命令，系统会先询问用户；用户未确认时不要改写命令绕过。做完后简要说明结果。",
            task,
            on_tool,
        )

    # 步骤 3：写作 Agent 汇总，审校 Agent 决定是否退回规划
    def write_fn(
        goal: str,
        retrieval: str,
        calculation: str,
        workspace: str,
        review_note: str,
    ) -> str:
        user = (
            f"用户目标：{goal}\n"
            f"检索结果：{retrieval or '无'}\n"
            f"计算结果：{calculation or '无'}\n"
            f"工程结果：{workspace or '无'}\n"
        )
        if review_note:
            user += f"上一稿未通过的原因：{review_note}\n请重写。"
        return stream_model(
            model,
            "你是写作 Agent。只根据检索结果、计算结果和工程结果回答，不要编造其中没有的事实。使用简体中文。",
            user,
            on_token,
        )

    def review_fn(
        goal: str,
        draft: str,
        retrieval: str,
        calculation: str,
        workspace: str,
    ) -> tuple[bool, str]:
        user = (
            f"用户目标：{goal}\n"
            f"检索结果：{retrieval or '无'}\n"
            f"计算结果：{calculation or '无'}\n"
            f"工程结果：{workspace or '无'}\n"
            f"草稿：{draft}"
        )
        return parse_review(ask_model(model, REVIEW_INSTRUCTION, user))

    return plan_fn, retrieval_fn, calculation_fn, workspace_fn, write_fn, review_fn
