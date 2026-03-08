# MaxHeal

> Playwright wrapper with **LLM-powered auto-heal** and **flaky auto-fix** for Python.

## Features

- 🔧 **Auto-heal** broken selectors at runtime using an LLM (via [OpenRouter](https://openrouter.ai))
- 🔁 **Flaky guard** — smart retry decorator for unstable async tests
- 🪶 **Zero friction** — drop-in wrapper around your existing Playwright `page`
- ⚡ **Selector cache** — healed selectors are reused within a session (no duplicate LLM calls)

## Python Quick Start (Zero-Setup)

Install via pip:

```bash
pip install max-heal
```

Then, simply configure MaxHeal globally before your tests run (e.g., in a `conftest.py` or application setup file). MaxHeal will automatically intercept all `playwright.sync_api.expect` and `playwright.async_api.expect` calls across your entire framework.

```python
import pytest
from playwright.sync_api import Page
from max_heal import MaxHealConfig, create_maxheal_page

# 1. Global AI Configuration
MAXHEAL_CONFIG = MaxHealConfig(
    api_key="sk-or-your-api-key",
    model="openai/gpt-4o-mini",
    max_retries=3
)

# 2. Wrap the global Playwright page fixture natively
@pytest.fixture
def page(page: Page):
    # This automatically activates the Global AssertPatch for this page
    return create_maxheal_page(page, MAXHEAL_CONFIG)

# 3. Write native tests normally — NO CODE CHANGES REQUIRED!
def test_login(page: Page):
    page.goto("https://example.com/login")
    
    # If the DOM changes and `#btn-signin` breaks, MaxHeal instantly freezes,
    # queries the LLM, injects the new selector, and retries the assert!
    from playwright.sync_api import expect
    expect(page.locator("#btn-signin")).to_be_visible(timeout=5000)
    page.locator("#btn-signin").click()
```

## Advanced AI Context (Allure/Logs)
MaxHeal allows you to inject testing metadata directly into the LLM's brain so it understands *what* the automation is actually trying to do. Just populate the `global_context` dictionary.

```python
from max_heal import global_context
import allure

def add_step(step_name):
    global_context["Current Test Step"] = step_name
    allure.step(step_name)
```



## Configuration

| Option         | Python default             | Description                            |
|----------------|----------------------------|----------------------------------------|
| `api_key`      | `""`                       | OpenRouter API key                     |
| `model`        | `openai/gpt-4o-mini`       | Chat model (any OpenRouter model)      |
| `base_url`     | `https://openrouter.ai/...`| OpenRouter base URL                    |
| `max_retries`  | `3`                        | Heal attempts per selector failure     |
| `heal_enabled` | `True`                     | Toggle auto-healing globally           |
| `timeout`      | `30.0`                     | HTTP timeout for LLM calls (seconds)   |

## How It Works

```
Test Action -> Timeout Error / Strict Mode Violation
        │
        ▼
  Snapshot DOM (aria tree + HTML)
        │
        ▼
  Prompt LLM (selector + error + DOM + Context)
        │
        ▼
  Parse healed selector
        │
        ▼
  Retry Native Assertion directly with new selector
        │
        ▼
  Cache result to prevent duplicate LLM calls
```

## License

MIT
