"""Diagnostic 7: does a single recipient work, and does 'Notify people' matter?

Waits long enough for the (slow) 'Unable to share' error and detects it by
page text instead of by dialog role.
"""
import os
import sys
import time

from playwright.sync_api import sync_playwright

EMAIL = "yearj6940@ttdistrict205.net"
PASSWORD = "1090RabbiR5$#@"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_verify")
TEST_FOLDER = "ZZZ Notify Probe"
ONE_MAIL = "tscadron@hotmail.com"


def error_text(page):
    for phrase in ("Unable to share", "Permission denied", "may violate our Terms of Service"):
        try:
            loc = page.get_by_text(phrase, exact=False)
            if loc.count() and loc.first.is_visible(timeout=500):
                return phrase
        except Exception:
            continue
    return ""


def dismiss_ok(page):
    try:
        oks = page.locator('button:has-text("OK")')
        for i in range(oks.count() - 1, -1, -1):
            btn = oks.nth(i)
            if btn.is_visible(timeout=400):
                btn.click(timeout=3000)
                page.wait_for_timeout(1000)
                return True
    except Exception:
        pass
    return False


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

        # turn OFF 'Notify people' (fewer notification mails -> less spam trigger)
        try:
            notify = frame.locator('input[type="checkbox"][aria-label*="Notify"]').first
            if notify.count():
                notify.uncheck(force=True)
                print("unchecked 'Notify people'", flush=True)
        except Exception as exc:
            print("notify toggle:", exc, flush=True)

        inp = frame.locator('input[role="combobox"][aria-label*="Add people"]').first
        inp.click(force=True)
        inp.fill(ONE_MAIL)
        page.wait_for_timeout(1500)
        page.keyboard.press("Enter")
        page.wait_for_timeout(1500)

        role_btn = frame.locator('button[aria-label*="change permission"]').first
        role_btn.click(timeout=5000)
        page.wait_for_timeout(1200)
        frame.locator('[role="menuitem"]:has-text("Viewer")').first.click(timeout=5000)
        page.wait_for_timeout(800)
        print("role:", frame.locator('button[aria-label*="change permission"]').first
              .get_attribute("aria-label"), flush=True)

        frame.locator('button:has-text("Send")').first.click(timeout=5000)
        print("Send clicked at", time.strftime("%H:%M:%S"), flush=True)

        outcome = "timeout"
        for i in range(45):
            page.wait_for_timeout(3000)
            err = error_text(page)
            if err:
                outcome = f"ERROR: {err}"
                print(f"[{3*(i+1)}s] {outcome}", flush=True)
                break
            if not page.locator('iframe[src*="drivesharing/driveshare"]').count():
                outcome = "dialog closed (success?)"
                print(f"[{3*(i+1)}s] {outcome}", flush=True)
                break
        page.screenshot(path=os.path.join(OUT, "diag7_after_send.png"))
        dismiss_ok(page)
        page.keyboard.press("Escape")
        page.wait_for_timeout(2000)

        # check the folder's people list
        try:
            row = page.locator(f'tr[data-id]:has-text("{TEST_FOLDER}")').first
            row.click()
            page.wait_for_timeout(500)
            row.click(button="right")
            page.wait_for_timeout(1200)
            page.locator('[role="menuitem"]').filter(has_text="Share").first.hover()
            page.wait_for_timeout(1000)
            page.locator('[aria-label="Share, Ctrl+Alt+A"]').first.click(timeout=5000)
            page.wait_for_timeout(5000)
            for f in page.frames:
                if "drivesharing/driveshare" in (f.url or ""):
                    print("\n--- people / access state ---", flush=True)
                    for el in f.locator('[role="menu"]').all()[:4]:
                        txt = (el.inner_text() or "").strip()
                        if txt:
                            print("   ", txt[:300].replace("\n", " | "), flush=True)
                    for el in f.locator('button[aria-label*="change"]').all()[:10]:
                        print("   btn:", el.get_attribute("aria-label"), flush=True)
                    page.screenshot(path=os.path.join(OUT, "diag7_people.png"))
                    break
        except Exception as exc:
            print("re-open failed:", exc, flush=True)

        print("OUTCOME:", outcome, flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(main())
