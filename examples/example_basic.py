"""
Example: MaxTest Auto — Python auto-heal demo.

This script intentionally uses a broken selector (`#broken-submit`) on the
Playwright demo form page, then watches MaxTest Auto heal it automatically.

Usage:
    OPENROUTER_API_KEY=sk-...  python examples/python/example_basic.py
"""
import asyncio
import logging
import os

from playwright.async_api import async_playwright

from max_heal import MaxHealPage, MaxHealConfig, flaky

logging.basicConfig(level=logging.INFO, format="%(message)s")


config = MaxHealConfig(
    api_key=os.environ.get("OPENROUTER_API_KEY", "your-api-key"),
    model="openai/gpt-4o-mini",
    max_retries=3,
    heal_enabled=True,
)


@flaky(max_retries=2, delay=1.0)
async def run_demo() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        page = await browser.new_page()
        auto = AutoPage(page, config)

        print("\n📄 Navigating to demo form …")
        await auto.goto("https://www.selenium.dev/selenium/web/web-form.html")

        print("⌨️  Filling text input …")
        # Selector is intentionally wrong — auto-heal will fix it
        await auto.fill(".broken-text-input", "MaxHeal!")

        print("🖱️  Clicking submit …")
        # This selector is also wrong — auto-heal will fix it
        await auto.click("#broken-submit")

        print("\n✅ Done — auto-heal handled the broken selectors!")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(run_demo())
