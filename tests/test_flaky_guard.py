"""
Unit tests for the @flaky decorator.
"""
from __future__ import annotations

import pytest
from max_heal.flaky_guard import flaky


@pytest.mark.asyncio
async def test_flaky_succeeds_on_first_try():
    calls = []

    @flaky(max_retries=3)
    async def fn():
        calls.append(1)
        return "ok"

    result = await fn()
    assert result == "ok"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_flaky_retries_and_succeeds():
    calls = []

    @flaky(max_retries=3, delay=0)
    async def fn():
        calls.append(1)
        if len(calls) < 3:
            raise AssertionError("not yet")
        return "ok"

    result = await fn()
    assert result == "ok"
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_flaky_raises_after_max_retries():
    calls = []

    @flaky(max_retries=3, delay=0)
    async def fn():
        calls.append(1)
        raise AssertionError("always fails")

    with pytest.raises(AssertionError, match="always fails"):
        await fn()

    assert len(calls) == 3


@pytest.mark.asyncio
async def test_flaky_preserves_function_name():
    @flaky(max_retries=2, delay=0)
    async def my_special_test():
        pass

    assert my_special_test.__name__ == "my_special_test"
