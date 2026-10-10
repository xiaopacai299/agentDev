"""Long-term memory kept apart from the session transcript."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from agentdev.runtime.config import home_dir, workspace_root

# 步骤 1：个人记忆放主目录，项目记忆放当前目录，并标出不能写入的内容
_KINDS = ("用户", "反馈", "项目", "引用")
_SCOPE_ALIASES = {"personal": "personal", "个人": "personal", "project": "project", "项目": "project"}
_REFERENCE_ALIASES = {"bug": "bug", "缺陷": "bug", "monitor": "monitor", "监控": "monitor", "wiki": "wiki", "文档": "wiki"}
_GARBAGE = (
    (re.compile(r"(?i)(\bdef\b|\bclass\b|\.py\b|\.js\b|\.ts\b|src[/\\])"), "代码模式和路径"),
    (re.compile(r"(?i)(\bgit\b|\bcommit\b)"), "git 历史"),
    (re.compile(r"(?i)(traceback|exception|stack|报错|调试|修复)"), "修复和调试细节"),
    (re.compile(r"(?i)(\btodo\b|\bfixme\b|openai_|\.env\b|配置里的任务|待办)"), "配置里的任务"),
    (re.compile(r"(?i)(status\s*=\s*(running|pending|done)|task_id|observations|本轮任务|临时任务)"), "临时任务状态"),
)


@dataclass
class UserProfile:
    background: str = ""
    granularity: str = ""

    def to_dict(self) -> dict:
        return {"background": self.background, "granularity": self.granularity}

    @classmethod
    def from_dict(cls, data: dict) -> UserProfile:
        return cls(
            background=str(data.get("background") or ""),
            granularity=str(data.get("granularity") or ""),
        )


@dataclass
class Feedback:
    rule: str
    reason: str
    scene: str
    scope: str

    def to_dict(self) -> dict:
        return {"rule": self.rule, "reason": self.reason, "scene": self.scene, "scope": self.scope}

    @classmethod
    def from_dict(cls, data: dict) -> Feedback:
        return cls(
            rule=str(data.get("rule") or ""),
            reason=str(data.get("reason") or ""),
            scene=str(data.get("scene") or ""),
            scope=str(data.get("scope") or ""),
        )


@dataclass
class ProjectFact:
    progress: str = ""
    deadline: str = ""
    motive: str = ""

    def to_dict(self) -> dict:
        return {"progress": self.progress, "deadline": self.deadline, "motive": self.motive}

    @classmethod
    def from_dict(cls, data: dict) -> ProjectFact:
        return cls(
            progress=str(data.get("progress") or ""),
            deadline=str(data.get("deadline") or ""),
            motive=str(data.get("motive") or ""),
        )


@dataclass
class Reference:
    title: str
    url: str
    kind: str
    when: str

    def to_dict(self) -> dict:
        return {"title": self.title, "url": self.url, "kind": self.kind, "when": self.when}

    @classmethod
    def from_dict(cls, data: dict) -> Reference:
        return cls(
            title=str(data.get("title") or ""),
            url=str(data.get("url") or ""),
            kind=str(data.get("kind") or ""),
            when=str(data.get("when") or ""),
        )


@dataclass
class Memory:
    user: UserProfile = field(default_factory=UserProfile)
    feedback: list[Feedback] = field(default_factory=list)
    project: ProjectFact = field(default_factory=ProjectFact)
    references: list[Reference] = field(default_factory=list)


# 步骤 2：读写单个记忆文件，坏文件按空处理
def _places(directory: Path | None) -> tuple[Path, Path]:
    if directory is not None:
        return directory, directory
    return home_dir() / "memory", workspace_root() / ".agent" / "memory"


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return default


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _fields(body: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for part in re.split(r"[；;]", body):
        if "=" in part:
            key, value = part.split("=", 1)
        elif "：" in part:
            key, value = part.split("：", 1)
        else:
            continue
        found[key.strip()] = value.strip()
    return found


def _rejection_reason(*parts: str) -> str:
    text = "\n".join(part for part in parts if part)
    for pattern, label in _GARBAGE:
        if pattern.search(text):
            return f"不能写入记忆：{label}"
    return ""


def _absolute_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return ""


def _save_user(directory: Path, profile: UserProfile) -> None:
    _write_json(directory / "user.json", profile.to_dict())


def _save_feedback(directory: Path, items: list[Feedback]) -> None:
    _write_json(directory / "feedback.json", [item.to_dict() for item in items])


def _save_project(directory: Path, fact: ProjectFact) -> None:
    _write_json(directory / "project.json", fact.to_dict())


def _save_references(directory: Path, items: list[Reference]) -> None:
    _write_json(directory / "references.json", [item.to_dict() for item in items])


def _load_folder(folder: Path) -> Memory:
    feedback_raw = _read_json(folder / "feedback.json", [])
    reference_raw = _read_json(folder / "references.json", [])
    if not isinstance(feedback_raw, list):
        feedback_raw = []
    if not isinstance(reference_raw, list):
        reference_raw = []
    return Memory(
        user=UserProfile.from_dict(_read_json(folder / "user.json", {})),
        feedback=[Feedback.from_dict(item) for item in feedback_raw if isinstance(item, dict)],
        project=ProjectFact.from_dict(_read_json(folder / "project.json", {})),
        references=[Reference.from_dict(item) for item in reference_raw if isinstance(item, dict)],
    )


def _user_profile(home: Path, work: Path) -> UserProfile:
    if (home / "user.json").exists():
        return _load_folder(home).user
    return _load_folder(work).user


def _personal_feedback(home: Path, work: Path) -> list[Feedback]:
    if (home / "feedback.json").exists():
        return [item for item in _load_folder(home).feedback if item.scope == "personal"]
    return [item for item in _load_folder(work).feedback if item.scope == "personal"]


def _remember_user(directory: Path | None, body: str) -> str:
    data = _fields(body)
    background = data.get("背景", "")
    granularity = data.get("颗粒度", "")
    if not background and not granularity:
        return "用户记忆需要背景或颗粒度。"
    reason = _rejection_reason(background, granularity)
    if reason:
        return reason
    home, work = _places(directory)
    current = _user_profile(home, work)
    if background:
        current.background = background
    if granularity:
        current.granularity = granularity
    _save_user(home, current)
    return "已记住用户。"


def _remember_feedback(directory: Path | None, body: str) -> str:
    data = _fields(body)
    rule = data.get("规则", "")
    why = data.get("原因", "")
    scene = data.get("场景", "")
    scope = _SCOPE_ALIASES.get(data.get("范围", ""), "")
    if not rule or not why or not scene or not scope:
        return "反馈记忆需要规则、原因、场景，以及范围 personal 或 project。"
    reason = _rejection_reason(rule, why, scene)
    if reason:
        return reason
    home, work = _places(directory)
    incoming = Feedback(rule=rule, reason=why, scene=scene, scope=scope)
    if home.resolve() == work.resolve():
        items = [item for item in _load_folder(home).feedback if not (item.rule == rule and item.scope == scope)]
        items.append(incoming)
        _save_feedback(home, items)
        return f"已记住反馈（{scope}）。"
    if scope == "personal":
        items = [item for item in _personal_feedback(home, work) if not (item.rule == rule and item.scope == scope)]
        items.append(incoming)
        _save_feedback(home, items)
        return f"已记住反馈（{scope}）。"
    existing = _load_folder(work).feedback
    personal = [item for item in existing if item.scope == "personal"]
    project_items = [
        item for item in existing if item.scope == "project" and not (item.rule == rule and item.scope == scope)
    ]
    project_items.append(incoming)
    _save_feedback(work, personal + project_items)
    return f"已记住反馈（{scope}）。"


def _remember_project(directory: Path | None, body: str) -> str:
    data = _fields(body)
    progress = data.get("进度", "")
    deadline = data.get("截止", "")
    motive = data.get("动机", "")
    if not progress and not deadline and not motive:
        return "项目记忆需要进度、截止或动机。"
    if deadline:
        parsed = _absolute_date(deadline)
        if not parsed:
            return "截止日期要写成绝对日期，例如 2026-10-17。"
        deadline = parsed
    reason = _rejection_reason(progress, motive)
    if reason:
        return reason
    _home, work = _places(directory)
    current = _load_folder(work).project
    if progress:
        current.progress = progress
    if deadline:
        current.deadline = deadline
    if motive:
        current.motive = motive
    _save_project(work, current)
    return "已记住项目。"


def _remember_reference(directory: Path | None, body: str) -> str:
    data = _fields(body)
    title = data.get("标题", "")
    url = data.get("地址", "")
    kind = _REFERENCE_ALIASES.get(data.get("类型", ""), "")
    when = data.get("何时", "")
    if not title or not url or not kind or not when:
        return "引用记忆需要标题、地址、类型（bug、monitor、wiki）和何时打开。"
    if not url.startswith(("http://", "https://")):
        return "引用地址要写成外部链接，不能写成本地路径。"
    reason = _rejection_reason(title, when)
    if reason:
        return reason
    _home, work = _places(directory)
    items = [item for item in _load_folder(work).references if item.url != url]
    items.append(Reference(title=title, url=url, kind=kind, when=when))
    _save_references(work, items)
    return "已记住引用。"


# 步骤 3：对外读取、渲染，以及只接受显式记住指令
def load_memory(directory: Path | None = None) -> Memory:
    home, work = _places(directory)
    if home.resolve() == work.resolve():
        return _load_folder(home)
    project_feedback = [item for item in _load_folder(work).feedback if item.scope == "project"]
    stored = _load_folder(work)
    return Memory(
        user=_user_profile(home, work),
        feedback=_personal_feedback(home, work) + project_feedback,
        project=stored.project,
        references=stored.references,
    )


def render_memory(memory: Memory) -> str:
    lines: list[str] = []
    if memory.user.background or memory.user.granularity:
        lines.append("用户记忆：")
        if memory.user.background:
            lines.append(f"- 背景：{memory.user.background}")
        if memory.user.granularity:
            lines.append(f"- 沟通颗粒度：{memory.user.granularity}")
    if memory.feedback:
        lines.append("反馈记忆：")
        for item in memory.feedback:
            lines.append(f"- [{item.scope}] {item.rule}。原因：{item.reason}。场景：{item.scene}")
    if memory.project.progress or memory.project.deadline or memory.project.motive:
        lines.append("项目记忆：")
        if memory.project.progress:
            lines.append(f"- 进度：{memory.project.progress}")
        if memory.project.deadline:
            lines.append(f"- 截止日期：{memory.project.deadline}")
        if memory.project.motive:
            lines.append(f"- 动机：{memory.project.motive}")
    if memory.references:
        lines.append("引用记忆：")
        for item in memory.references:
            lines.append(f"- {item.title}（{item.kind}）{item.url}。在{item.when}时打开，不要把链接正文当成已经读过。")
    return "\n".join(lines)


def remember_command(text: str, directory: Path | None = None) -> str:
    # 步骤 1：只接受以「记住」开头的显式指令
    raw = text.strip()
    if not raw.startswith("记住"):
        return "这不是一条记忆指令。"
    matched = re.match(r"^(用户|反馈|项目|引用)\s*[：:]\s*(.*)$", raw.removeprefix("记住").strip(), re.DOTALL)
    if matched is None:
        return "请写成：记住用户、记住反馈、记住项目或记住引用。"
    kind, body = matched.group(1), matched.group(2).strip()
    if kind not in _KINDS:
        return "请写成：记住用户、记住反馈、记住项目或记住引用。"
    # 步骤 2：按类型写入对应文件，垃圾内容和相对日期直接拒绝
    writers = {
        "用户": _remember_user,
        "反馈": _remember_feedback,
        "项目": _remember_project,
        "引用": _remember_reference,
    }
    return writers[kind](directory, body)
