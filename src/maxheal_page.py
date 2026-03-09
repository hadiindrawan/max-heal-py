"""
maxheal_page.py — MaxHealPage: the main public wrapper (sync & async).

Design (SOLID):
- S: wraps Page I/O only; all fix logic delegated to FlakeAnalyzer.
- L: __getattr__ makes MaxHealPage a drop-in for any Playwright Page.
- D: receives FlakeAnalyzer (injected), not any concrete strategy.
- O: new flake types handled by adding a strategy — MaxHealPage never changes.

expect(locator).to_be_visible() / .to_contain_text() continue to work
because locator() always returns a native Playwright Locator.
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from playwright.sync_api import Error as SyncError
from playwright.sync_api import Page as SyncPage
from playwright.sync_api import TimeoutError as SyncTimeout

if TYPE_CHECKING:
    from playwright.sync_api import Locator

from .flaky_guard import flaky, flaky_sync

logger = logging.getLogger(__name__)
_SYNC_ERRORS = (SyncTimeout, SyncError)


class MaxHealPage:
    """Sync Playwright Page wrapper that routes failures to FlakeAnalyzer.

    Inject a fully-wired FlakeAnalyzer via the constructor, or use
    create_maxheal_page() from factory.py for zero-boilerplate setup.

    All original Playwright methods pass through transparently, so:

        expect(self.page.locator("#btn")).to_be_visible()     # works
        expect(self.page.locator(".msg")).to_contain_text("") # works
    """

    def __init__(
        self,
        page: SyncPage,
        analyzer,
        max_retries: int = 3,
        heal_enabled: bool = True,
    ) -> None:
        self._page = page
        self._analyzer = analyzer
        self._max_retries = max_retries
        self._heal_enabled = heal_enabled

    # ------------------------------------------------------------------
    # Heal-aware action methods
    # ------------------------------------------------------------------

    def click(self, selector: str, intent: str | None = None, **kwargs: Any) -> None:
        """Click; routes failures through FlakeAnalyzer."""
        self._act("click", selector, intent, **kwargs)

    def fill(self, selector: str, value: str, intent: str | None = None, **kwargs: Any) -> None:
        """Fill; routes failures through FlakeAnalyzer."""
        self._act("fill", selector, intent, value, **kwargs)

    def wait_for_selector(self, selector: str, intent: str | None = None, **kwargs: Any) -> Any:
        """Wait for selector; routes failures through FlakeAnalyzer."""
        return self._act("wait_for_selector", selector, intent, **kwargs)

    def locator(self, selector: str, *args: Any, **kwargs: Any) -> "Locator":
        """Return a native Playwright Locator. Healing happens lazily during expect() or click()."""
        loc = self._page.locator(selector, *args, **kwargs)
        if self._heal_enabled:
            try:
                args_repr = ", ".join([repr(a) for a in args] + [f"{k}={v!r}" for k, v in kwargs.items()])
                loc._maxheal_selector = f"locator({selector!r}, {args_repr})" if args_repr else selector
                loc._maxheal_page = self
            except Exception:
                pass
        return loc

    # ------------------------------------------------------------------
    # Transparent proxy — full Playwright Page API passes through
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> Any:
        """Proxy all other attributes/methods to the underlying Page.

        Dynamically intercepts get_by_* methods to provide healing support
        for native Playwright locators.
        """
        attr = getattr(self._page, name)
        
        if name.startswith("get_by_") and callable(attr):
            def wrapper(*args: Any, **kwargs: Any) -> "Locator":
                loc = attr(*args, **kwargs)
                if self._heal_enabled:
                    try:
                        args_repr = ", ".join([repr(a) for a in args] + [f"{k}={v!r}" for k, v in kwargs.items()])
                        loc._maxheal_selector = f"{name}({args_repr})"
                        loc._maxheal_page = self
                    except Exception:
                        pass
                return loc
            return wrapper
            
        if (name == "goto" or name.startswith("wait_for_")) and name != "wait_for_selector" and callable(attr):
            def network_retry_wrapper(*args: Any, **kwargs: Any) -> Any:
                if not self._heal_enabled:
                    return attr(*args, **kwargs)
                    
                @flaky_sync(max_retries=self._max_retries, delay=1.5, exceptions=_SYNC_ERRORS)
                def _run_network_call():
                    logger.info(f"[MaxHeal] Intercepting network call: page.{name}() with retries")
                    return attr(*args, **kwargs)
                    
                return _run_network_call()
            return network_retry_wrapper
            
        return attr

    # ------------------------------------------------------------------
    # Internal heal loop
    # ------------------------------------------------------------------

    def _act(self, method: str, selector: str, intent: str | None, *args: Any, **kwargs: Any) -> Any:
        from .heal_engine import global_context
        current = selector
        last_exc: Exception | None = None
        
        # Temporarily apply explicit intent if provided
        prev_intent = global_context.get("Explicit Action Intent")
        if intent:
            global_context["Explicit Action Intent"] = intent

        try:
            for attempt in range(1, self._max_retries + 1):
                try:
                    kwargs_clean = {k: v for k, v in kwargs.items() if k != "intent"}
                    return getattr(self._page, method)(current, *args, **kwargs_clean)
    
                except _SYNC_ERRORS as exc:
                    last_exc = exc
                    if not self._heal_enabled:
                        raise
    
                    logger.warning(
                        "[MaxHeal] Attempt %d/%d — %s(%r) failed: %s",
                        attempt, self._max_retries, method, current, exc,
                    )
    
                    result = self._analyzer.handle(self._page, current, str(exc))
    
                    if result.wait_ms > 0:
                        time.sleep(result.wait_ms / 1000)
    
                    if result.healed_selector:
                        current = result.healed_selector
                    elif not result.should_retry:
                        raise  # no strategy could help
    
            raise last_exc  # type: ignore[misc]
        finally:
            if intent:
                if prev_intent is not None:
                    global_context["Explicit Action Intent"] = prev_intent
                else:
                    global_context.pop("Explicit Action Intent", None)


class AsyncMaxHealPage:
    """Async Playwright Page wrapper that routes failures to the async FlakeAnalyzer."""

    def __init__(
        self,
        page: Any,
        analyzer: Any,
        max_retries: int = 3,
        heal_enabled: bool = True,
    ) -> None:
        self._page = page
        self._analyzer = analyzer
        self._max_retries = max_retries
        self._heal_enabled = heal_enabled

    async def click(self, selector: str, intent: str | None = None, **kwargs: Any) -> None:
        await self._act("click", selector, intent, **kwargs)

    async def fill(self, selector: str, value: str, intent: str | None = None, **kwargs: Any) -> None:
        await self._act("fill", selector, intent, value, **kwargs)

    async def wait_for_selector(self, selector: str, intent: str | None = None, **kwargs: Any) -> Any:
        return await self._act("wait_for_selector", selector, intent, **kwargs)

    async def locator(self, selector: str, *args: Any, **kwargs: Any) -> Any:
        """Return a native Playwright Locator."""
        loc = self._page.locator(selector, *args, **kwargs)
        if self._heal_enabled:
            try:
                args_repr = ", ".join([repr(a) for a in args] + [f"{k}={v!r}" for k, v in kwargs.items()])
                loc._maxheal_selector = f"locator({selector!r}, {args_repr})" if args_repr else selector
                loc._maxheal_page = self
            except Exception:
                pass
        return loc

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._page, name)
        
        if name.startswith("get_by_") and callable(attr):
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                loc = attr(*args, **kwargs)
                if self._heal_enabled:
                    try:
                        args_repr = ", ".join([repr(a) for a in args] + [f"{k}={v!r}" for k, v in kwargs.items()])
                        loc._maxheal_selector = f"{name}({args_repr})"
                        loc._maxheal_page = self
                    except Exception:
                        pass
                return loc
            return wrapper
            
        if (name == "goto" or name.startswith("wait_for_")) and name != "wait_for_selector" and callable(attr):
            def async_network_retry_wrapper(*args: Any, **kwargs: Any) -> Any:
                if not self._heal_enabled:
                    return attr(*args, **kwargs)
                    
                from playwright.async_api import Error as AE, TimeoutError as AT
                
                @flaky(max_retries=self._max_retries, delay=1.5, exceptions=(AT, AE))
                async def _run_async_network_call():
                    logger.info(f"[MaxHeal] Intercepting async network call: page.{name}() with retries")
                    return await attr(*args, **kwargs)
                    
                return _run_async_network_call()
            return async_network_retry_wrapper
            
        return attr

    async def _act(self, method: str, selector: str, intent: str | None, *args: Any, **kwargs: Any) -> Any:
        import asyncio
        from playwright.async_api import Error as AE, TimeoutError as AT
        from .heal_engine import global_context
        
        current = selector
        last_exc: Exception | None = None
        
        prev_intent = global_context.get("Explicit Action Intent")
        if intent:
            global_context["Explicit Action Intent"] = intent
            
        try:
            for attempt in range(1, self._max_retries + 1):
                try:
                    kwargs_clean = {k: v for k, v in kwargs.items() if k != "intent"}
                    return await getattr(self._page, method)(current, *args, **kwargs_clean)
                except (AT, AE) as exc:
                    last_exc = exc
                    if not self._heal_enabled:
                        raise
                    logger.warning(
                        "[MaxHeal] Attempt %d/%d — %s(%r) failed: %s",
                        attempt, self._max_retries, method, current, exc,
                    )
                    result = await self._analyzer.handle(self._page, current, str(exc))
                    if result.wait_ms > 0:
                        await asyncio.sleep(result.wait_ms / 1000)
                    if result.healed_selector:
                        current = result.healed_selector
                    elif not result.should_retry:
                        raise
            raise last_exc  # type: ignore[misc]
        finally:
            if intent:
                if prev_intent is not None:
                    global_context["Explicit Action Intent"] = prev_intent
                else:
                    global_context.pop("Explicit Action Intent", None)
