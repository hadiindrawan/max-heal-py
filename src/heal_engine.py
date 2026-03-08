"""
heal_engine.py — LLM-powered selector healing engines (sync & async).

Each engine implements its Protocol (IHealEngine / IAsyncHealEngine).
ILLMClient and IDomSnapshot are injected — engines don't know about OpenRouter
or Playwright internals directly (Dependency Inversion).
"""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page as SyncPage
    from playwright.async_api import Page as AsyncPage

logger = logging.getLogger(__name__)

# Global dictionary for dynamic LLM context (e.g., current test step, trace info)
# Add keys here and they will be populated dynamically into the LLM prompt.
global_context: dict[str, str] = {}

_PROMPT = """\
You are a Playwright test automation expert.

A selector failed during a test run. Your goal is to suggest ONE alternative selector \\
that either locates the same element OR locates the most logically appropriate element \\
given the current test step and context.

{context_block}
## Failed Selector
{selector}

## Error
{error}

## Page DOM (trimmed)
{dom}

## Rules
{intent_rule}\
- Return ONLY the selector string — no explanation, no code fences, no quotes.
- Prefer: data-testid, aria roles, stable IDs, visible text.
- If no logically better selector exists, return the original unchanged.
"""


def _clean(raw: str) -> str:
    """Strip code fences and surrounding quotes from LLM output."""
    return re.sub(r"```[^\n]*\n?", "", raw).strip().strip("'\"` ")

def _format_context() -> str:
    if not global_context:
        return ""
    lines = ["\n## Current Test Run Context"]
    for k, v in global_context.items():
        if v is not None:
            lines.append(f"- {k}: {v}")
    return "\n".join(lines) + "\n"

def _get_intent_rule() -> str:
    if not global_context:
        return ""
    
    keys_str = " and ".join(f"'{k}'" for k in global_context.keys() if "Step" in k or "Description" in k)
    if keys_str:
        return f"- Determine intent based on the {keys_str}.\n"
    return "- Determine intent based on the test run context provided above.\n"


class SyncHealEngine:
    """Sync heal engine — implements ``IHealEngine``.

    Receives ILLMClient and IDomSnapshot via constructor (DI).
    """

    def __init__(self, llm_client, dom_snapshot) -> None:
        self._llm = llm_client
        self._dom = dom_snapshot
        self._cache: dict[str, str] = {}

    def heal(self, page: "SyncPage", selector: str, error: str) -> str | None:
        if selector in self._cache:
            logger.debug("[MaxHeal] Cache hit: %s", selector)
            return self._cache[selector]
        try:
            dom = self._dom.snapshot(page, selector)
            ctx = _format_context()
            intent_rule = _get_intent_rule()
            raw = self._llm.ask(_PROMPT.format(selector=selector, error=error, dom=dom, context_block=ctx, intent_rule=intent_rule))
            healed = _clean(raw)
            if healed and healed != selector:
                logger.info("[MaxHeal] Healed: %r → %r", selector, healed)
                self._cache[selector] = healed
                return healed
            logger.warning("[MaxHeal] LLM could not improve: %r", selector)
            return None
        except Exception as exc:
            logger.error("[MaxHeal] HealEngine error: %s", exc)
            return None

    def clear_cache(self) -> None:
        self._cache.clear()


class AsyncHealEngine:
    """Async heal engine — implements ``IAsyncHealEngine``.

    Receives IAsyncLLMClient and IAsyncDomSnapshot via constructor (DI).
    """

    def __init__(self, llm_client, dom_snapshot) -> None:
        self._llm = llm_client
        self._dom = dom_snapshot
        self._cache: dict[str, str] = {}

    async def heal(self, page: "AsyncPage", selector: str, error: str) -> str | None:
        if selector in self._cache:
            logger.debug("[MaxHeal] Cache hit: %s", selector)
            return self._cache[selector]
        try:
            dom = await self._dom.snapshot(page, selector)
            ctx = _format_context()
            intent_rule = _get_intent_rule()
            raw = await self._llm.ask(
                _PROMPT.format(selector=selector, error=error, dom=dom, context_block=ctx, intent_rule=intent_rule)
            )
            healed = _clean(raw)
            if healed and healed != selector:
                logger.info("[MaxHeal] Healed: %r → %r", selector, healed)
                self._cache[selector] = healed
                return healed
            logger.warning("[MaxHeal] LLM could not improve: %r", selector)
            return None
        except Exception as exc:
            logger.error("[MaxHeal] HealEngine error: %s", exc)
            return None

    def clear_cache(self) -> None:
        self._cache.clear()
