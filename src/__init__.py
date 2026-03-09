"""
MaxHeal — Playwright wrapper with LLM-powered auto-heal and flaky auto-fix.
"""

# ── Primary public API ─────────────────────────────────────────────────────────
from .config import MaxHealConfig
from .factory import create_maxheal_page
from .flaky_guard import flaky, flaky_sync
from .heal_engine import global_context, max_step
from .maxheal_page import AsyncMaxHealPage, MaxHealPage

# ── Global expect Monkeypatch ──────────────────────────────────────────────────
import playwright.sync_api
import playwright.async_api

def _apply_global_expect_patch():
    if getattr(playwright.sync_api, "_maxheal_patched", False):
        return
    playwright.sync_api._maxheal_patched = True
    
    _orig_expect = playwright.sync_api.expect
    
    class MaxHealAssertionsWrapper:
        def __init__(self, actual_locator, message):
            self._actual_locator = actual_locator
            self._message = message
            
        def __getattr__(self, name):
            # We want to intercept .to_be_visible(), etc.
            if not name.startswith("to_"):
                return getattr(_orig_expect(self._actual_locator, self._message), name)
                
            def wrapper(*args, **kwargs):
                current_loc = self._actual_locator
                maxheal_page = getattr(current_loc, "_maxheal_page", None)
                
                # If this locator doesn't belong to a MaxHealPage or healing is off, just run normally.
                if not maxheal_page or not getattr(maxheal_page, "_heal_enabled", False):
                    # just apply flaky_sync for normal retries
                    @flaky_sync(max_retries=3, delay=1.5, exceptions=(AssertionError, Exception))
                    def run_standard_assert():
                        return getattr(_orig_expect(current_loc, self._message), name)(*args, **kwargs)
                    return run_standard_assert()
                    
                # Dynamic Healing Loop
                @flaky_sync(max_retries=maxheal_page._max_retries, delay=1.5, exceptions=(AssertionError, Exception))
                def run_healing_assert():
                    nonlocal current_loc
                    try:
                        return getattr(_orig_expect(current_loc, self._message), name)(*args, **kwargs)
                    except Exception as exc:
                        # Extract the failure and heal
                        analyzer = maxheal_page._analyzer
                        page = maxheal_page._page
                        
                        # Use our saved pseudo-selector, or fallback to Playwright's native string repr
                        pseudo_selector = getattr(current_loc, "_maxheal_selector", None)
                        if not pseudo_selector:
                            pseudo_selector = getattr(getattr(current_loc, "_impl_obj", None), "_selector", str(current_loc))
                            
                        result = analyzer.handle(page, pseudo_selector, str(exc))
                        
                        if result.healed_selector:
                            if result.healed_selector.startswith("locator(") or result.healed_selector.startswith("get_by_"):
                                current_loc = eval(f"page.{result.healed_selector}")
                            else:
                                current_loc = page.locator(result.healed_selector)
                            
                            # Propagate maxheal context to the new locator
                            current_loc._maxheal_page = maxheal_page
                            current_loc._maxheal_selector = result.healed_selector
                            
                        if result.wait_ms > 0:
                            import time
                            time.sleep(result.wait_ms / 1000.0)
                            
                        # Re-raise to trigger the flaky_sync retry with the newly healed `current_loc`
                        raise
                        
                return run_healing_assert()
            return wrapper
            
    def auto_heal_expect(actual, message=None):
        return MaxHealAssertionsWrapper(actual, message)
        
    playwright.sync_api.expect = auto_heal_expect

def _apply_global_async_expect_patch():
    if getattr(playwright.async_api, "_maxheal_patched", False):
        return
    playwright.async_api._maxheal_patched = True
    
    _orig_async_expect = playwright.async_api.expect
    
    class AsyncMaxHealAssertionsWrapper:
        def __init__(self, actual_locator, message):
            self._actual_locator = actual_locator
            self._message = message
            
        def __getattr__(self, name):
            if not name.startswith("to_"):
                return getattr(_orig_async_expect(self._actual_locator, self._message), name)
                
            async def wrapper(*args, **kwargs):
                current_loc = self._actual_locator
                maxheal_page = getattr(current_loc, "_maxheal_page", None)
                
                if not maxheal_page or not getattr(maxheal_page, "_heal_enabled", False):
                    @flaky(max_retries=3, delay=1.5, exceptions=(AssertionError, Exception))
                    async def run_standard_assert():
                        return await getattr(_orig_async_expect(current_loc, self._message), name)(*args, **kwargs)
                    return await run_standard_assert()
                    
                @flaky(max_retries=maxheal_page._max_retries, delay=1.5, exceptions=(AssertionError, Exception))
                async def run_healing_assert():
                    nonlocal current_loc
                    try:
                        return await getattr(_orig_async_expect(current_loc, self._message), name)(*args, **kwargs)
                    except Exception as exc:
                        analyzer = maxheal_page._analyzer
                        page = maxheal_page._page
                        
                        pseudo_selector = getattr(current_loc, "_maxheal_selector", None)
                        if not pseudo_selector:
                            pseudo_selector = getattr(getattr(current_loc, "_impl_obj", None), "_selector", str(current_loc))
                            
                        result = await analyzer.handle(page, pseudo_selector, str(exc))
                        
                        if result.healed_selector:
                            if result.healed_selector.startswith("locator(") or result.healed_selector.startswith("get_by_"):
                                current_loc = eval(f"page.{result.healed_selector}")
                            else:
                                current_loc = page.locator(result.healed_selector)
                                
                            current_loc._maxheal_page = maxheal_page
                            current_loc._maxheal_selector = result.healed_selector
                            
                        if result.wait_ms > 0:
                            import asyncio
                            await asyncio.sleep(result.wait_ms / 1000.0)
                            
                        raise
                        
                return await run_healing_assert()
            return wrapper
            
    def auto_heal_async_expect(actual, message=None):
        return AsyncMaxHealAssertionsWrapper(actual, message)
        
    playwright.async_api.expect = auto_heal_async_expect

_apply_global_expect_patch()
_apply_global_async_expect_patch()


# ── FlakeAnalyzer public surface ───────────────────────────────────────────────
from .flake_analyzer import FlakeAnalyzer, FlakeCategory, StrategyResult

# ── Built-in strategies (injectable) ──────────────────────────────────────────
from .strategies import (
    AnimationStrategy,
    LLMHealStrategy,
    NotInteractableStrategy,
    OverlayStrategy,
    StrictViolationStrategy,
)

# ── Advanced / injectable components ──────────────────────────────────────────
from .dom_snapshot import PlaywrightDomSnapshot
from .heal_engine import SyncHealEngine
from .llm_client import SyncOpenRouterClient
from .protocols import IHealEngine, ILLMClient, IDomSnapshot



__all__ = [
    # Primary
    "MaxHealConfig", "MaxHealPage", "AsyncMaxHealPage",
    "create_maxheal_page", "create_async_maxheal_page",
    "flaky_sync", "flaky", "global_context", "max_step",
    # FlakeAnalyzer
    "FlakeAnalyzer", "FlakeCategory", "StrategyResult",
    # Strategies
    "LLMHealStrategy", "NotInteractableStrategy", "OverlayStrategy",
    "StrictViolationStrategy", "AnimationStrategy",
    # Protocols
    "ILLMClient", "IHealEngine", "IDomSnapshot",
    "IAsyncLLMClient", "IAsyncHealEngine", "IAsyncDomSnapshot",
    # Concrete components
    "SyncOpenRouterClient", "SyncHealEngine", "PlaywrightDomSnapshot",
    "AsyncOpenRouterClient", "AsyncHealEngine", "AsyncPlaywrightDomSnapshot",
]
__version__ = "0.2.0"
