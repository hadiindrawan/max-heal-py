"""
flake_analyzer.py — FlakeAnalyzer: classifies Playwright errors and routes
to the right strategy.

Architecture (SOLID):
- S: FlakeAnalyzer only classifies and delegates — strategies do the fixing.
- O: Add a new strategy by implementing IFlakeStrategy + passing it in.
- D: FlakeAnalyzer depends on IFlakeStrategy list (injected), not concretions.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page
    from playwright.async_api import Page as AsyncPage

logger = logging.getLogger(__name__)


# ── Flake categories ──────────────────────────────────────────────────────────

class FlakeCategory(Enum):
    """Root-cause categories for a Playwright action failure."""
    SELECTOR_MISSING    = "selector_missing"    # element not in DOM — selector wrong
    NOT_INTERACTABLE    = "not_interactable"    # element exists but disabled/hidden
    COVERED_BY_OVERLAY  = "covered_by_overlay"  # another element intercepts the click
    STRICT_VIOLATION    = "strict_violation"    # selector matches multiple elements
    ANIMATION_RUNNING   = "animation_running"   # element is still moving/transitioning
    UNKNOWN             = "unknown"             # none of the above


# ── Strategy result ───────────────────────────────────────────────────────────

@dataclass
class StrategyResult:
    """What a strategy did and what MaxHealPage should do next."""
    should_retry: bool = False          # True  → re-run the original action
    healed_selector: str | None = None  # set   → use this selector instead
    wait_ms: int = 0                    # > 0   → wait before retry


# ── Keyword maps for classification ──────────────────────────────────────────

_SELECTOR_MISSING_HINTS = [
    "waiting for locator",
    "waiting for selector",
    "no element found",
    "expected to be attached",
]
_NOT_INTERACTABLE_HINTS = [
    "element is not visible",
    "is not visible",
    "expected to be visible",
    "element is not enabled",
    "is not enabled",
    "expected to be enabled",
    "element is disabled",
    "is disabled",
    "not attached",
    "detached",
]
_OVERLAY_HINTS = [
    "intercepts pointer events",
    "other element would receive the click",
    "element is hidden",
    "overlay",
]
_STRICT_HINTS = [
    "strict mode violation",
    "resolved to",
    "multiple elements",
]
_ANIMATION_HINTS = [
    "element is not stable",
    "is not stable",
    "still animating",
    "layout is still changing",
]


def classify_error(error: str) -> FlakeCategory:
    """Map a Playwright error message to a FlakeCategory."""
    low = error.lower()
    if any(h in low for h in _ANIMATION_HINTS):
        return FlakeCategory.ANIMATION_RUNNING
    if any(h in low for h in _OVERLAY_HINTS):
        return FlakeCategory.COVERED_BY_OVERLAY
    if any(h in low for h in _STRICT_HINTS):
        return FlakeCategory.STRICT_VIOLATION
    if any(h in low for h in _NOT_INTERACTABLE_HINTS):
        return FlakeCategory.NOT_INTERACTABLE
    if any(h in low for h in _SELECTOR_MISSING_HINTS):
        return FlakeCategory.SELECTOR_MISSING
    return FlakeCategory.UNKNOWN


# ── FlakeAnalyzer ─────────────────────────────────────────────────────────────

class FlakeAnalyzer:
    """Classifies a Playwright error and delegates to the right strategy.

    Strategies are tried in order until one returns ``should_retry=True``
    or provides a ``healed_selector``.

    Inject strategies via the constructor (Dependency Inversion)::

        analyzer = FlakeAnalyzer(strategies=[
            LLMHealStrategy(engine),
            NotInteractableStrategy(),
            OverlayStrategy(),
            StrictViolationStrategy(engine),
            AnimationStrategy(),
        ])
    """

    def __init__(self, strategies: list) -> None:
        self._strategies = strategies

    def handle(
        self, page: "Page", selector: str, error: str
    ) -> StrategyResult:
        """Classify the error and ask each compatible strategy to handle it."""
        category = classify_error(error)
        logger.debug("[MaxHeal] Flake category: %s for %r", category.value, selector)

        for strategy in self._strategies:
            if strategy.can_handle(category):
                result = strategy.handle(page, selector, error, category)
                if result.should_retry or result.healed_selector:
                    return result

        # Nothing worked — tell MaxHealPage to not retry
        return StrategyResult(should_retry=False)


class AsyncFlakeAnalyzer:
    """Async variant of FlakeAnalyzer."""

    def __init__(self, strategies: list) -> None:
        self._strategies = strategies

    async def handle(
        self, page: "AsyncPage", selector: str, error: str
    ) -> StrategyResult:
        category = classify_error(error)
        logger.debug("[MaxHeal] Async Flake category: %s for %r", category.value, selector)

        for strategy in self._strategies:
            if strategy.can_handle(category):
                result = await strategy.handle(page, selector, error, category)
                if result.should_retry or result.healed_selector:
                    return result

        return StrategyResult(should_retry=False)
