import json

from agentdev.cli import colored
from agentdev.loop import consume_agent_stream, extract_observations, run_turn, visible_text
from agentdev.memory import load_state, save_state
from agentdev.planning import build_plan, format_history, parse_plan
from agentdev.state import AgentState, new_state


def test_parse_plan_reads_json_fence():
    text = '```json\n{"steps": ["查天气", "回答用户"]}\n```'
    assert parse_plan(text) == ["查天气", "回答用户"]


def test_build_plan_sends_recent_history():
    class Response:
        content = '{"steps": ["回答李白的籍贯"]}'

    class Model:
        def __init__(self):
            self.messages = None

        def invoke(self, messages):
            self.messages = messages
            return Response()

    model = Model()
    history = [
        {"role": "user", "content": "李白是谁"},
        {"role": "assistant", "content": "李白是唐代诗人"},
    ]
    steps = build_plan(model, "他是哪里人", ["- calculate: 计算"], history)
    assert steps == ["回答李白的籍贯"]
    assert "李白是唐代诗人" in model.messages[1]["content"]
    assert format_history([]) == "无"


def test_parse_plan_limits_to_three_steps():
    text = json.dumps({"steps": ["一", "二", "三", "四"]})
    assert parse_plan(text) == ["一", "二", "三"]


def test_state_roundtrip():
    state = new_state()
    state.messages.append({"role": "user", "content": "你好"})
    restored = AgentState.from_dict(state.to_dict())
    assert restored.session_id == state.session_id
    assert restored.messages == state.messages


def test_memory_survives_reload(tmp_path):
    path = tmp_path / "session.json"
    state = new_state()
    state.messages.append({"role": "user", "content": "记住我"})
    state.status = "running"
    save_state(state, path)

    loaded = load_state(path)
    assert loaded.session_id == state.session_id
    assert loaded.messages[0]["content"] == "记住我"
    assert loaded.status == "idle"


def test_extract_observations_pairs_tool_results():
    class CallMessage:
        tool_calls = [{"id": "1", "name": "calculate", "args": {"expression": "1+1"}}]

    class ToolMessage:
        type = "tool"
        tool_call_id = "1"
        name = "calculate"
        content = "2"

    observations = extract_observations([CallMessage(), ToolMessage()])
    assert observations == [
        {"tool": "calculate", "args": {"expression": "1+1"}, "result": "2"}
    ]


def test_colored_wraps_text_and_resets():
    assert colored("计划", "36") == "\033[36m计划\033[0m"


def test_visible_text_skips_tool_call_chunks():
    class ToolChunk:
        text = ""
        tool_call_chunks = [{"name": "calculate"}]

    assert visible_text(ToolChunk()) == ""


def test_consume_stream_emits_tokens_in_order():
    class Chunk:
        def __init__(self, text: str):
            self.text = text

    class Agent:
        def stream(self, payload, **kwargs):
            yield {"type": "messages", "data": (Chunk("北"), {})}
            yield {"type": "messages", "data": (Chunk("京"), {})}

    tokens: list[str] = []
    reply, observations = consume_agent_stream(Agent(), [], on_token=tokens.append)
    assert tokens == ["北", "京"]
    assert reply == "北京"
    assert observations == []


def test_consume_stream_prints_tool_before_later_tokens():
    class Chunk:
        def __init__(self, text: str):
            self.text = text

    class ToolMessage:
        type = "tool"
        tool_call_id = "1"
        name = "get_weather"
        content = "晴"

    class Agent:
        def stream(self, payload, **kwargs):
            yield {
                "type": "updates",
                "data": {"tools": {"messages": [ToolMessage()]}},
            }
            yield {"type": "messages", "data": (Chunk("晴天"), {})}

    events: list[str] = []
    reply, observations = consume_agent_stream(
        Agent(),
        [],
        on_token=events.append,
        on_tool=lambda items: events.append(items[0]["tool"]),
    )
    assert events == ["get_weather", "晴天"]
    assert reply == "晴天"
    assert observations[0]["result"] == "晴"


def test_run_turn_updates_state_and_saves():
    state = new_state()
    state.messages.append({"role": "user", "content": "算一下"})
    saved: list[AgentState] = []

    def plan_fn(goal: str) -> list[str]:
        return ["调用计算器", "回答用户"]

    def execute_fn(current, step_text, prior):
        return f"完成:{step_text}", [{"tool": "calculate", "args": {}, "result": "2"}]

    result = run_turn(state, plan_fn, execute_fn, saved.append)
    assert [step.status for step in result.plan] == ["done", "done"]
    assert result.status == "done"
    assert result.messages[-1]["content"] == "完成:回答用户"
    assert result.observations[-1]["tool"] == "calculate"
    assert saved[-1].status == "done"


def test_run_turn_stops_at_max_steps():
    state = new_state()
    state.messages.append({"role": "user", "content": "很多步"})

    result = run_turn(
        state,
        plan_fn=lambda goal: ["一步", "二步", "三步"],
        execute_fn=lambda current, step_text, prior: ("ok", []),
        save_fn=lambda current: None,
        max_steps=1,
    )
    assert result.status == "failed"
    assert result.step_count == 1
    assert result.plan[1].result == "已达到本轮最大步数"
