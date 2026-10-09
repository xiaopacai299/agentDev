"""Interactive command-line chat."""

from __future__ import annotations

import argparse

from agentdev.agent import build_agent, message_text
from agentdev.config import load_settings


def run_chat() -> None:
    settings = load_settings()
    agent = build_agent(settings)
    messages: list = []

    print(f"模型：{settings.model}")
    print("输入问题开始对话，输入 exit 退出。")

    while True:
        try:
            user_text = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_text:
            continue
        if user_text.lower() in {"exit", "quit"}:
            break

        messages.append({"role": "user", "content": user_text})
        result = agent.invoke({"messages": messages})
        messages = result["messages"]
        print(f"助手: {message_text(messages[-1])}")


def main() -> None:
    parser = argparse.ArgumentParser(description="LangChain agent MVP")
    parser.parse_args()
    run_chat()


if __name__ == "__main__":
    main()
