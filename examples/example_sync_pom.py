"""
Example: Integrating MaxHeal into an existing sync POM framework.

Shows the SOLID approach:
- DeliveryHomePageModel only stores state — healing is injected, not hardcoded.
- Tests use @flaky_sync for retry.
- expect(locator).to_be_visible() / to_contain_text() work exactly as before.
"""
import logging
import os
from playwright.sync_api import Page, sync_playwright, expect

from max_heal import (
    MaxHealConfig,
    create_maxheal_page,
    flaky_sync,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")

MAXHEAL_CONFIG = MaxHealConfig(
    api_key=os.environ.get(
        "OPENROUTER_API_KEY",
        "your-api-key",
    ),
    model="openai/gpt-4o-mini",
    max_retries=3,
)


# ── Base Page Model ────────────────────────────────────────────────────────────
#  Only ONE change from your existing code:
#  self.page = create_maxheal_page(page, MAXHEAL_CONFIG)
#  Everything else — locators, expect() calls — remains identical.

class DeliveryHomePageModel:
    def __init__(self, page: Page):
        # ✅ Wrap with MaxHeal — healing engine is wired by the factory
        self.page = create_maxheal_page(page, MAXHEAL_CONFIG)

        # Locators — unchanged from your original code
        # Returned objects are native Playwright Locators → expect() still works
        self.new_button_navbar          = self.page.locator("button[data-test='new-btn']")
        self.data_source_title          = self.page.locator("h2.data-source-title")
        self.workflow_title             = self.page.locator("h2.workflow-title")
        self.task_board_title           = self.page.locator("h2.task-board-title")
        self.navbar_profile_avatar_button = self.page.locator(".navbar-profile-avatar")
        self.navbar_company_search_input  = self.page.locator(".company-search-input")
        self.search_data_source_input_sidepane = self.page.locator(".search-data-source")
        self.data_source_header_title   = self.page.locator(".sidepanel-header-title")

    def company_option_first(self, name: str):
        return self.page.locator(f"[data-testid='company-{name}']")

    def add_draft_data_source_button_sidepane(self, platform_id: str):
        return self.page.locator(f"[data-platform-id='{platform_id}'] .add-draft-btn")

    def dropdown_data_source_option_button_by_text(self):
        return self.page.locator("text=Data Source")

    def dropdown_upload_rule_option_button_by_text(self):
        return self.page.locator("text=Upload Rule")


# ── Page Actions ───────────────────────────────────────────────────────────────
#  Zero changes needed here — all methods work exactly as before.

class DeliveryHomePage(DeliveryHomePageModel):
    def __init__(self, page: Page):
        super().__init__(page)

    def user_click_on_new_button_navbar(self):
        self.new_button_navbar.click()        # auto-heals if selector breaks

    def user_click_on_data_source_option_button(self):
        self.dropdown_data_source_option_button_by_text().click()

    def user_click_on_upload_rule_option_button(self):
        self.dropdown_upload_rule_option_button_by_text().click()

    def is_on_dashboard_page(self):
        logging.info("Checking dashboard page…")
        # ✅ expect() with to_be_visible() / to_contain_text() — unchanged
        expect(self.data_source_title).to_be_visible()
        expect(self.workflow_title).to_be_visible()
        expect(self.task_board_title).to_be_visible()
        expect(self.new_button_navbar).to_be_visible()

    def change_company(self, name: str):
        logging.info(f"Changing company to {name}…")
        self.navbar_profile_avatar_button.click()
        self.navbar_company_search_input.fill(name)
        self.company_option_first(name).click()
        self.page.wait_for_timeout(1000)

    def is_sidepanel_opened(self):
        # ✅ to_be_visible() works on native locators returned by MaxHealPage
        expect(self.data_source_header_title).to_be_visible()

    def user_search_existing_data_source_in_sidepane(self, source_name: str):
        self.search_data_source_input_sidepane.click()
        self.search_data_source_input_sidepane.fill(source_name)

    def user_click_on_add_draft_button_of_data_source_in_sidepane(self, platform_id: str):
        self.add_draft_data_source_button_sidepane(platform_id).click()


# ── Tests — use @flaky_sync for retry ─────────────────────────────────────────

@flaky_sync(max_retries=3, delay=1.0)
def test_dashboard_loads(page: Page):
    home = DeliveryHomePage(page)
    home.is_on_dashboard_page()


# ── Demo run (broken selectors → auto-heal) ───────────────────────────────────

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=400)
        page = browser.new_page()
        page.goto("https://www.selenium.dev/selenium/web/web-form.html")

        auto = create_maxheal_page(page, MAXHEAL_CONFIG)

        print("\n⌨️  Filling (broken selector) …")
        auto.fill(".broken-text-input", "MaxHeal!")

        print("🖱️  Clicking (broken selector) …")
        auto.click("#broken-submit")

        # ✅ to_be_visible() / to_contain_text() work on healed locators
        result_heading = auto.locator("h1")
        expect(result_heading).to_be_visible()

        print("\n✅ MaxHeal sync POM demo complete!")
        browser.close()


if __name__ == "__main__":
    main()
