"""File and command tools: read, write, edit, and bash."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from pathlib import Path

from langchain.tools import tool
from pydantic import BaseModel, Field

from agentdev.runtime.config import workspace_root
from agentdev.runtime.tool_guard import deletion_already_confirmed

# 步骤 1：限制单次读取和命令输出的长度，并识别删除命令
_MAX_READ_LINES = 200
_MAX_BASH_OUTPUT = 8000
_DELETE_COMMAND = re.compile(
    r"(?i)(\bRemove-Item\b|\brm\b|\brmdir\b|\brd\b|\bdel\b|\berase\b|\bri\b|\bunlink\b|"
    r"os\.remove\b|os\.unlink\b|shutil\.rmtree\b|::Delete\b|\bgit\s+clean\b)"
)


def resolve_path(path: str, root: Path | None = None) -> Path:
    # 步骤 1：相对路径从当前工作目录算起，绝对路径可以指向任意目录
    base = root if root is not None else workspace_root()
    raw = Path(path)
    candidate = raw if raw.is_absolute() else base / raw
    return candidate.resolve()


def describe_path(file: Path, root: Path) -> str:
    try:
        return str(file.relative_to(root.resolve()))
    except ValueError:
        return str(file)


def is_delete_command(command: str) -> bool:
    return _DELETE_COMMAND.search(command) is not None


def confirm_delete(command: str) -> bool:
    # 步骤 1：把将要执行的删除命令展示给用户
    print("\n即将删除文件，命令如下：")
    print(command)
    # 步骤 2：只有明确确认才继续
    try:
        answer = input("确认删除请输入 yes 或 确认：").strip().lower()
    except EOFError:
        return False
    return answer in {"yes", "确认"}


# 步骤 2：读取文件，并带上行号
def read_file_text(
    path: str,
    offset: int = 1,
    limit: int = _MAX_READ_LINES,
    root: Path | None = None,
) -> str:
    # 步骤 1：定位文件并读出全部行
    file = resolve_path(path, root)
    if not file.is_file():
        raise FileNotFoundError(f"文件不存在：{path}")
    lines = file.read_text(encoding="utf-8").splitlines()
    # 步骤 2：按起始行和行数截取
    start = max(int(offset), 1) - 1
    count = max(1, min(int(limit), _MAX_READ_LINES))
    selected = lines[start : start + count]
    if not selected:
        return "(没有更多内容)"
    return "\n".join(f"{start + index + 1}|{line}" for index, line in enumerate(selected))


# 步骤 3：整文件写入
def write_file_text(path: str, content: str, root: Path | None = None) -> str:
    # 步骤 1：确保父目录存在后覆盖写入
    base = root if root is not None else workspace_root()
    file = resolve_path(path, base)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(content, encoding="utf-8")
    return f"已写入 {describe_path(file, base)}，共 {len(content)} 个字符"


# 步骤 4：用一段原文精确替换成新文本
def edit_file_text(path: str, old_text: str, new_text: str, root: Path | None = None) -> str:
    # 步骤 1：原文必须唯一，避免补丁打错位置
    base = root if root is not None else workspace_root()
    file = resolve_path(path, base)
    if not file.is_file():
        raise FileNotFoundError(f"文件不存在：{path}")
    content = file.read_text(encoding="utf-8")
    count = content.count(old_text)
    if count == 0:
        raise ValueError("没有找到要替换的原文")
    if count > 1:
        raise ValueError(f"原文出现了 {count} 次，请提供更长的上下文")
    # 步骤 2：只替换这一处
    file.write_text(content.replace(old_text, new_text, 1), encoding="utf-8")
    return f"已替换 {describe_path(file, base)} 中的 1 处"


# 步骤 5：在项目根目录执行命令，删除前必须得到确认
def run_command(
    command: str,
    timeout: int = 30,
    root: Path | None = None,
    confirm: Callable[[str], bool] | None = None,
) -> str:
    # 步骤 1：删除命令先询问，未确认则不执行
    if not command.strip():
        raise ValueError("命令为空")
    if is_delete_command(command):
        approved = deletion_already_confirmed() or (confirm or confirm_delete)(command)
        if not approved:
            return "已取消删除，命令未执行"
    wait = max(1, min(int(timeout), 60))
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            cwd=root if root is not None else workspace_root(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=wait,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return f"命令超时（{wait} 秒）"
    # 步骤 2：合并输出并截断过长结果
    output = (completed.stdout + completed.stderr).strip()
    if len(output) > _MAX_BASH_OUTPUT:
        output = output[:_MAX_BASH_OUTPUT] + "\n...(输出已截断)"
    return f"退出码: {completed.returncode}\n{output or '(无输出)'}"


# 步骤 6：用一套模型约束工程工具参数
class ReadArgs(BaseModel):
    path: str = Field(min_length=1)
    offset: int = Field(default=1, ge=1)
    limit: int = Field(default=200, ge=1, le=200)


class WriteArgs(BaseModel):
    path: str = Field(min_length=1)
    content: str


class EditArgs(BaseModel):
    path: str = Field(min_length=1)
    old_text: str = Field(min_length=1)
    new_text: str


class BashArgs(BaseModel):
    command: str = Field(min_length=1, max_length=4000)
    timeout: int = Field(default=30, ge=1, le=60)


def _bash_risk(args: dict) -> str:
    command = str(args.get("command") or "")
    if is_delete_command(command):
        return command
    return ""


# 步骤 7：注册工程工具
@tool(args_schema=ReadArgs)
def read(path: str, offset: int = 1, limit: int = 200) -> str:
    """读取文本文件，返回带行号的内容。path 可以是任意目录的绝对路径，相对路径从当前工作目录算起。offset 是起始行，从 1 开始。limit 是最多读取的行数。"""
    try:
        return read_file_text(path, offset, limit)
    except (OSError, ValueError) as exc:
        return f"无法读取文件：{exc}"


@tool(args_schema=WriteArgs)
def write(path: str, content: str) -> str:
    """把 content 写入文件，覆盖已有内容。path 可以是任意目录的绝对路径，相对路径从当前工作目录算起。适合新建文件或重写整个文件。"""
    try:
        return write_file_text(path, content)
    except (OSError, ValueError) as exc:
        return f"无法写入文件：{exc}"


@tool(args_schema=EditArgs)
def edit(path: str, old_text: str, new_text: str) -> str:
    """把文件中唯一的 old_text 替换成 new_text。path 可以是任意目录的绝对路径。old_text 必须和文件内容完全一致，并且只出现一次。适合小段补丁，不要用来重写整个文件。"""
    try:
        return edit_file_text(path, old_text, new_text)
    except (OSError, ValueError) as exc:
        return f"无法编辑文件：{exc}"


@tool(args_schema=BashArgs, extras={"risk": "confirm", "risk_of": _bash_risk})
def bash(command: str, timeout: int = 30) -> str:
    """用 PowerShell 执行命令，返回退出码和输出。默认工作目录是当前目录，命令可以访问其他目录。command 是命令文本。timeout 是最长等待秒数，最大 60。删除文件的命令会先询问用户，只有用户输入 yes 或 确认后才会执行。"""
    try:
        return run_command(command, timeout)
    except (OSError, ValueError) as exc:
        return f"无法执行命令：{exc}"
