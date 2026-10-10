"""Load runtime settings from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# 步骤 1：工作目录跟用户当前终端走，密钥放在用户主目录
def workspace_root() -> Path:
    return Path.cwd()


def home_dir() -> Path:
    return Path.home() / ".agent"


# 步骤 2：声明运行时需要的配置项
@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str | None
    model: str
    temperature: float


# 步骤 3：从环境变量装载配置
def load_settings() -> Settings:
    # 步骤 1：先读主目录密钥，当前目录的 .env 可以覆盖模型名
    load_dotenv(home_dir() / ".env", override=True)
    load_dotenv(workspace_root() / ".env", override=True)

    # 步骤 2：读取密钥、接口地址、模型名和温度
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
    model = os.getenv("MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    temperature = float(os.getenv("TEMPERATURE", "0"))

    # 步骤 3：缺少密钥时中止启动
    if not api_key:
        raise RuntimeError(
            "还没有接通模型。请运行 wkagent setup，选择服务商并输入 API Key。"
        )

    # 步骤 4：返回不可变配置
    return Settings(
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=temperature,
    )
