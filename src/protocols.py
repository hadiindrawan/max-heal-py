"""
protocols.py — Abstract interfaces (Protocols) for MaxHeal components.

Following Interface Segregation & Dependency Inversion principles:
- MaxHealPage depends on IHealEngine, not a concrete class.
- IHealEngine depends on ILLMClient, not OpenRouter directly.
- Swap any component by implementing its Protocol.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from playwright.sync_api import Page as SyncPage
    from playwright.async_api import Page as AsyncPage


@runtime_checkable
class ILLMClient(Protocol):
    """Sync LLM client — ask a question, get a text answer."""

    def ask(self, prompt: str) -> str:
        ...


@runtime_checkable
class IAsyncLLMClient(Protocol):
    """Async LLM client — ask a question, get a text answer."""

    async def ask(self, prompt: str) -> str:
        ...


@runtime_checkable
class IDomSnapshot(Protocol):
    """Sync DOM snapshot — capture a compact page snapshot."""

    def snapshot(self, page: "SyncPage", selector: str | None = None) -> str:
        ...


@runtime_checkable
class IAsyncDomSnapshot(Protocol):
    """Async DOM snapshot — capture a compact page snapshot."""

    async def snapshot(self, page: "AsyncPage", selector: str | None = None) -> str:
        ...


@runtime_checkable
class IHealEngine(Protocol):
    """Sync heal engine — attempt to recover a broken selector."""

    def heal(self, page: "SyncPage", selector: str, error: str) -> str | None:
        ...


@runtime_checkable
class IAsyncHealEngine(Protocol):
    """Async heal engine — attempt to recover a broken selector."""

    async def heal(
        self, page: "AsyncPage", selector: str, error: str
    ) -> str | None:
        ...
