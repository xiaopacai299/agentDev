"""Chat model setup and plain-text extraction. No business prompt lives here."""

from __future__ import annotations

from langchain.chat_models import init_chat_model

from agentdev.runtime.config import Settings

# 步骤 1：把模型回复提取成纯文本
def message_text(message) -> str:
    # 步骤 1：取出消息正文
    content = getattr(message, "content", message)
    # 步骤 2：纯文本直接返回
    if isinstance(content, str):
        return content
    # 步骤 3：从内容块里收集文本
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    return "".join(parts)


# 步骤 2：按配置创建聊天模型
def build_model(settings: Settings):
    # 步骤 1：组装模型参数
    model_kwargs = {
        "model": settings.model,
        "model_provider": "openai",
        "api_key": settings.api_key,
        "temperature": settings.temperature,
    }
    # 步骤 2：使用兼容接口时传入地址
    if settings.base_url:
        model_kwargs["base_url"] = settings.base_url
    return init_chat_model(**model_kwargs)
