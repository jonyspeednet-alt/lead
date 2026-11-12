"""Diagnostic 6: how long does 'Send' take, and what does success look like?

Shares the probe folder with one address, waits for the dialog to close,
then re-opens the dialog and dumps the people list with their roles.
"""
import os
import sys

from playwright.sync_api import sync_playwright

EMAIL = "yearj6940@ttdistrict205.net"
PASSWORD = "1090RabbiR5$#@"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_verify")
TEST_FOLDER = "ZZZ Verify Probe"
MAILS = ["katherine.thompson@juno.com", "sleibow@netscape.net", "redgrilfoever@yahoo.com"]


def dump_dialogs(page, label):
    print(f"--- dialogs {label} ---", flush=True)
    for el in page.locator('[role="dialog"]').all()[:5]:
        try:
            txt = (el.inner_text() or "").strip()
            if txt and txt != "Loading...":
                print("   >>", txt[:200].replace("\n", " | "), flush=True)
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

        def make_folder(name):
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
            dlg.press_sequentially(name, delay=30)
            page.keyboard.press("Enter")
            page.wait_for_timeout(4000)

        def open_share(name):
            row = page.locator(f'tr[data-id]:has-text("{name}")').first
            row.wait_for(state="visible", timeout=15000)
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
                    return f
            return None

        make_folder(TEST_FOLDER)
        frame = open_share(TEST_FOLDER)

        inp = frame.locator('input[role="combobox"][aria-label*="Add people"]').first
        inp.click(force=True)
        for address in MAILS:
            inp.fill(address)
            page.wait_for_timeout(1200)
            page.keyboard.press("Enter")
            page.wait_for_timeout(1200)
        print("added", len(MAILS), "addresses", flush=True)

        role_btn = frame.locator('button[aria-label*="change permission"]').first
        role_btn.click(timeout=5000)
        page.wait_for_timeout(1200)
        frame.locator('[role="menuitem"]:has-text("Viewer")').first.click(timeout=5000)
        page.wait_for_timeout(800)
        print("role now:", frame.locator('button[aria-label*="change permission"]').first
              .get_attribute("aria-label"), flush=True)

        frame.locator('button:has-text("Send")').first.click(timeout=5000)
        print("Send clicked", flush=True)

        # wait for the dialog to close or an error to show
        closed = False
        for i in range(30):
            page.wait_for_timeout(2000)
            texts = []
            for el in page.locator('[role="dialog"]').all()[:5]:
                try:
                    t = (el.inner_text() or "").strip()
                    if t and t != "Loading...":
                        texts.append(t)
                except Exception:
                    pass
            if any("Unable to share" in t or "Permission denied" in t for t in texts):
                print(f"ERROR after {2*(i+1)}s:", texts[0][:200].replace("\n", " | "), flush=True)
                page.screenshot(path=os.path.join(OUT, "diag6_error.png"))
                for el in page.locator('[role="dialog"]').all():
                    try:
                        ok = el.locator('button:has-text("OK")')
                        if ok.count() and ok.first.is_visible():
                            ok.first.click()
                            page.wait_for_timeout(1500)
                    except Exception:
                        pass
                break
            if not page.locator('iframe[src*="drivesharing/driveshare"]').count():
                closed = True
                print(f"dialog closed after {2*(i+1)}s", flush=True)
                break
        page.screenshot(path=os.path.join(OUT, "diag6_after_send.png"))

        # close whatever is left
        page.keyboard.press("Escape")
        page.wait_for_timeout(2000)

        # re-open and dump the people list
        frame2 = open_share(TEST_FOLDER)
        if frame2:
            print("\n--- people list after share ---", flush=True)
            for el in frame2.locator('[role="menu"]').all()[:4]:
                try:
                    txt = (el.inner_text() or "").strip()
                    if txt:
                        print("   ", txt[:400].replace("\n", " | "), flush=True)
                except Exception:
                    pass
            print("\n--- role buttons now ---", flush=True)
            for el in frame2.locator('button[aria-label*="change permission"]').all()[:10]:
                try:
                    print("   ", el.get_attribute("aria-label"), flush=True)
                except Exception:
                    pass
            page.screenshot(path=os.path.join(OUT, "diag6_people.png"))
        print("done, dialog_closed=", closed, flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(main())
