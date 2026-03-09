"""
example_v2_features.py

This example demonstrates how to build an automation test from scratch using 
MaxHeal's Version 2 AI Intent features:
1. `max_step` block context manager
2. Inline `intent=` overrides
3. Seamless `allure` integration
"""

import os
import allure
from playwright.sync_api import sync_playwright
from max_heal import MaxHealConfig, create_maxheal_page, max_step

# Ensure you have your OpenRouter API key set
API_KEY = os.environ.get("OPENROUTER_API_KEY", "your-api-key")

MAXHEAL_CONFIG = MaxHealConfig(
    api_key=API_KEY,
    model="openai/gpt-4o-mini",
    max_retries=3,
    use_allure=True
)

def run_v2_example():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        raw_page = browser.new_page()
        
        # 2. Wrap the page with MaxHeal
        page = create_maxheal_page(raw_page, MAXHEAL_CONFIG)
        
        page.goto("https://practicetestautomation.com/practice-test-login/")
        
        # -------------------------------------------------------------
        # Feature A: `max_step` Scope
        # Any failures in this block will feed exactly this sentence
        # to the LLM to help it heal the locators smartly!
        # -------------------------------------------------------------
        with max_step("User fills out Username and Password fields"):
            # If "#username" breaks, LLM knows we are looking for the username field!
            page.fill("#username", "student")
            page.fill("#password", "Password123")
            
        # -------------------------------------------------------------
        # Feature B: Inline Intent kwargs
        # You can bypass the block approach and give laser-targeted 
        # hints specifically to a single Playwright action:
        # -------------------------------------------------------------
        page.click("#submit", intent="The main 'Submit' button below the form")
        
        # Wait for the next page to load successfully
        page.wait_for_url("**/practice-test-exceptions/")
        
        # -------------------------------------------------------------
        # Feature C: Allure Integration
        # If your team already uses Allure, `integrate_allure()` (from step 1)
        # means you don't even need `max_step`. It hooks into allure natively!
        # -------------------------------------------------------------
        with allure.step("User verifies that the success banner is visible"):
            from playwright.sync_api import expect
            # Even native expects are wrapped and will use the Allure intent!
            expect(page.locator(".custom-success-message")).to_be_visible()
            
        browser.close()

if __name__ == "__main__":
    print("Running MaxHeal V2 Example...")
    run_v2_example()
