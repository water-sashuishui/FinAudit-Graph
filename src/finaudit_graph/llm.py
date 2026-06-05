from __future__ import annotations

import json
import urllib.request
from typing import Any

from .settings import ProjectSettings

# 本模块只封装最小可用的 DeepSeek 调用逻辑。
# 它不依赖更重的 SDK，目的是让 CLI、工作流和 fallback 调用都保持轻量。

def normalize_chat_completions_url(base_url: str) -> str:
    """Return the OpenAI-compatible chat completions endpoint for DeepSeek."""
    clean_url = base_url.rstrip("/")
    if clean_url.endswith("/chat/completions"):
        return clean_url
    if clean_url.endswith("/v1"):
        return f"{clean_url}/chat/completions"
    return f"{clean_url}/v1/chat/completions"


class DeepSeekClient:
    """Minimal OpenAI-compatible DeepSeek chat client.

    The API key is sent only in the Authorization header and is never logged.
    """

    def __init__(self, settings: ProjectSettings | None = None, timeout_seconds: int = 15) -> None:
        """保存运行配置和请求超时时间。"""
        self.settings = settings or ProjectSettings.from_env()
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        """判断是否具备发起 DeepSeek 调用所需的最小配置。"""
        return bool(self.settings.deepseek_api_key and self.settings.audit_llm_model)

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
        """发送 OpenAI-compatible chat 请求，并返回第一条模型回复文本。"""
        if not self.configured:
            raise RuntimeError("DeepSeek settings are not configured.")

        payload = {
            "model": self.settings.audit_llm_model,
            "messages": messages,
            "temperature": temperature,
        }
        request = urllib.request.Request(
            normalize_chat_completions_url(self.settings.deepseek_base_url),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.deepseek_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")

        data: dict[str, Any] = json.loads(body)
        return data["choices"][0]["message"]["content"]
