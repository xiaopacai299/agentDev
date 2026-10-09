"""Action loop: plan, call tools, update state, repeat until the turn is done."""

from __future__ import annotations

from collections.abc import Callable

from langchain_core.messages import ToolMessage

from agentdev.agent import SYSTEM_PROMPT, message_text
from agentdev.state import AgentState, PlanStep

# 步骤 1：只在模型停不下来时打断，正常结束条件是不再调用工具
SAFETY_ROUNDS = 20


# 步骤 2：从本次模型回复里收集工具调用
def extract_observations(messages) -> list[dict]:
    pending: dict[str, dict] = {}
    order: list[str] = []
    for message in messages:
        for call in getattr(message, "tool_calls", None) or []:
            call_id = str(call.get("id") or len(order))
            pending[call_id] = {
                "tool": call.get("name") or "",
                "args": call.get("args") or {},
                "result": "",
            }
            order.append(call_id)
        if getattr(message, "type", None) == "tool":
            call_id = str(getattr(message, "tool_call_id", "") or "")
            content = message_text(message)
            if call_id in pending:
                pending[call_id]["result"] = content
            else:
                extra_id = f"tool-{len(order)}"
                pending[extra_id] = {
                    "tool": getattr(message, "name", "") or "",
                    "args": {},
                    "result": content,
                }
                order.append(extra_id)
    return [pending[call_id] for call_id in order]


# 步骤 3：取出模型增量里的可见文字
def visible_text(token) -> str:
    if getattr(token, "tool_call_chunks", None):
        return ""
    text = getattr(token, "text", "")
    return text if isinstance(text, str) else str(text or "")


# 步骤 4：边生成边回调，并收集工具结果
def consume_agent_stream(agent, messages, on_token=None, on_tool=None) -> tuple[str, list[dict]]:
    # 步骤 1：逐块读取模型输出和工具更新
    parts: list[str] = []
    collected: list = []
    printed_tools = 0
    for part in agent.stream(
        {"messages": messages},
        stream_mode=["messages", "updates"],
        version="v2",
    ):
        if part["type"] == "messages":
            token, _metadata = part["data"]
            text = visible_text(token)
            if not text:
                continue
            parts.append(text)
            if on_token:
                on_token(text)
            continue
        if part["type"] != "updates":
            continue
        for source, update in part["data"].items():
            if str(source).startswith("__") or not isinstance(update, dict):
                continue
            update_messages = update.get("messages") or []
            if isinstance(update_messages, list):
                collected.extend(update_messages)
        # 步骤 2：工具结果一到就回调，不等整段结束
        observations = extract_observations(collected)
        ready = [item for item in observations if item["result"]]
        fresh = ready[printed_tools:]
        printed_tools = len(ready)
        if on_tool and fresh:
            on_tool(fresh)
    return "".join(parts).strip(), extract_observations(collected)


# 步骤 5：拼出带计划和历史的模型输入
def build_transcript(state: AgentState) -> list:
    plan = "\n".join(f"{index}. {step.text}" for index, step in enumerate(state.plan, 1))
    system = (
        f"{SYSTEM_PROMPT}\n"
        f"本轮计划：\n{plan}\n"
        "可以多次调用工具。信息足够、不再调用工具时，直接给出最终答案。"
    )
    history = [item for item in state.messages if item.get("role") in {"user", "assistant"}]
    return [{"role": "system", "content": system}, *history]


# 步骤 6：请求一次模型，有工具调用就返回调用，没有则返回最终答案
def run_model_round(model, tools, transcript, on_token=None) -> tuple[str, list, object | None]:
    # 步骤 1：流式接收这一次生成
    gathered = None
    for chunk in model.bind_tools(tools).stream(transcript):
        gathered = chunk if gathered is None else gathered + chunk
        text = visible_text(chunk)
        if text and on_token:
            on_token(text)
    if gathered is None:
        return "", [], None
    # 步骤 2：区分工具调用和最终答案
    tool_calls = list(getattr(gathered, "tool_calls", None) or [])
    return message_text(gathered), tool_calls, gathered


# 步骤 7：执行一个工具调用
def run_registered_tool(tools, call: dict) -> str:
    found = {item.name: item for item in tools}
    tool = found.get(call.get("name"))
    if tool is None:
        return f"没有这个工具：{call.get('name')}"
    try:
        return str(tool.invoke(call.get("args") or {}))
    except Exception as exc:
        return f"工具执行失败：{exc}"


def tool_result_message(call: dict, result: str) -> ToolMessage:
    return ToolMessage(
        content=result,
        tool_call_id=str(call.get("id") or ""),
        name=str(call.get("name") or ""),
    )


# 步骤 8：单个子 Agent 内部循环，没有工具调用时返回最终文字
def run_agent_loop(
    transcript: list,
    generate_fn: Callable[[list], tuple[str, list, object | None]],
    run_tool_fn: Callable[[dict], str],
    on_tool: Callable[[list[dict]], None] | None = None,
    safety_rounds: int = SAFETY_ROUNDS,
) -> str:
    # 步骤 1：还有工具调用就执行并写回对话
    rounds = 0
    while True:
        rounds += 1
        if rounds > safety_rounds:
            return "工具调用未能结束"
        text, tool_calls, ai_message = generate_fn(transcript)
        if not tool_calls:
            return text
        if ai_message is not None:
            transcript.append(ai_message)
        observations = []
        for call in tool_calls:
            result = run_tool_fn(call)
            observations.append(
                {
                    "tool": call.get("name") or "",
                    "args": call.get("args") or {},
                    "result": result,
                }
            )
            transcript.append(tool_result_message(call, result))
        if on_tool and observations:
            on_tool(observations)


# 步骤 9：按「有工具就继续，没有工具就结束」循环
def run_turn(
    state: AgentState,
    plan_fn: Callable[[str], list[str]],
    generate_fn: Callable[[list], tuple[str, list, object | None]],
    run_tool_fn: Callable[[dict], str],
    save_fn: Callable[[AgentState], None],
    on_plan: Callable[[list[PlanStep]], None] | None = None,
    on_tool: Callable[[list[dict]], None] | None = None,
    safety_rounds: int = SAFETY_ROUNDS,
) -> AgentState:
    # 步骤 1：规划并写入状态
    state.status = "planning"
    goal = str(state.messages[-1]["content"])
    steps = plan_fn(goal) or [goal]
    state.plan = [PlanStep(text=item) for item in steps]
    save_fn(state)
    if on_plan:
        on_plan(state.plan)

    # 步骤 2：模型还在调用工具就执行并写回，不再调用就结束
    state.status = "running"
    transcript = build_transcript(state)
    final = ""
    rounds = 0
    while True:
        rounds += 1
        if rounds > safety_rounds:
            state.status = "failed"
            final = final or "工具调用未能结束"
            break
        try:
            text, tool_calls, ai_message = generate_fn(transcript)
        except Exception as exc:
            state.status = "failed"
            final = f"这一步失败：{exc}"
            break
        state.step_count += 1
        if not tool_calls:
            final = text
            break
        if ai_message is not None:
            transcript.append(ai_message)
        observations = []
        for call in tool_calls:
            result = run_tool_fn(call)
            observations.append(
                {
                    "tool": call.get("name") or "",
                    "args": call.get("args") or {},
                    "result": result,
                }
            )
            transcript.append(tool_result_message(call, result))
        if on_tool and observations:
            on_tool(observations)
        state.observations.extend(observations)
        save_fn(state)

    # 步骤 3：把最终回答写回会话
    for step in state.plan:
        step.status = "done"
        if not step.result:
            step.result = final
    state.messages.append({"role": "assistant", "content": final})
    if state.status != "failed":
        state.status = "done"
    save_fn(state)
    return state
