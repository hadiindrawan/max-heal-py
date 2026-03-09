import pytest
from max_heal.heal_engine import global_context, max_step
from max_heal.maxheal_page import MaxHealPage, AsyncMaxHealPage

def test_max_step_populates_context():
    global_context.clear()
    with max_step("User logs in"):
        assert global_context.get("Current Auto Step") == "User logs in"
    assert "Current Auto Step" not in global_context

def test_max_step_restores_previous_context():
    global_context.clear()
    with max_step("Outer step"):
        assert global_context.get("Current Auto Step") == "Outer step"
        with max_step("Inner step"):
            assert global_context.get("Current Auto Step") == "Inner step"
        assert global_context.get("Current Auto Step") == "Outer step"
    assert "Current Auto Step" not in global_context

def test_explicit_intent_overrides_context():
    global_context.clear()
    
    class MockPage:
        def click(self, selector, *args, **kwargs):
            assert global_context.get("Explicit Action Intent") == "Login button"
            return None
            
    page = MaxHealPage(MockPage(), analyzer=None, heal_enabled=False)
    
    with max_step("User fills out form"):
        assert global_context.get("Current Auto Step") == "User fills out form"
        page.click("#login", intent="Login button")
        assert global_context.get("Current Auto Step") == "User fills out form"
        
    assert "Explicit Action Intent" not in global_context

@pytest.mark.asyncio
async def test_async_explicit_intent_overrides_context():
    global_context.clear()
    
    class MockAsyncPage:
        async def click(self, selector, *args, **kwargs):
            assert global_context.get("Explicit Action Intent") == "Async Login button"
            return None
            
    page = AsyncMaxHealPage(MockAsyncPage(), analyzer=None, heal_enabled=False)
    
    with max_step("User fills out form"):
        assert global_context.get("Current Auto Step") == "User fills out form"
        await page.click("#login", intent="Async Login button")
        assert global_context.get("Current Auto Step") == "User fills out form"
        
    assert "Explicit Action Intent" not in global_context
