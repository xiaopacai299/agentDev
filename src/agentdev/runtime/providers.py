"""OpenAI-compatible providers the user can pick in the terminal."""

from __future__ import annotations

from dataclasses import dataclass

# 步骤 1：列出可接通的服务商和它们的默认模型
@dataclass(frozen=True)
class Provider:
    key: str
    label: str
    base_url: str | None
    models: tuple[str, ...]


PROVIDERS = (
    Provider("openai", "OpenAI", None, ("gpt-4o-mini", "gpt-4o")),
    Provider("deepseek", "DeepSeek", "https://api.deepseek.com", ("deepseek-chat", "deepseek-reasoner")),
    Provider("kimi", "Kimi（月之暗面）", "https://api.moonshot.cn/v1", ("moonshot-v1-8k", "moonshot-v1-32k")),
    Provider(
        "qwen",
        "通义千问",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ("qwen-plus", "qwen-turbo"),
    ),
    Provider("zhipu", "智谱 GLM", "https://open.bigmodel.cn/api/paas/v4/", ("glm-4-flash", "glm-4")),
    Provider("openrouter", "OpenRouter", "https://openrouter.ai/api/v1", ()),
    Provider("custom", "自定义兼容接口", "", ()),
)


# 步骤 2：按序号或名称找到服务商
def find_provider(answer: str) -> Provider | None:
    text = answer.strip().lower()
    if text.isdigit():
        index = int(text) - 1
        if 0 <= index < len(PROVIDERS):
            return PROVIDERS[index]
        return None
    for item in PROVIDERS:
        if text == item.key or text == item.label.lower():
            return item
    return None
