"""Persist agent state so a restart does not drop the session."""

from __future__ import annotations

import json
from pathlib import Path

from agentdev.config import PROJECT_ROOT
from agentdev.state import AgentState, new_state

# 步骤 1：约定会话文件位置
SESSION_PATH = PROJECT_ROOT / ".agent" / "session.json"


# 步骤 2：从磁盘恢复会话
def load_state(path: Path = SESSION_PATH) -> AgentState:
    # 步骤 1：没有文件时创建新会话
    if not path.exists():
        return new_state()
    # 步骤 2：读取并还原状态
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        state = AgentState.from_dict(data)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return new_state()
    # 步骤 3：中断的轮次回到空闲，避免卡在执行中
    if state.status in {"planning", "running"}:
        state.status = "idle"
    return state


# 步骤 3：把当前状态写回磁盘
def save_state(state: AgentState, path: Path = SESSION_PATH) -> None:
    # 步骤 1：确保目录存在
    path.parent.mkdir(parents=True, exist_ok=True)
    # 步骤 2：整份状态覆盖写入
    path.write_text(
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
