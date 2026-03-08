"""
Unit tests for HealEngine (Sync and Async).
"""
from __future__ import annotations
import pytest

from max_heal.heal_engine import AsyncHealEngine, SyncHealEngine

# ---------------------------------------------------------------------------
# Mocks
# ---------------------------------------------------------------------------

class _FakeAsyncLLM:
    def __init__(self, responses):
        self._responses = responses
        self.call_count = 0

    async def ask(self, prompt: str) -> str:
        resp = self._responses[self.call_count]
        self.call_count += 1
        if isinstance(resp, Exception):
            raise resp
        return resp

class _FakeSyncLLM:
    def __init__(self, responses):
        self._responses = responses
        self.call_count = 0

    def ask(self, prompt: str) -> str:
        resp = self._responses[self.call_count]
        self.call_count += 1
        if isinstance(resp, Exception):
            raise resp
        return resp


class _FakeAsyncDom:
    async def snapshot(self, page, selector: str) -> str:
        return '<div id="real-btn">Submit</div>'

class _FakeSyncDom:
    def snapshot(self, page, selector: str) -> str:
        return '<div id="real-btn">Submit</div>'


class _FakePage:
    """Minimal Playwright page stub."""
    pass


# ---------------------------------------------------------------------------
# Async Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_async_heal_returns_new_selector():
    llm = _FakeAsyncLLM(["#real-btn"])
    dom = _FakeAsyncDom()
    engine = AsyncHealEngine(llm, dom)
    
    result = await engine.heal(_FakePage(), "#broken-btn", "Timeout")
    assert result == "#real-btn"
    assert llm.call_count == 1


@pytest.mark.asyncio
async def test_async_heal_uses_cache_on_second_call():
    llm = _FakeAsyncLLM(["#real-btn"])
    dom = _FakeAsyncDom()
    engine = AsyncHealEngine(llm, dom)
    
    first = await engine.heal(_FakePage(), "#broken-btn", "Timeout")
    second = await engine.heal(_FakePage(), "#broken-btn", "Timeout")
    
    assert first == "#real-btn"
    assert second == "#real-btn"
    assert llm.call_count == 1  # Cache hit


@pytest.mark.asyncio
async def test_async_heal_returns_none_on_llm_error():
    llm = _FakeAsyncLLM([RuntimeError("Server Error")])
    dom = _FakeAsyncDom()
    engine = AsyncHealEngine(llm, dom)
    
    result = await engine.heal(_FakePage(), "#broken-btn", "Timeout")
    assert result is None
    assert llm.call_count == 1


@pytest.mark.asyncio
async def test_async_heal_strips_markdown_fences():
    llm = _FakeAsyncLLM(["```\n#real-btn\n```"])
    dom = _FakeAsyncDom()
    engine = AsyncHealEngine(llm, dom)
    
    result = await engine.heal(_FakePage(), "#broken-btn", "Timeout")
    assert result == "#real-btn"


# ---------------------------------------------------------------------------
# Sync Tests
# ---------------------------------------------------------------------------

def test_sync_heal_returns_new_selector():
    llm = _FakeSyncLLM(["#real-btn"])
    dom = _FakeSyncDom()
    engine = SyncHealEngine(llm, dom)
    
    result = engine.heal(_FakePage(), "#broken-btn", "Timeout")
    assert result == "#real-btn"
    assert llm.call_count == 1

def test_sync_heal_uses_cache_on_second_call():
    llm = _FakeSyncLLM(["#real-btn"])
    dom = _FakeSyncDom()
    engine = SyncHealEngine(llm, dom)
    
    first = engine.heal(_FakePage(), "#broken-btn", "Timeout")
    second = engine.heal(_FakePage(), "#broken-btn", "Timeout")
    
    assert first == "#real-btn"
    assert second == "#real-btn"
    assert llm.call_count == 1

def test_sync_heal_returns_none_on_llm_error():
    llm = _FakeSyncLLM([RuntimeError("Server Error")])
    dom = _FakeSyncDom()
    engine = SyncHealEngine(llm, dom)
    
    result = engine.heal(_FakePage(), "#broken-btn", "Timeout")
    assert result is None

def test_sync_heal_strips_markdown_fences():
    llm = _FakeSyncLLM(["```\n#real-btn\n```"])
    dom = _FakeSyncDom()
    engine = SyncHealEngine(llm, dom)
    
    result = engine.heal(_FakePage(), "#broken-btn", "Timeout")
    assert result == "#real-btn"
