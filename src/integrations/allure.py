"""
allure.py — Native integration with Allure reporting.
"""
import functools
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

def integrate_allure() -> bool:
    """Monkeypatches allure.step to automatically sync with max_heal's global_context.
    
    Returns:
        bool: True if allure was successfully monkeypatched, False if allure is not installed.
    """
    try:
        import allure
    except ImportError:
        logger.warning("[MaxHeal] Allure is not installed. Skipping Allure integration.")
        return False

    from max_heal.heal_engine import global_context

    _orig_add_step = allure.step

    @contextmanager
    @functools.wraps(_orig_add_step)
    def _maxheal_allure_step(title, *args, **kwargs):
        # Allow class methods to pass 'self' args if utilized natively via allure
        prev_step = global_context.get("Current Auto Step")
        
        # When allure is used as a decorator without parenthesis, title might be a callable.
        # But typically `allure.step("description")` is used, so title is a string.
        if isinstance(title, str):
            global_context["Current Auto Step"] = title
            
        try:
            with _orig_add_step(title, *args, **kwargs):
                yield
        finally:
            if isinstance(title, str):
                if prev_step is not None:
                    global_context["Current Auto Step"] = prev_step
                else:
                    global_context.pop("Current Auto Step", None)

    allure.step = _maxheal_allure_step
    
    import max_heal.heal_engine as heal_engine
    heal_engine._ALLURE_INTEGRATED = True
    
    logger.info("[MaxHeal] Successfully integrated with allure.step().")
    return True
