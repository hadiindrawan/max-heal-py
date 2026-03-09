"""
factory.py — Zero-boilerplate factories for MaxHealPage.

Wires the full chain: Config → LLMClient + DomSnapshot → HealEngine
→ Strategy list → FlakeAnalyzer → MaxHealPage.

Callers only need to know MaxHealConfig and create_maxheal_page().
"""
from __future__ import annotations

from .config import MaxHealConfig
from .dom_snapshot import PlaywrightDomSnapshot, AsyncPlaywrightDomSnapshot
from .flake_analyzer import FlakeAnalyzer, AsyncFlakeAnalyzer
from .heal_engine import SyncHealEngine, AsyncHealEngine
from .llm_client import SyncOpenRouterClient, AsyncOpenRouterClient
from .maxheal_page import MaxHealPage, AsyncMaxHealPage
from .strategies import (
    AnimationStrategy,
    LLMHealStrategy,
    NotInteractableStrategy,
    OverlayStrategy,
    StrictViolationStrategy,
    AsyncAnimationStrategy,
    AsyncLLMHealStrategy,
    AsyncNotInteractableStrategy,
    AsyncOverlayStrategy,
    AsyncStrictViolationStrategy,
)
from .integrations.allure import integrate_allure


def create_maxheal_page(
    page,
    config: MaxHealConfig | None = None,
    extra_strategies: list | None = None,
) -> MaxHealPage:
    """Create a sync MaxHealPage with all 5 default strategies wired up.

    Default strategy priority order:
        1. AnimationStrategy      — wait for element to stop moving
        2. OverlayStrategy        — detect & dismiss loading masks / modals
        3. NotInteractableStrategy — scroll into view, wait for enabled
        4. StrictViolationStrategy — ask LLM to narrow the selector
        5. LLMHealStrategy        — ask LLM for a replacement selector

    Add custom strategies via ``extra_strategies`` — they run first.

    Usage::

        from max_heal import MaxHealConfig, create_maxheal_page

        config = MaxHealConfig(api_key="sk-...")
        page = create_maxheal_page(playwright_page, config)
        page.click("#might-break")

    Args:
        page:             A sync Playwright Page.
        config:           MaxHealConfig; defaults to MaxHealConfig().
        extra_strategies: Optional additional strategies, prepended to defaults.

    Returns:
        A fully wired MaxHealPage.
    """
    cfg = config or MaxHealConfig()
    
    if cfg.use_allure:
        integrate_allure()
        
    llm = SyncOpenRouterClient(cfg)
    dom = PlaywrightDomSnapshot()
    engine = SyncHealEngine(llm_client=llm, dom_snapshot=dom)

    default_strategies = [
        AnimationStrategy(),
        OverlayStrategy(),
        NotInteractableStrategy(),
        StrictViolationStrategy(heal_engine=engine, dom_snapshot=dom),
        LLMHealStrategy(heal_engine=engine),
    ]
    strategies = (extra_strategies or []) + default_strategies

    analyzer = FlakeAnalyzer(strategies=strategies)
    return MaxHealPage(
        page,
        analyzer=analyzer,
        max_retries=cfg.max_retries,
        heal_enabled=cfg.heal_enabled,
    )

def create_async_maxheal_page(
    page,
    config: MaxHealConfig | None = None,
    extra_strategies: list | None = None,
) -> AsyncMaxHealPage:
    """Create an async AsyncMaxHealPage with all 5 default strategies wired up."""
    cfg = config or MaxHealConfig()
    
    if cfg.use_allure:
        integrate_allure()
        
    llm = AsyncOpenRouterClient(cfg)
    dom = AsyncPlaywrightDomSnapshot()
    engine = AsyncHealEngine(llm_client=llm, dom_snapshot=dom)

    default_strategies = [
        AsyncAnimationStrategy(),
        AsyncOverlayStrategy(),
        AsyncNotInteractableStrategy(),
        AsyncStrictViolationStrategy(heal_engine=engine, dom_snapshot=dom),
        AsyncLLMHealStrategy(heal_engine=engine),
    ]
    strategies = (extra_strategies or []) + default_strategies

    analyzer = AsyncFlakeAnalyzer(strategies=strategies)
    return AsyncMaxHealPage(
        page,
        analyzer=analyzer,
        max_retries=cfg.max_retries,
        heal_enabled=cfg.heal_enabled,
    )
