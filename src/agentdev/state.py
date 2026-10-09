"""Agent state: the single source of truth for one session."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


# 步骤 1：声明计划中的一步
@dataclass
class PlanStep:
    text: str
    status: str = "pending"
    result: str = ""

    def to_dict(self) -> dict:
        return {"text": self.text, "status": self.status, "result": self.result}

    @classmethod
    def from_dict(cls, data: dict) -> PlanStep:
        return cls(
            text=str(data["text"]),
            status=str(data.get("status", "pending")),
            result=str(data.get("result", "")),
        )


# 步骤 2：声明会话状态
@dataclass
class AgentState:
    session_id: str
    messages: list[dict] = field(default_factory=list)
    plan: list[PlanStep] = field(default_factory=list)
    observations: list[dict] = field(default_factory=list)
    status: str = "idle"
    step_count: int = 0

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "messages": self.messages,
            "plan": [step.to_dict() for step in self.plan],
            "observations": self.observations,
            "status": self.status,
            "step_count": self.step_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AgentState:
        return cls(
            session_id=str(data["session_id"]),
            messages=list(data.get("messages") or []),
            plan=[PlanStep.from_dict(item) for item in data.get("plan") or []],
            observations=list(data.get("observations") or []),
            status=str(data.get("status", "idle")),
            step_count=int(data.get("step_count", 0)),
        )


# 步骤 3：创建一份空会话
def new_state() -> AgentState:
    return AgentState(session_id=uuid4().hex)
