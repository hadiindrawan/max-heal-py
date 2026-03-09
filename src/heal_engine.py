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
from contextlib import contextmanager
from contextvars import ContextVar

if TYPE_CHECKING:
    from playwright.sync_api import Page as SyncPage
    from playwright.async_api import Page as AsyncPage

logger = logging.getLogger(__name__)

# A ContextVar holds an isolated state for each asyncio task/thread.
_context_state: ContextVar[dict[str, str]] = ContextVar("maxheal_context", default={})
_ALLURE_INTEGRATED = False

class ContextProxy:
    """A proxy dictionary that safely routes operations to a thread/task-local ContextVar."""
    def __setitem__(self, key: str, value: str) -> None:
        state = _context_state.get().copy()
        state[key] = value
        _context_state.set(state)
        
    def __getitem__(self, key: str) -> str:
        return _context_state.get()[key]
        
    def __contains__(self, key: str) -> bool:
        return key in _context_state.get()

    def get(self, key: str, default: str | None = None) -> str | None:
        return _context_state.get().get(key, default)
        
    def items(self):
        return _context_state.get().items()
        
    def keys(self):
        return _context_state.get().keys()
        
    def clear(self) -> None:
        _context_state.set({})
        
    def pop(self, key: str, default: str | None = None) -> str | None:
        state = _context_state.get().copy()
        try:
            val = state.pop(key)
        except KeyError:
            if default is not None:
                return default
            raise
        _context_state.set(state)
        return val

# The proxy object. Looks like a dict, acts like a dict, but is thread/async safe.
global_context = ContextProxy()

@contextmanager
def max_step(description: str):
    """Context manager to declare the intent of the upcoming Playwright actions.
    
    Any failures inside this block will prioritize this description when
    querying the LLM for a healed selector. If Allure is installed, this
    also automatically creates an Allure step in the test report.
    """
    prev_step = global_context.get("Current Auto Step")
    global_context["Current Auto Step"] = description
    
    # Try to natively execute an Allure step block if explicitly integrated
    if _ALLURE_INTEGRATED:
        try:
            import allure
            # When allure is integrated, we call the native block to ensure it generates in the report
            # The monkeypatch wrapper defined inside integrations/allure.py intercepts this natively!
            from datetime import datetime, timezone, timedelta
            now = datetime.now(timezone.utc)
            jakarta_time = now + timedelta(hours=7)
            step_description = f"{jakarta_time.strftime('%Y-%m-%d %H:%M:%S')} - {description}"
            
            context_block = allure.step(step_description)
        except ImportError:
            from contextlib import nullcontext
            context_block = nullcontext()
    else:
        from contextlib import nullcontext
        context_block = nullcontext()
        
    try:
        with context_block:
            yield
    finally:
        if prev_step is not None:
            global_context["Current Auto Step"] = prev_step
        else:
            global_context.pop("Current Auto Step", None)

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
