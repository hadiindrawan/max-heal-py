"""
example_flake_analyzer.py — Demo of all 5 FlakeAnalyzer strategies.

Runs against a self-contained local HTML page (no server needed).
Each scenario simulates a real-world flakiness cause:

  1. SELECTOR_MISSING   — broken selector → LLM heals to correct one
  2. NOT_INTERACTABLE   — button disabled 2s then becomes enabled
  3. COVERED_BY_OVERLAY — loading spinner blocks button for 1.5s
  4. STRICT_VIOLATION   — selector matches 3 elements → LLM narrows it
  5. ANIMATION_RUNNING  — button slides in via CSS animation

Usage:
    cd /Users/hadi/Documents/Hadi/Research/max-heal
    .venv/bin/python python/examples/example_flake_analyzer.py
"""
import logging
import os
import sys

from playwright.sync_api import sync_playwright, expect

# ── Ensure maxtest_auto is importable ──────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from maxtest_auto import MaxHealConfig, create_maxheal_page
from maxtest_auto.flake_analyzer import FlakeAnalyzer, FlakeCategory, classify_error

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)

MAXHEAL_CONFIG = MaxHealConfig(
    api_key=os.environ.get(
        "OPENROUTER_API_KEY",
        "your-api-key",
    ),
    model="openai/gpt-4o-mini",
    max_retries=3,
)

# ── Local HTML with 5 flaky scenarios ─────────────────────────────────────────
DEMO_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>MaxHeal FlakeAnalyzer Demo</title>
  <style>
    body { font-family: sans-serif; padding: 24px; background: #0f0f1a; color: #e2e8f0; }
    h1   { color: #a78bfa; margin-bottom: 4px; }
    h2   { color: #818cf8; margin-top: 32px; font-size: 1rem; }
    .scenario { background: #1e1e2e; border: 1px solid #313155;
                border-radius: 8px; padding: 16px; margin: 12px 0; }
    button { padding: 8px 20px; border-radius: 6px; border: none;
             background: #7c3aed; color: white; cursor: pointer; font-size: 14px; }
    button:disabled { background: #555; cursor: not-allowed; }
    input  { padding: 8px; border-radius: 6px; border: 1px solid #444;
             background: #2d2d44; color: white; width: 220px; }
    .overlay { position: absolute; top: 0; left: 0; width: 100%; height: 100%;
               background: rgba(0,0,0,0.7); display: flex;
               align-items: center; justify-content: center;
               font-size: 1.2rem; color: #a78bfa; z-index: 10; }
    .box     { position: relative; }

    /* Scenario 5: sliding animation */
    @keyframes slideIn {
      0%   { transform: translateX(-200px); opacity: 0; }
      100% { transform: translateX(0);      opacity: 1; }
    }
    #animated-btn {
      animation: slideIn 2s ease-out forwards;
    }
  </style>
</head>
<body>
  <h1>MaxHeal — FlakeAnalyzer Demo</h1>

  <!-- Scenario 1: Broken selector (SELECTOR_MISSING) -->
  <div class="scenario">
    <h2>Scenario 1 · SELECTOR_MISSING</h2>
    <input id="real-email-input"
           data-testid="email-input"
           placeholder="Enter email" />
    <p id="s1-result" style="display:none;color:#4ade80">✅ Filled!</p>
  </div>

  <!-- Scenario 2: Disabled button (NOT_INTERACTABLE) -->
  <div class="scenario">
    <h2>Scenario 2 · NOT_INTERACTABLE</h2>
    <button id="delayed-btn" disabled>Loading… (enables in 2s)</button>
    <p id="s2-result" style="display:none;color:#4ade80">✅ Clicked!</p>
    <script>
      setTimeout(function() {
        var b = document.getElementById('delayed-btn');
        b.disabled = false;
        b.textContent = 'Submit';
      }, 2000);
    </script>
  </div>

  <!-- Scenario 3: Overlay blocking button (COVERED_BY_OVERLAY) -->
  <div class="scenario box">
    <h2>Scenario 3 · COVERED_BY_OVERLAY</h2>
    <div id="loading-overlay" class="overlay">⏳ Loading…</div>
    <button id="confirm-btn">Confirm</button>
    <p id="s3-result" style="display:none;color:#4ade80">✅ Clicked through overlay!</p>
    <script>
      setTimeout(function() {
        var el = document.getElementById('loading-overlay');
        if (el) el.remove();
      }, 1500);
    </script>
  </div>

  <!-- Scenario 4: Multiple matches (STRICT_VIOLATION) -->
  <div class="scenario">
    <h2>Scenario 4 · STRICT_VIOLATION</h2>
    <button class="action-btn" data-action="delete">Delete</button>
    <button class="action-btn" data-action="edit"   id="target-edit-btn">Edit</button>
    <button class="action-btn" data-action="view">View</button>
    <p id="s4-result" style="display:none;color:#4ade80">✅ Clicked correct button!</p>
  </div>

  <!-- Scenario 5: Animated element (ANIMATION_RUNNING) -->
  <div class="scenario">
    <h2>Scenario 5 · ANIMATION_RUNNING</h2>
    <button id="animated-btn">Animated Button</button>
    <p id="s5-result" style="display:none;color:#4ade80">✅ Clicked after animation!</p>
  </div>

  <script>
    // Mark results when buttons/inputs are interacted with
    document.querySelectorAll('button').forEach(function(btn) {
      btn.addEventListener('click', function() {
        var sid = btn.closest('.scenario').querySelector('[id^="s"]');
        if (sid) sid.style.display = 'block';
      });
    });
    document.getElementById('real-email-input').addEventListener('input', function() {
      document.getElementById('s1-result').style.display = 'block';
    });
  </script>
</body>
</html>
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

def section(title: str) -> None:
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print('─'*60)

def check(category: FlakeCategory, expected: FlakeCategory, msg: str) -> None:
    ok = category == expected
    print(f"  {'✅' if ok else '❌'} classify_error → [{category.value}] (expected: {expected.value})")
    print(f"     error: {msg[:70]}")


# ── Demo run ──────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n🔬 MaxHeal FlakeAnalyzer Demo")
    print("   Each scenario triggers a different flake category\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page    = browser.new_page()
        page.set_content(DEMO_HTML)
        auto    = create_maxheal_page(page, MAXHEAL_CONFIG)

        # ── Scenario 1: SELECTOR_MISSING ──────────────────────────────────────
        section("Scenario 1 · SELECTOR_MISSING")
        print("  Broken selector: '#wrong-input-id'")
        print("  Real element:    '#real-email-input' / [data-testid='email-input']")
        print()
        check(
            classify_error("TimeoutError: waiting for locator('#wrong-input-id')"),
            FlakeCategory.SELECTOR_MISSING,
            "TimeoutError: waiting for locator('#wrong-input-id')",
        )
        print("\n  → LLMHealStrategy: calling OpenRouter to find the correct selector…")
        auto.fill("#wrong-input-id", "user@example.com")
        expect(page.locator("#real-email-input")).to_have_value("user@example.com")
        print("  ✅ expect(#real-email-input).to_have_value('user@example.com') passed!")

        # ── Scenario 2: NOT_INTERACTABLE ─────────────────────────────────────
        section("Scenario 2 · NOT_INTERACTABLE (button disabled for 2s)")
        print("  Button is disabled on page load, becomes enabled after 2 seconds.")
        check(
            classify_error("Error: element is not enabled"),
            FlakeCategory.NOT_INTERACTABLE,
            "Error: element is not enabled",
        )
        print("\n  → NotInteractableStrategy: scroll into view + wait for enabled…")
        auto.click("#delayed-btn")
        expect(page.locator("#s2-result")).to_be_visible()
        print("  ✅ expect(#s2-result).to_be_visible() passed!")

        # ── Scenario 3: COVERED_BY_OVERLAY ───────────────────────────────────
        section("Scenario 3 · COVERED_BY_OVERLAY (loading mask for 1.5s)")
        print("  A semi-transparent overlay blocks the Confirm button.")
        check(
            classify_error("Error: element #confirm-btn intercepts pointer events"),
            FlakeCategory.COVERED_BY_OVERLAY,
            "Error: element intercepts pointer events",
        )
        print("\n  → OverlayStrategy: wait for overlay to disappear…")
        auto.click("#confirm-btn")
        expect(page.locator("#s3-result")).to_be_visible()
        print("  ✅ expect(#s3-result).to_be_visible() passed!")

        # ── Scenario 4: STRICT_VIOLATION ─────────────────────────────────────
        section("Scenario 4 · STRICT_VIOLATION (3 buttons share .action-btn)")
        print("  '.action-btn' matches 3 buttons. We want the Edit button.")
        check(
            classify_error("Error: strict mode violation, locator('.action-btn') resolved to 3 elements"),
            FlakeCategory.STRICT_VIOLATION,
            "Error: strict mode violation",
        )
        print("\n  → StrictViolationStrategy: asking LLM to make selector more specific…")
        auto.click(".action-btn")          # strict mode would normally fail
        expect(page.locator("#s4-result")).to_be_visible()
        print("  ✅ expect(#s4-result).to_be_visible() passed!")

        # ── Scenario 5: ANIMATION_RUNNING ─────────────────────────────────────
        section("Scenario 5 · ANIMATION_RUNNING (button slides in over 2s)")
        print("  Button animates (translateX) for 2 seconds before stabilizing.")
        check(
            classify_error("Error: element is not stable"),
            FlakeCategory.ANIMATION_RUNNING,
            "Error: element is not stable",
        )
        print("\n  → AnimationStrategy: polling until element stops moving…")
        auto.click("#animated-btn")
        expect(page.locator("#s5-result")).to_be_visible()
        print("  ✅ expect(#s5-result).to_be_visible() passed!")

        section("✅ All 5 FlakeAnalyzer scenarios passed!")
        browser.close()


if __name__ == "__main__":
    main()
