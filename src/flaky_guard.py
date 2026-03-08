"""
flaky_guard.py — Retry decorators (sync & async) for flaky test functions.

Single Responsibility: retry logic only. No healing knowledge here.
"""
from __future__ import annotations

import asyncio
import functools
import logging
import time
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)
F = TypeVar("F", bound=Callable[..., Any])


def flaky_sync(
    max_retries: int = 3,
    delay: float = 0.5,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """Retry a **synchronous** function on failure.

    Usage::

        @flaky_sync(max_retries=3, delay=1.0)
        def test_login(page):
            home = DeliveryHomePage(page)
            home.is_on_dashboard_page()
    """
    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(1, max_retries + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < max_retries:
                        logger.warning(
                            "[MaxHeal] Flaky %d/%d %r: %s — retry in %.1fs",
                            attempt, max_retries, fn.__name__, exc, delay,
                        )
                        time.sleep(delay)
                    else:
                        logger.error("[MaxHeal] All %d attempts failed: %r",
                                     max_retries, fn.__name__)
            raise last_exc  # type: ignore[misc]
        return wrapper  # type: ignore[return-value]
    return decorator


def flaky(
    max_retries: int = 3,
    delay: float = 0.5,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """Retry an **async** function on failure.

    Usage::

        @flaky(max_retries=3, delay=1.0)
        async def test_login(page):
            ...
    """
    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(1, max_retries + 1):
                try:
                    return await fn(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < max_retries:
                        logger.warning(
                            "[MaxHeal] Flaky %d/%d %r: %s — retry in %.1fs",
                            attempt, max_retries, fn.__name__, exc, delay,
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error("[MaxHeal] All %d attempts failed: %r",
                                     max_retries, fn.__name__)
            raise last_exc  # type: ignore[misc]
        return wrapper  # type: ignore[return-value]
    return decorator
