from agentdev.graph import parse_agent_task, parse_review, run_graph
from agentdev.state import new_state

# 测试场景：出行计划必须同时用到检索 Agent 和计算 Agent。
# 往返高铁 553 元，住宿 420 元 1 晚，餐饮每天 300 元共 2 天，总花费 1573 元。
TRAVEL_TASK = (
    "下周六去上海玩2天。先查这个行程的天气，再计算总花费："
    "往返高铁553元，住宿每晚420元住1晚，餐饮每天300元共2天。"
    "最后说明天气是否适合出门，并给出总花费。"
)
WEATHER = "周六小雨，周日多云，有雨具即可出门"
TOTAL = "1573"


def test_parse_agent_task_reads_specialist_jobs():
    text = """```json
{"retrieval_task": "查上海天气", "calculation_task": "553+420+600", "writing_task": "写计划"}
```"""
    task = parse_agent_task(text, "出行")
    assert task.retrieval_task == "查上海天气"
    assert task.calculation_task == "553+420+600"
    assert task.writing_task == "写计划"


def test_parse_review_rejects_incomplete_draft():
    passed, reason = parse_review('{"pass": false, "reason": "没有总花费"}')
    assert passed is False
    assert reason == "没有总花费"


def test_travel_plan_uses_retrieval_calculation_and_review_retry():
    state = new_state()
    state.messages.append({"role": "user", "content": TRAVEL_TASK})
    calls = {"plan": 0, "write": 0, "retrieval": 0, "calculation": 0}
    events: list[str] = []

    def plan_fn(goal, review_note):
        calls["plan"] += 1
        assert goal == TRAVEL_TASK
        if calls["plan"] > 1:
            assert "总花费" in review_note
        return parse_agent_task(
            '{"retrieval_task": "查上海两天天气", "calculation_task": "553+420+300*2", "writing_task": "写出天气建议和总花费"}',
            goal,
        )

    def retrieval_fn(task):
        calls["retrieval"] += 1
        assert "天气" in task
        return WEATHER

    def calculation_fn(task):
        calls["calculation"] += 1
        assert "553" in task
        return f"553+420+600={TOTAL}"

    def write_fn(goal, retrieval, calculation, review_note):
        calls["write"] += 1
        assert WEATHER in retrieval
        assert TOTAL in calculation
        if review_note:
            return f"上海{WEATHER}。总花费 {TOTAL} 元，带伞可以出门。"
        return "可以出门。"

    def review_fn(goal, draft, retrieval, calculation):
        if TOTAL not in draft or "小雨" not in draft:
            return False, "草稿没有同时写明天气和小雨对应的总花费"
        return True, "天气和总花费都在"

    result = run_graph(
        state,
        plan_fn,
        retrieval_fn,
        calculation_fn,
        write_fn,
        review_fn,
        save_fn=lambda current: None,
        on_event=lambda kind, text: events.append(kind),
    )

    assert calls == {"plan": 2, "write": 2, "retrieval": 2, "calculation": 2}
    assert result.status == "done"
    assert TOTAL in result.messages[-1]["content"]
    assert "小雨" in result.messages[-1]["content"]
    assert events.count("review") == 2
    assert "retrieval_agent" in {item["tool"] for item in result.observations}
    assert "calculation_agent" in {item["tool"] for item in result.observations}
