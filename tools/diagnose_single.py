"""Diagnostic 5: does sharing with a SINGLE address work on this account?

Also checks whether the school policy blocks 'Anyone with the link'.
"""
import os
import sys

from playwright.sync_api import sync_playwright

EMAIL = "yearj6940@ttdistrict205.net"
PASSWORD = "1090RabbiR5$#@"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_verify")
TEST_FOLDER = "ZZZ Single Share Probe"
ONE_MAIL = "lucy.aquino@bellsouth.net"


def dialogs(page, label):
    print(f"--- dialogs {label} ---", flush=True)
    for el in page.locator('[role="dialog"]').all()[:5]:
        try:
            txt = (el.inner_text() or "").strip()
            if txt:
                print("   >>", txt[:160].replace("\n", " | "), flush=True)
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
        row.wait_for(state="visible", timeout=15000)
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

        dialogs(page, "after opening the share dialog")

        # --- one address only ------------------------------------------------
        inp = frame.locator('input[role="combobox"][aria-label*="Add people"]').first
        inp.click(force=True)
        inp.fill(ONE_MAIL)
        page.wait_for_timeout(1500)
        page.keyboard.press("Enter")
        page.wait_for_timeout(2000)

        role_btn = frame.locator('button[aria-label*="change permission"]').first
        print("role before:", role_btn.get_attribute("aria-label"), flush=True)
        role_btn.click(timeout=5000)
        page.wait_for_timeout(1200)
        frame.locator('[role="menuitem"]:has-text("Viewer")').first.click(timeout=5000)
        page.wait_for_timeout(1000)
        print("role after :", frame.locator('button[aria-label*="change permission"]').first
              .get_attribute("aria-label"), flush=True)

        frame.locator('button:has-text("Send")').first.click(timeout=5000)
        page.wait_for_timeout(6000)
        dialogs(page, "after Send with ONE address")
        page.screenshot(path=os.path.join(OUT, "diag5_one_send.png"))

        # dismiss whatever is on top, then look at the drive row
        for el in page.locator('[role="dialog"]').all():
            try:
                ok = el.locator('button:has-text("OK")')
                if ok.count() and ok.first.is_visible():
                    ok.first.click()
                    page.wait_for_timeout(1500)
            except Exception:
                pass
        page.keyboard.press("Escape")
        page.wait_for_timeout(2000)
        page.screenshot(path=os.path.join(OUT, "diag5_after_dismiss.png"))

        row = page.locator(f'tr[data-id]:has-text("{TEST_FOLDER}")').first
        try:
            print("drive row:", (row.inner_text() or "").replace("\n", " | ")[:250], flush=True)
        except Exception as exc:
            print("row read failed:", exc, flush=True)
        print("done", flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(main())
