"""Diagnostic 2: find the role dropdown (Editor/Viewer) inside the share dialog.

Logs in, opens the share dialog for a probe folder and dumps the menus for
the 'add people' role selector and the general-access role selector.
Nothing is shared with anybody.
"""
import os
import sys

from playwright.sync_api import sync_playwright

EMAIL = "yearj6940@ttdistrict205.net"
PASSWORD = "1090RabbiR5$#@"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_verify")
os.makedirs(OUT, exist_ok=True)
TEST_FOLDER = "ZZZ Role Probe Test"


def dump(name, text):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as handle:
        handle.write(text)
    print(f"[saved] {name} ({len(text)} chars)", flush=True)


def describe(locators, label):
    print(f"\n--- {label} ---", flush=True)
    for loc in locators:
        try:
            for el in loc.all()[:12]:
                try:
                    print(f"   tag={el.evaluate('e => e.tagName'):6s} "
                          f"role={el.get_attribute('role') or '-':12s} "
                          f"aria={(el.get_attribute('aria-label') or '-')[:55]:55s} "
                          f"text={(el.inner_text() or '').strip()[:40]!r}", flush=True)
                except Exception:
                    pass
        except Exception:
            pass


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=False,
                                    args=["--disable-blink-features=AutomationControlled",
                                          "--start-maximized"])
        context = browser.new_context(
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()

        page.goto("https://accounts.google.com/signin", timeout=30000)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2000)
        page.locator('input#identifierId, input[name="identifier"], input[type="email"]').first.fill(EMAIL)
        page.wait_for_timeout(500)
        try:
            page.locator('#identifierNext, button:has-text("Next")').first.click(timeout=3000)
        except Exception:
            page.keyboard.press("Enter")
        page.wait_for_timeout(3000)
        pw = page.locator('input[type="password"]').first
        pw.wait_for(state="visible", timeout=10000)
        pw.fill(PASSWORD)
        page.wait_for_timeout(500)
        try:
            page.locator('#passwordNext, button:has-text("Next")').first.click(timeout=3000)
        except Exception:
            page.keyboard.press("Enter")
        page.wait_for_timeout(8000)

        page.goto("https://drive.google.com/drive/my-drive", timeout=45000)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(4000)

        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
        page.keyboard.press("Shift+F")
        page.wait_for_timeout(1500)
        if not page.locator('div[role="dialog"] input[type="text"]').is_visible(timeout=3000):
            page.locator('button[aria-label="New"]').first.click(timeout=3000)
            page.wait_for_timeout(800)
            page.locator('[role="menuitem"]:has-text("New folder")').first.click(timeout=3000)
        dlg = page.locator('div[role="dialog"] input[type="text"]').last
        dlg.wait_for(state="visible", timeout=10000)
        dlg.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        dlg.press_sequentially(TEST_FOLDER, delay=30)
        page.keyboard.press("Enter")
        page.wait_for_timeout(4000)

        row = page.locator(f'tr[data-id]:has-text("{TEST_FOLDER}")').first
        row.wait_for(state="visible", timeout=10000)
        row.click()
        page.wait_for_timeout(500)
        row.click(button="right")
        page.wait_for_timeout(1200)
        page.locator('[role="menuitem"]').filter(has_text="Share").first.hover()
        page.wait_for_timeout(1000)
        page.locator('[aria-label="Share, Ctrl+Alt+A"]').first.click(timeout=5000)
        page.wait_for_timeout(5000)

        frame = None
        for f in page.frames:
            if "drivesharing/driveshare" in (f.url or ""):
                frame = f
                break
        if frame is None:
            print("NO SHARE FRAME", flush=True)
            return 2

        print("frame url:", frame.url, flush=True)

        describe([
            frame.locator("button"),
            frame.locator('[role="button"]'),
            frame.locator('[role="combobox"]'),
            frame.locator('[role="menuitem"]'),
        ], "all buttons / roles in the share dialog")

        # ---- 1. general access dropdown ------------------------------------
        print("\n=== clicking the general access dropdown ===", flush=True)
        try:
            frame.locator('button[aria-label*="change general access"]').first.click(timeout=5000)
        except Exception as exc:
            print("general access button failed:", exc, flush=True)
        page.wait_for_timeout(1500)
        page.screenshot(path=os.path.join(OUT, "diag_general_menu.png"))
        describe([
            frame.locator('[role="menuitem"]'),
            frame.locator('li[role="none"]'),
            frame.locator('[role="option"]'),
            frame.locator('span:has-text("Anyone with the link")'),
        ], "general access menu items")

        # pick "Anyone with the link"
        try:
            frame.locator('span:has-text("Anyone with the link")').last.click(timeout=5000)
            print("clicked 'Anyone with the link'", flush=True)
        except Exception as exc:
            print("anyone with the link failed:", exc, flush=True)
        page.wait_for_timeout(2000)
        page.screenshot(path=os.path.join(OUT, "diag_general_anyone.png"))

        # after switching, a role dropdown for the link appears
        describe([
            frame.locator('button'),
            frame.locator('[role="button"]'),
        ], "after switching to 'Anyone with the link'")

        # try to open that role dropdown
        print("\n=== looking for the link role dropdown ===", flush=True)
        for sel in ['button[aria-label*="role"]', 'button[aria-label*="Role"]',
                    '[role="combobox"][aria-label*="role"]',
                    'div[role="button"][aria-label*="role"]']:
            try:
                loc = frame.locator(sel).first
                if loc.is_visible(timeout=1500):
                    print("visible role trigger:", sel, flush=True)
                    loc.click(timeout=3000)
                    page.wait_for_timeout(1200)
                    page.screenshot(path=os.path.join(OUT, "diag_role_menu.png"))
                    describe([frame.locator('[role="menuitem"]'), frame.locator('[role="option"]')],
                             "role menu items")
                    break
            except Exception as exc:
                print("  ", sel, "->", exc, flush=True)

        page.screenshot(path=os.path.join(OUT, "diag_role_probe.png"))
        print("done", flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(main())
