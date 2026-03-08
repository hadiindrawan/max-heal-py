"""
strategies.py — Concrete IFlakeStrategy implementations.

Each strategy:
- can_handle(category) → says which FlakeCategory it covers
- handle(page, selector, error, category) → returns StrategyResult

Adding a new strategy requires only implementing these two methods and
injecting the strategy into FlakeAnalyzer — MaxHealPage never changes.
"""
from __future__ import annotations

import logging
import re
import time
from typing import TYPE_CHECKING

from .flake_analyzer import FlakeCategory, StrategyResult

if TYPE_CHECKING:
    from playwright.sync_api import Page
    from playwright.async_api import Page as AsyncPage

logger = logging.getLogger(__name__)


# ── Strategy 1: LLM Selector Healing ─────────────────────────────────────────

class LLMHealStrategy:
    """Handles SELECTOR_MISSING: asks the LLM for a better selector.

    Delegates to the injected IHealEngine (Dependency Inversion).
    """

    def __init__(self, heal_engine) -> None:  # IHealEngine
        self._engine = heal_engine

    def can_handle(self, category: FlakeCategory) -> bool:
        # LLM Strategy is the ultimate fallback, it accepts anything
        # (It is ordered last in factory.py)
        return True

    def handle(
        self, page: "Page", selector: str, error: str, category: FlakeCategory
    ) -> StrategyResult:
        logger.info("[MaxHeal] Strategy: LLMHeal for %r", selector)
        healed = self._engine.heal(page, selector, error)
        return StrategyResult(healed_selector=healed, should_retry=healed is not None)


class AsyncLLMHealStrategy:
    """Async Handles SELECTOR_MISSING."""

    def __init__(self, heal_engine) -> None:  # IAsyncHealEngine
        self._engine = heal_engine

    def can_handle(self, category: FlakeCategory) -> bool:
        # Async LLM Strategy is the ultimate fallback, it accepts anything
        return True

    async def handle(
        self, page: "AsyncPage", selector: str, error: str, category: FlakeCategory
    ) -> StrategyResult:
        logger.info("[MaxHeal] Strategy: Async LLMHeal for %r", selector)
        healed = await self._engine.heal(page, selector, error)
        return StrategyResult(healed_selector=healed, should_retry=healed is not None)


# ── Strategy 2: Not Interactable ──────────────────────────────────────────────

_INTERACTABLE_JS = """
(function(sel) {
  try {
    var el = document.querySelector(sel);
    if (!el) return {found: false};
    var rect = el.getBoundingClientRect();
    return {
      found: true,
      visible: rect.width > 0 && rect.height > 0,
      enabled: !el.disabled,
      inViewport: rect.top >= 0 && rect.top < window.innerHeight
    };
  } catch(e) { return {found: false, error: e.toString()}; }
})(%s)
"""


class NotInteractableStrategy:
    """Handles NOT_INTERACTABLE: scrolls element into view and waits for enabled.

    Does NOT call the LLM — purely DOM manipulation.
    """

    def __init__(self, wait_ms: int = 2000) -> None:
        self._wait_ms = wait_ms

    def can_handle(self, category: FlakeCategory) -> bool:
        return category == FlakeCategory.NOT_INTERACTABLE

    def handle(
        self, page: "Page", selector: str, error: str, category: FlakeCategory
    ) -> StrategyResult:
        logger.info("[MaxHeal] Strategy: NotInteractable — scroll + wait for %r", selector)
        try:
            # Scroll the element into view
            page.evaluate(
                f"document.querySelector({repr(selector)})?.scrollIntoView"
                f"({{behavior: 'instant', block: 'center'}})"
            )
            # Wait for element to become enabled and visible
            loc = page.locator(selector)
            loc.wait_for(state="visible", timeout=self._wait_ms)
            loc.wait_for(state="enabled", timeout=self._wait_ms)
            logger.info("[MaxHeal] Element now interactable: %r", selector)
            return StrategyResult(should_retry=True, wait_ms=200)
        except Exception as exc:
            logger.debug("[MaxHeal] NotInteractableStrategy failed: %s", exc)
            return StrategyResult(should_retry=False)


class AsyncNotInteractableStrategy:
    """Async handles NOT_INTERACTABLE."""

    def __init__(self, wait_ms: int = 2000) -> None:
        self._wait_ms = wait_ms

    def can_handle(self, category: FlakeCategory) -> bool:
        return category == FlakeCategory.NOT_INTERACTABLE

    async def handle(
        self, page: "AsyncPage", selector: str, error: str, category: FlakeCategory
    ) -> StrategyResult:
        logger.info("[MaxHeal] Strategy: Async NotInteractable — scroll + wait for %r", selector)
        try:
            await page.evaluate(
                f"document.querySelector({repr(selector)})?.scrollIntoView"
                f"({{behavior: 'instant', block: 'center'}})"
            )
            loc = page.locator(selector)
            await loc.wait_for(state="visible", timeout=self._wait_ms)
            await loc.wait_for(state="enabled", timeout=self._wait_ms)
            logger.info("[MaxHeal] Element now interactable: %r", selector)
            return StrategyResult(should_retry=True, wait_ms=200)
        except Exception as exc:
            logger.debug("[MaxHeal] AsyncNotInteractableStrategy failed: %s", exc)
            return StrategyResult(should_retry=False)


# ── Strategy 3: Overlay / Blocker ─────────────────────────────────────────────

# Common patterns for dismissible overlays / loading masks
_OVERLAY_SELECTORS = [
    # Loading spinners / masks
    "[class*='loading']", "[class*='spinner']", "[class*='skeleton']",
    "[class*='overlay']", "[class*='mask']", "[class*='backdrop']",
    # Modals / dialogs
    "[role='dialog'] button[aria-label*='close']",
    "[role='dialog'] button[aria-label*='Close']",
    "button[class*='close']", "button[class*='dismiss']",
    # Toast / snackbar
    "[class*='toast'] button", "[class*='snackbar'] button",
    # Cookie banners
    "button[id*='accept']", "button[id*='cookie']",
]
_OVERLAY_WAIT_JS = """
(function() {
  var selectors = %s;
  for (var i = 0; i < selectors.length; i++) {
    var el = document.querySelector(selectors[i]);
    if (el && el.offsetParent !== null) {
      el.click();
      return selectors[i];
    }
  }
  // Check if any loading mask is present (not dismissible, just wait)
  var loading = document.querySelector(
    "[class*='loading']:not([hidden]), [class*='spinner']:not([hidden])"
  );
  return loading ? '__WAIT__' : null;
})()
"""


class OverlayStrategy:
    """Handles COVERED_BY_OVERLAY: detects + dismisses overlays; waits for loaders."""

    def __init__(self, max_wait_ms: int = 5000) -> None:
        self._max_wait_ms = max_wait_ms

    def can_handle(self, category: FlakeCategory) -> bool:
        return category == FlakeCategory.COVERED_BY_OVERLAY

    def handle(
        self, page: "Page", selector: str, error: str, category: FlakeCategory
    ) -> StrategyResult:
        logger.info("[MaxHeal] Strategy: Overlay — detecting blocker for %r", selector)
        try:
            result = page.evaluate(_OVERLAY_WAIT_JS % repr(_OVERLAY_SELECTORS))
            if result == "__WAIT__":
                # A loading mask is present — wait for it to disappear
                logger.info("[MaxHeal] Loading mask detected — waiting up to %dms", self._max_wait_ms)
                page.wait_for_function(
                    """() => !document.querySelector(
                        "[class*='loading']:not([hidden]),[class*='spinner']:not([hidden])"
                    )""",
                    timeout=self._max_wait_ms,
                )
                return StrategyResult(should_retry=True, wait_ms=300)
            elif result:
                logger.info("[MaxHeal] Dismissed overlay via: %s", result)
                return StrategyResult(should_retry=True, wait_ms=500)
        except Exception as exc:
            logger.warning("[MaxHeal] OverlayStrategy failed: %s", exc)
        return StrategyResult(should_retry=False)


class AsyncOverlayStrategy:
    """Async Handles COVERED_BY_OVERLAY."""

    def __init__(self, max_wait_ms: int = 5000) -> None:
        self._max_wait_ms = max_wait_ms

    def can_handle(self, category: FlakeCategory) -> bool:
        return category == FlakeCategory.COVERED_BY_OVERLAY

    async def handle(
        self, page: "AsyncPage", selector: str, error: str, category: FlakeCategory
    ) -> StrategyResult:
        logger.info("[MaxHeal] Strategy: Async Overlay — detecting blocker for %r", selector)
        try:
            result = await page.evaluate(_OVERLAY_WAIT_JS % repr(_OVERLAY_SELECTORS))
            if result == "__WAIT__":
                logger.info("[MaxHeal] Loading mask detected — waiting up to %dms", self._max_wait_ms)
                await page.wait_for_function(
                    """() => !document.querySelector(
                        "[class*='loading']:not([hidden]),[class*='spinner']:not([hidden])"
                    )""",
                    timeout=self._max_wait_ms,
                )
                return StrategyResult(should_retry=True, wait_ms=300)
            elif result:
                logger.info("[MaxHeal] Dismissed overlay via: %s", result)
                return StrategyResult(should_retry=True, wait_ms=500)
        except Exception as exc:
            logger.warning("[MaxHeal] AsyncOverlayStrategy failed: %s", exc)
        return StrategyResult(should_retry=False)


# ── Strategy 4: Strict Violation (multiple matches) ───────────────────────────

_STRICT_PROMPT = """\
A Playwright selector matched multiple elements (strict mode violation).
Suggest a MORE SPECIFIC selector that matches exactly ONE element.

## Original Selector
{selector}

## Error
{error}

## Page DOM (trimmed)
{dom}

## Rules
- Return ONLY the new selector string.
- Prefer: data-testid, specific IDs, :nth-child, :first-of-type, aria roles with name.
- No explanation, no code fences, no quotes.
"""


class StrictViolationStrategy:
    """Handles STRICT_VIOLATION: asks LLM to make the selector more specific."""

    def __init__(self, heal_engine, dom_snapshot) -> None:
        self._engine = heal_engine
        self._dom = dom_snapshot

    def can_handle(self, category: FlakeCategory) -> bool:
        return category == FlakeCategory.STRICT_VIOLATION

    def handle(
        self, page: "Page", selector: str, error: str, category: FlakeCategory
    ) -> StrategyResult:
        logger.info("[MaxHeal] Strategy: StrictViolation — refining %r", selector)
        # Reuse HealEngine but the prompt context is different
        healed = self._engine.heal(
            page,
            selector,
            f"STRICT VIOLATION: {error}",  # prefix signals to LLM it's a specificity issue
        )
        return StrategyResult(healed_selector=healed, should_retry=healed is not None)


class AsyncStrictViolationStrategy:
    """Async Handles STRICT_VIOLATION."""

    def __init__(self, heal_engine, dom_snapshot) -> None:
        self._engine = heal_engine
        self._dom = dom_snapshot

    def can_handle(self, category: FlakeCategory) -> bool:
        return category == FlakeCategory.STRICT_VIOLATION

    async def handle(
        self, page: "AsyncPage", selector: str, error: str, category: FlakeCategory
    ) -> StrategyResult:
        logger.info("[MaxHeal] Strategy: Async StrictViolation — refining %r", selector)
        healed = await self._engine.heal(
            page,
            selector,
            f"STRICT VIOLATION: {error}",
        )
        return StrategyResult(healed_selector=healed, should_retry=healed is not None)


# ── Strategy 5: Animation / Unstable Element ──────────────────────────────────

_STABLE_JS = """
(function(sel, samples, interval) {
  return new Promise(function(resolve) {
    var rects = [];
    function check() {
      var el = document.querySelector(sel);
      if (!el) { resolve(false); return; }
      var r = el.getBoundingClientRect();
      rects.push(r.top + ',' + r.left + ',' + r.width + ',' + r.height);
      if (rects.length >= samples) {
        var stable = rects.every(function(v) { return v === rects[0]; });
        resolve(stable);
      } else {
        setTimeout(check, interval);
      }
    }
    check();
  });
})(%s, %d, %d)
"""


class AnimationStrategy:
    """Handles ANIMATION_RUNNING: polls until the element stops moving."""

    def __init__(self, samples: int = 3, interval_ms: int = 100, timeout_ms: int = 3000) -> None:
        self._samples = samples
        self._interval_ms = interval_ms
        self._timeout_ms = timeout_ms

    def can_handle(self, category: FlakeCategory) -> bool:
        return category == FlakeCategory.ANIMATION_RUNNING

    def handle(
        self, page: "Page", selector: str, error: str, category: FlakeCategory
    ) -> StrategyResult:
        logger.info("[MaxHeal] Strategy: Animation — waiting for stable: %r", selector)
        deadline = time.time() + self._timeout_ms / 1000
        while time.time() < deadline:
            try:
                stable = page.evaluate(
                    _STABLE_JS % (repr(selector), self._samples, self._interval_ms)
                )
                if stable:
                    logger.info("[MaxHeal] Element stable: %r", selector)
                    return StrategyResult(should_retry=True, wait_ms=100)
            except Exception:
                pass
            time.sleep(self._interval_ms / 1000)
        logger.warning("[MaxHeal] Element still not stable after %dms: %r",
                       self._timeout_ms, selector)
        return StrategyResult(should_retry=False)


class AsyncAnimationStrategy:
    """Async Handles ANIMATION_RUNNING."""

    def __init__(self, samples: int = 3, interval_ms: int = 100, timeout_ms: int = 3000) -> None:
        self._samples = samples
        self._interval_ms = interval_ms
        self._timeout_ms = timeout_ms

    def can_handle(self, category: FlakeCategory) -> bool:
        return category == FlakeCategory.ANIMATION_RUNNING

    async def handle(
        self, page: "AsyncPage", selector: str, error: str, category: FlakeCategory
    ) -> StrategyResult:
        logger.info("[MaxHeal] Strategy: Async Animation — waiting for stable: %r", selector)
        import asyncio
        deadline = time.time() + self._timeout_ms / 1000
        while time.time() < deadline:
            try:
                stable = await page.evaluate(
                    _STABLE_JS % (repr(selector), self._samples, self._interval_ms)
                )
                if stable:
                    logger.info("[MaxHeal] Element stable: %r", selector)
                    return StrategyResult(should_retry=True, wait_ms=100)
            except Exception:
                pass
            await asyncio.sleep(self._interval_ms / 1000)
        logger.warning("[MaxHeal] Element still not stable after %dms: %r",
                       self._timeout_ms, selector)
        return StrategyResult(should_retry=False)
