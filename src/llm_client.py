"""
llm_client.py — OpenRouter LLM client implementations (sync & async).

Both implement their respective Protocol (ILLMClient / IAsyncLLMClient),
so they can be swapped for any other LLM provider without touching HealEngine.
"""
from __future__ import annotations

import httpx
import logging

from .config import MaxHealConfig
logger = logging.getLogger(__name__)

_HEADERS_BASE = {
    "HTTP-Referer": "https://github.com/maxheal",
    "X-Title": "MaxHeal",
}
_PAYLOAD_BASE = {
    "temperature": 0,
    "max_tokens": 256,
}


def _build_headers(api_key: str) -> dict:
    return {**_HEADERS_BASE, "Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _parse_response(data: dict) -> str:
    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError(f"LLM returned no choices: {data}")
    return choices[0]["message"]["content"].strip()


class SyncOpenRouterClient:
    """Synchronous OpenRouter client — implements ``ILLMClient``."""

    def __init__(self, config: MaxHealConfig) -> None:
        self._config = config
        self._headers = _build_headers(config.api_key)

    def ask(self, prompt: str) -> str:
        # logger.info(f"[MaxHeal] Asking LLM: {prompt}")

        payload = {**_PAYLOAD_BASE, "model": self._config.model,
                   "messages": [{"role": "user", "content": prompt}]}
        with httpx.Client(timeout=self._config.timeout) as client:
            r = client.post(f"{self._config.base_url}/chat/completions",
                            json=payload, headers=self._headers)
            r.raise_for_status()
            return _parse_response(r.json())


class AsyncOpenRouterClient:
    """Asynchronous OpenRouter client — implements ``IAsyncLLMClient``."""

    def __init__(self, config: MaxHealConfig) -> None:
        self._config = config
        self._headers = _build_headers(config.api_key)

    async def ask(self, prompt: str) -> str:
        # logger.info(f"[MaxHeal] Asking LLM: {prompt}")

        payload = {**_PAYLOAD_BASE, "model": self._config.model,
                   "messages": [{"role": "user", "content": prompt}]}
        async with httpx.AsyncClient(timeout=self._config.timeout) as client:
            r = await client.post(f"{self._config.base_url}/chat/completions",
                                  json=payload, headers=self._headers)
            r.raise_for_status()
            return _parse_response(r.json())
