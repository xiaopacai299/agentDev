"""Interactive command-line chat."""

from __future__ import annotations

import argparse

from agentdev.agent import build_agent, message_text
from agentdev.config import load_settings


# 步骤 1：进行多轮对话
def run_chat() -> None:
    # 步骤 1：读取配置并创建 Agent
    settings = load_settings()
    agent = build_agent(settings)
    messages: list = []

    # 步骤 2：提示当前模型和退出方式
    print(f"模型：{settings.model}")
    print("输入问题开始对话，输入 exit 退出。")

    while True:
        # 步骤 3：读取用户输入，中断时结束
        try:
            user_text = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        # 步骤 4：空输入跳过，exit 结束对话
        if not user_text:
            continue
        if user_text.lower() in {"exit", "quit"}:
            break

        # 步骤 5：把本轮对话交给 Agent 并打印回复
        messages.append({"role": "user", "content": user_text})
        result = agent.invoke({"messages": messages})
        messages = result["messages"]
        print(f"助手: {message_text(messages[-1])}")


# 步骤 2：启动命令行入口
def main() -> None:
    # 步骤 1：解析命令行参数
    parser = argparse.ArgumentParser(description="LangChain agent MVP")
    parser.parse_args()
    # 步骤 2：进入对话
    run_chat()


if __name__ == "__main__":
    main()
