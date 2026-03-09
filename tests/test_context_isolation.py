import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from max_heal.heal_engine import global_context, max_step


def _thread_worker(worker_id: int) -> bool:
    """A worker that sets a context and sleeps, verifying it isn't overwritten."""
    global_context["Worker_ID"] = str(worker_id)
    # Sleep to force a race condition if dict was shared
    time.sleep(0.1)
    
    # Assert isolation
    assert global_context["Worker_ID"] == str(worker_id)
    return True


def test_thread_isolation():
    """Verify ThreadPoolExecutor isolates global_context using ContextVars."""
    global_context.clear()
    global_context["Worker_ID"] = "MainThread"
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(_thread_worker, i) for i in range(5)]
        
        # Wait for all threads to finish; raises exception if an assert fails inside the worker
        for f in futures:
            assert f.result() is True
            
    # The main thread should remain completely isolated from the chaos
    assert global_context["Worker_ID"] == "MainThread"


@pytest.mark.asyncio
async def test_asyncio_isolation():
    """Verify asyncio.gather tasks isolate global_context using ContextVars."""
    global_context.clear()
    global_context["Worker_ID"] = "MainAsync"

    async def _async_worker(worker_id: int):
        with max_step(f"Step_{worker_id}"):
            global_context["Worker_ID"] = f"Async_{worker_id}"
            # Force an event loop context switch
            await asyncio.sleep(0.1)
            
            assert global_context["Worker_ID"] == f"Async_{worker_id}"
            assert global_context["Current Auto Step"] == f"Step_{worker_id}"
        return True

    results = await asyncio.gather(*[_async_worker(i) for i in range(5)])
    assert all(results)
    
    # Ensure the parent event loop task context was untouched
    assert global_context["Worker_ID"] == "MainAsync"
    assert "Current Auto Step" not in global_context
