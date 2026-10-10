"""Ask the user which model to use and store the key in the home config."""

from __future__ import annotations

from collections.abc import Callable
from getpass import getpass

from agentdev.runtime.config import Settings, home_dir
from agentdev.runtime.providers import PROVIDERS, Provider, find_provider

# 步骤 1：把接通结果写进用户主目录，不打印密钥
def save_home_settings(api_key: str, model: str, base_url: str | None) -> None:
    path = home_dir() / ".env"
    path.parent.mkdir(parents=True, exist_ok=True)
    values = {
        "OPENAI_API_KEY": api_key.strip(),
        "MODEL": model.strip(),
        "OPENAI_BASE_URL": (base_url or "").strip(),
        "TEMPERATURE": "0",
    }
    existing: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.strip().startswith("#") or "=" not in line:
                continue
            key, raw = line.split("=", 1)
            existing[key.strip()] = raw
    existing.update(values)
    body = "\n".join(f"{key}={value}" for key, value in existing.items()) + "\n"
    path.write_text(body, encoding="utf-8")


def _ask_model(provider: Provider, input_fn: Callable[[str], str]) -> str:
    if not provider.models:
        return input_fn("输入模型名：").strip()
    print("选择模型，也可以直接输入列表之外的模型名：")
    for index, name in enumerate(provider.models, 1):
        print(f"{index}. {name}")
    answer = input_fn("模型序号或名称：").strip()
    if answer.isdigit():
        index = int(answer) - 1
        if 0 <= index < len(provider.models):
            return provider.models[index]
    return answer


# 步骤 2：在终端里完成服务商、模型和密钥的选择
def run_setup(
    input_fn: Callable[[str], str] | None = None,
    secret_fn: Callable[[str], str] | None = None,
) -> Settings:
    ask = input_fn or input
    secret = secret_fn or getpass
    # 步骤 1：列出服务商并让用户选一个
    print("选择模型服务商：")
    for index, item in enumerate(PROVIDERS, 1):
        print(f"{index}. {item.label}")
    provider = None
    while provider is None:
        provider = find_provider(ask("服务商序号或名称："))
        if provider is None:
            print("没有这个服务商，请重新输入。")
    # 步骤 2：确定模型名和接口地址
    model = _ask_model(provider, ask)
    while not model:
        model = ask("模型名不能为空，请重新输入：").strip()
    base_url = provider.base_url
    if provider.key == "custom":
        base_url = ask("兼容接口地址，例如 https://api.example.com/v1：").strip()
        while not base_url.startswith(("http://", "https://")):
            base_url = ask("地址需要以 http:// 或 https:// 开头：").strip()
    # 步骤 3：读取密钥并写入主目录
    api_key = secret("API Key：").strip()
    while not api_key:
        api_key = secret("API Key 不能为空：").strip()
    save_home_settings(api_key, model, base_url)
    print(f"已接通 {provider.label}，模型 {model}。密钥保存在 {home_dir() / '.env'}。")
    return Settings(api_key=api_key, base_url=base_url or None, model=model, temperature=0.0)
