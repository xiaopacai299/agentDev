"""Interactive command-line chat."""

from __future__ import annotations

import argparse
import sys

from agentdev.agents.assistant.graph import build_graph_runners, run_graph
from agentdev.runtime.config import home_dir, load_settings, workspace_root
from agentdev.runtime.model import build_model
from agentdev.runtime.memory import load_state, save_state
from agentdev.runtime.memory_store import remember_command
from agentdev.runtime.setup import run_setup
from agentdev.runtime.state import new_state

# 灰色提示、品红输入、青色计划、黄色工具、绿色回答
HINT = "90"
USER = "35"
PLAN = "36"
TOOL = "33"
ANSWER = "32"


# 步骤 1：打开终端颜色并按内容上色
def enable_ansi() -> None:
    if sys.platform != "win32":
        return
    import ctypes

    kernel = ctypes.windll.kernel32
    handle = kernel.GetStdHandle(-11)
    mode = ctypes.c_uint()
    if kernel.GetConsoleMode(handle, ctypes.byref(mode)):
        kernel.SetConsoleMode(handle, mode.value | 0x0004)


def colored(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m"


def paint(text: str, code: str, end: str = "\n") -> None:
    print(colored(text, code), end=end, flush=True)


# 步骤 2：按子 Agent 角色上色
def show_agent_event(kind: str, text: str) -> None:
    preview = text if len(text) <= 240 else text[:240] + "..."
    if kind == "planning":
        paint(f"规划 Agent: {preview}", PLAN)
    elif kind == "retrieval":
        paint(f"检索 Agent: {preview}", "34")
    elif kind == "calculation":
        paint(f"计算 Agent: {preview}", "33")
    elif kind == "workspace":
        paint(f"工程 Agent: {preview}", "34")
    elif kind == "writing":
        paint("写作 Agent:", ANSWER)
    elif kind == "review":
        paint(f"审校 Agent: {preview}", "32" if preview.startswith("通过") else "31")


# 步骤 3：用黄色打印刚完成的工具
def print_tools(observations) -> None:
    for item in observations:
        paint(f"\n工具: {item['tool']} {item['args']} => {item['result']}", TOOL)


HELP = """命令：
/help     查看命令
/status   查看当前模型和工作目录
/model    重新选择服务商、模型和 API Key
/new      清空当前会话，保留长期记忆
/exit     退出
记住...   写入长期记忆，例如：记住用户：背景=后端；颗粒度=少术语"""


def show_status(settings) -> None:
    endpoint = settings.base_url or "https://api.openai.com/v1"
    paint(f"模型：{settings.model}", HINT)
    paint(f"接口：{endpoint}", HINT)
    paint(f"工作目录：{workspace_root()}", HINT)
    paint(f"配置文件：{home_dir() / '.env'}", HINT)


# 步骤 4：进行多轮对话，并在每轮后保存状态
def run_chat(settings=None) -> None:
    # 步骤 1：打开颜色，没有密钥时先让用户接通模型
    enable_ansi()
    if settings is None:
        try:
            settings = load_settings()
        except RuntimeError:
            settings = run_setup()
    model = build_model(settings)
    state = load_state()

    # 步骤 2：用灰色提示模型和会话恢复情况
    show_status(settings)
    if state.messages:
        paint(f"已恢复会话，历史消息 {len(state.messages)} 条。", HINT)
    paint("输入 /help 查看命令。", HINT)

    while True:
        # 步骤 3：读取用户输入，中断时结束
        try:
            user_text = input(colored("你: ", USER)).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        # 步骤 4：空输入跳过，exit 结束，new 清空会话
        if not user_text:
            continue
        command = user_text.lower()
        if command in {"exit", "quit", "/exit", "/quit"}:
            break
        if command in {"/help", "help"}:
            paint(HELP, HINT)
            continue
        if command == "/status":
            show_status(settings)
            continue
        if command in {"/model", "/setup"}:
            settings = run_setup()
            model = build_model(settings)
            continue
        if command in {"new", "/new"}:
            state = new_state()
            save_state(state)
            paint("已开始新会话。长期记忆仍保留。", HINT)
            continue
        if user_text.startswith("记住"):
            reply = remember_command(user_text)
            state.messages.append({"role": "user", "content": user_text})
            state.messages.append({"role": "assistant", "content": reply})
            save_state(state)
            paint(reply, ANSWER)
            continue

        # 步骤 5：交给多个子 Agent 协作，写作内容流式输出
        state.messages.append({"role": "user", "content": user_text})
        paint("正在规划...", HINT)
        started = False

        def on_token(text: str) -> None:
            nonlocal started
            started = True
            paint(text, ANSWER, end="")

        runners = build_graph_runners(model, on_tool=print_tools, on_token=on_token)
        state = run_graph(
            state,
            *runners,
            save_fn=save_state,
            on_event=show_agent_event,
        )
        if started:
            print()
        else:
            reply = state.messages[-1]["content"] if state.messages else ""
            paint(f"助手: {reply}", ANSWER)


# 步骤 5：启动命令行入口
def main() -> None:
    # 步骤 1：setup 只接通模型，其余情况进入对话
    parser = argparse.ArgumentParser(description="终端里的多 Agent 助手")
    parser.add_argument("command", nargs="?", choices=("setup",), help="选择服务商并保存 API Key")
    args = parser.parse_args()
    # 步骤 2：进入配置或对话
    if args.command == "setup":
        enable_ansi()
        run_setup()
        return
    run_chat()


if __name__ == "__main__":
    main()
