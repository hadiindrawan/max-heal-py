"""
config.py — MaxHealConfig: single configuration dataclass for MaxHeal.
"""
from dataclasses import dataclass


@dataclass
class MaxHealConfig:
    """Configuration for MaxHeal.

    Attributes:
        api_key:      LLM provider API key (e.g. OpenRouter).
        model:        Chat model identifier.
        base_url:     LLM provider base URL.
        max_retries:  Max heal attempts per selector failure.
        heal_enabled: Toggle auto-healing globally.
        timeout:      HTTP timeout (seconds) for LLM calls.
        use_allure:   Automatically hook allure.step into LLM context.
    """

    api_key: str = ""
    model: str = "openai/gpt-4o-mini"
    base_url: str = "https://openrouter.ai/api/v1"
    max_retries: int = 3
    heal_enabled: bool = True
    timeout: float = 30.0
    use_allure: bool = False



