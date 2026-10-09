"""Action loop: plan, call tools, update state, repeat until the turn is done."""

from __future__ import annotations

from collections.abc import Callable

from agentdev.agent import message_text
from agentdev.state import AgentState, PlanStep

# 步骤 1：约定一轮最多执行几步
MAX_STEPS_PER_TURN = 4


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


# 步骤 5：让带工具的 Agent 完成当前这一步
def execute_step(
    agent,
    state: AgentState,
    step_text: str,
    prior: list[str],
    on_token=None,
    on_tool=None,
) -> tuple[str, list[dict]]:
    # 步骤 1：拼出只针对当前步骤的指令
    done = "\n".join(prior) or "无"
    instruction = (
        f"当前要完成的步骤：{step_text}\n"
        f"本轮前面步骤的结果：\n{done}\n"
        "对话历史里已经说明的人物和事实直接使用，不要把代词当成没有指代对象。\n"
        "需要外部能力时调用工具。用简体中文给出这一步的结果。"
    )
    history = [item for item in state.messages if item.get("role") in {"user", "assistant"}]
    # 步骤 2：流式执行并收集工具结果
    return consume_agent_stream(
        agent,
        [*history, {"role": "user", "content": instruction}],
        on_token=on_token,
        on_tool=on_tool,
    )


# 步骤 6：按计划循环，直到步骤完成或达到上限
def run_turn(
    state: AgentState,
    plan_fn: Callable[[str], list[str]],
    execute_fn: Callable[[AgentState, str, list[str]], tuple[str, list[dict]]],
    save_fn: Callable[[AgentState], None],
    max_steps: int = MAX_STEPS_PER_TURN,
    on_plan: Callable[[list[PlanStep]], None] | None = None,
) -> AgentState:
    # 步骤 1：规划并写入状态
    state.status = "planning"
    goal = str(state.messages[-1]["content"])
    steps = plan_fn(goal) or [goal]
    state.plan = [PlanStep(text=item) for item in steps]
    save_fn(state)
    if on_plan:
        on_plan(state.plan)

    # 步骤 2：逐步执行，每步更新状态并保存
    state.status = "running"
    prior: list[str] = []
    taken = 0
    for step in state.plan:
        if taken >= max_steps:
            state.status = "failed"
            step.result = "已达到本轮最大步数"
            break
        step.status = "doing"
        save_fn(state)
        try:
            reply, observations = execute_fn(state, step.text, prior)
        except Exception as exc:
            reply, observations = f"这一步失败：{exc}", []
            state.status = "failed"
        step.result = reply
        step.status = "done"
        state.observations.extend(observations)
        state.step_count += 1
        taken += 1
        prior.append(f"{step.text}: {reply}")
        save_fn(state)
        if state.status == "failed":
            break

    # 步骤 3：把最终回答写回会话
    final = next((step.result for step in reversed(state.plan) if step.result), "")
    state.messages.append({"role": "assistant", "content": final})
    if state.status != "failed":
        state.status = "done"
    save_fn(state)
    return state
