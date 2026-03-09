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

## Providing "Intent" Context (V2)

MaxHeal works best when it knows *what* the user is trying to accomplish. You can inject this intent directly into the AI's brain using the built-in `max_step` context manager.

```python
from max_heal import max_step

def test_login(page):
    with max_step("User fills out the login form with admin credentials"):
        page.fill("#user", "admin")
        page.fill("#pass", "secret")
        
    with max_step("User clicks the submit button"):
        page.click(".btn-primary")
```
If a selector fails anywhere inside a `max_step` block, that exact description is routed to the LLM to help exactly pinpoint the missing button or field!

### Inline Intents
You can also pass `intent=` directly to actions for laser-focused precision:
```python
page.click("#submit", intent="The login button on the top right corner")
```

### Native Allure Integration

If your framework already uses `allure.step`, you don't even need to rewrite your code to use `max_step`. MaxHeal ships with a native Allure plugin that automatically parses your existing Allure steps and feeds them to the LLM.

Simply enable it in your `MaxHealConfig`:

```python
MAXHEAL_CONFIG = MaxHealConfig(
    api_key="...",
    use_allure=True # Automatically syncs allure.step() into MaxHeal's LLM context!
)
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
| `use_allure`   | `False`                    | Hook allure.step into LLM context      |

## Concurrency & Thread-Safety (pytest-xdist)

MaxHeal is **100% thread-safe and async-safe**. 
All intents, steps, and `global_context` mutations are securely bound using Python's native `ContextVars`. This means you can run hundreds of UI tests concurrently using `pytest -n 16` or `asyncio.gather()`, and the LLM contexts will *never* leak or cross-pollinate between test workers!

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
