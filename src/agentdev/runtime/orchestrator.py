"""Two-layer orchestration: only the main loop may spawn workers, and only it writes the task table."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from agentdev.runtime.state import AgentState, PlanStep

# 步骤 1：锁死两层拓扑和并发上限
MAX_CONCURRENCY = 3
ORCHESTRATOR = "orchestrator"
CHILD_SPAWN_REJECTION = "子 Agent 不能派生子 Agent"
CAPACITY_REJECTION = "并发已满，路由层拒绝派生"


@dataclass(frozen=True)
class SpawnRequest:
    owner: str
    text: str
    run: Callable[[], str]


# 步骤 2：中心任务表只由主循环改写，子 Agent 只返回自己的结果
def _step_for(plan: list[PlanStep], owner: str) -> PlanStep | None:
    for step in plan:
        if step.owner == owner:
            return step
    return None


def _await_workers(accepted: list[SpawnRequest]) -> dict[str, tuple[str, str]]:
    # 步骤 1：没有可派任务时直接回到主循环
    if not accepted:
        return {}
    outcomes: dict[str, tuple[str, str]] = {}

    def invoke(request: SpawnRequest) -> tuple[str, str, str]:
        try:
            return request.owner, "done", request.run()
        except Exception as exc:
            return request.owner, "failed", f"失败：{exc}"

    # 步骤 2：主循环在这里挂起，等本批子 Agent 全部结束
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        futures = [pool.submit(invoke, request) for request in accepted]
        for future in futures:
            owner, status, result = future.result()
            outcomes[owner] = (status, result)
    return outcomes


def _record_worker(state: AgentState, owner: str, status: str, result: str) -> None:
    step = _step_for(state.plan, owner)
    if step is None:
        return
    step.status = status
    step.result = result
    state.observations.append(
        {"tool": f"{owner}_agent", "args": {"task": step.text}, "result": result}
    )


# 步骤 3：对外提供路由、任务表和并行汇合
def route_spawn(
    caller: str,
    requests: list[SpawnRequest],
    running: int = 0,
) -> tuple[list[SpawnRequest], list[tuple[SpawnRequest, str]]]:
    # 步骤 1：子节点没有派生权，请求整批退回
    if caller != ORCHESTRATOR:
        return [], [(item, CHILD_SPAWN_REJECTION) for item in requests]
    # 步骤 2：剩余名额不够时，多出来的请求直接拒绝
    slots = max(0, MAX_CONCURRENCY - running)
    accepted = list(requests[:slots])
    rejected = [(item, CAPACITY_REJECTION) for item in requests[slots:]]
    return accepted, rejected


def build_task_rows(jobs: list[tuple[str, str]], attempt: int) -> list[PlanStep]:
    rows: list[PlanStep] = []
    for owner, text in jobs:
        if not str(text).strip():
            continue
        rows.append(PlanStep(text=text, task_id=f"{owner}-{attempt}", owner=owner))
    return rows


def step_for(plan: list[PlanStep], owner: str) -> PlanStep | None:
    return _step_for(plan, owner)


def result_of(plan: list[PlanStep], owner: str) -> str:
    step = _step_for(plan, owner)
    if step is None:
        return ""
    return step.result


def run_workers(
    state: AgentState,
    requests: list[SpawnRequest],
    save_fn: Callable[[AgentState], None],
    on_event: Callable[[str, str], None] | None = None,
    owner_order: tuple[str, ...] = (),
) -> None:
    # 步骤 1：扫描待派任务，满载或越权的请求在路由层拒绝
    accepted, rejected = route_spawn(ORCHESTRATOR, requests)
    for request, reason in rejected:
        _record_worker(state, request.owner, "rejected", reason)
    for request in accepted:
        step = _step_for(state.plan, request.owner)
        if step is not None:
            step.status = "running"
    state.status = "running"
    save_fn(state)
    # 步骤 2：挂起等待，再由主循环按所属写回结果
    outcomes = _await_workers(accepted)
    order = owner_order or tuple(request.owner for request in accepted)
    for owner in order:
        if owner not in outcomes:
            continue
        status, result = outcomes[owner]
        _record_worker(state, owner, status, result)
        if on_event:
            on_event(owner, result)
    save_fn(state)
