"""
dom_snapshot.py — DOM snapshot implementations (sync & async).

Each class implements a single Protocol (IDomSnapshot / IAsyncDomSnapshot).
Swap this out for any custom snapshot strategy without touching MaxHealPage.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page as SyncPage
    from playwright.async_api import Page as AsyncPage

_MAX_CHARS = 4_000
_JS = """
(function() {
  function nodeInfo(el, depth) {
    if (depth > 8) return '';
    var role = el.getAttribute('role') || el.tagName.toLowerCase();
    var id = el.id ? '#' + el.id : '';
    var cls = el.className && typeof el.className === 'string'
      ? '.' + el.className.trim().split(/\\s+/).join('.') : '';
    var text = (el.textContent || '').trim().slice(0, 60);
    var line = '  '.repeat(depth) + '[' + role + ']' + id + cls +
               (text ? ' "' + text + '"' : '');
    var kids = Array.from(el.children)
      .map(function(c){ return nodeInfo(c, depth+1); })
      .filter(Boolean).join('\\n');
    return kids ? line + '\\n' + kids : line;
  }
  return nodeInfo(document.body, 0);
})()
"""


def _trim(text: str) -> str:
    if len(text) <= _MAX_CHARS:
        return text
    h = _MAX_CHARS // 2
    return text[:h] + f"\n...[trimmed {len(text)-_MAX_CHARS} chars]...\n" + text[-h:]


class PlaywrightDomSnapshot:
    """Sync DOM snapshot via Playwright ``page.evaluate``."""

    def snapshot(self, page: "SyncPage", selector: str | None = None) -> str:
        try:
            s: str = page.evaluate(_JS)
            if s:
                return _trim(s)
        except Exception:
            pass
        try:
            return _trim(page.evaluate("document.body.innerHTML"))
        except Exception:
            return "(DOM unavailable)"


class AsyncPlaywrightDomSnapshot:
    """Async DOM snapshot via Playwright ``page.evaluate``."""

    async def snapshot(self, page: "AsyncPage", selector: str | None = None) -> str:
        try:
            s: str = await page.evaluate(_JS)
            if s:
                return _trim(s)
        except Exception:
            pass
        try:
            return _trim(await page.evaluate("document.body.innerHTML"))
        except Exception:
            return "(DOM unavailable)"
