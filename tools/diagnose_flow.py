"""Diagnostic 4: full share flow with the real account.

- adds one address, opens the role dropdown, picks Viewer
- sends, then re-opens the dialog to verify the permission stuck
- also tries the 'Anyone with the link' general access and reports any error dialog
"""
import os
import sys

from playwright.sync_api import sync_playwright

EMAIL = "yearj6940@ttdistrict205.net"
PASSWORD = "1090RabbiR5$#@"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_verify")
TEST_FOLDER = "ZZZ Final Probe"
PROBE_MAILS = ["accessorysurpluscom@yahoo.com", "acoizza@yahoo.com"]


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
        if frame is None:
            print("NO FRAME", flush=True)
            return 2

        # ---- add people, then force the role to Viewer ---------------------
        inp = frame.locator('input[role="combobox"][aria-label*="Add people"]').first
        for address in PROBE_MAILS:
            inp.click(force=True)
            inp.fill(address)
            page.wait_for_timeout(1200)
            page.keyboard.press("Enter")
            page.wait_for_timeout(1500)

        role_btn = frame.locator('button[aria-label*="change permission"]').first
        print("role button aria:", role_btn.get_attribute("aria-label"), flush=True)
        role_btn.click(timeout=5000)
        page.wait_for_timeout(1500)
        page.screenshot(path=os.path.join(OUT, "diag4_role_menu.png"))
        print("\n--- menu items ---", flush=True)
        for el in frame.locator('[role="menuitem"]').all()[:12]:
            try:
                print(f"   role={el.get_attribute('role')} aria={el.get_attribute('aria-label')} "
                      f"text={(el.inner_text() or '').strip()[:40]!r}", flush=True)
            except Exception:
                pass

        try:
            frame.locator('[role="menuitem"]:has-text("Viewer")').first.click(timeout=5000)
            print(">> Viewer selected", flush=True)
        except Exception as exc:
            print("!! could not select Viewer:", exc, flush=True)
        page.wait_for_timeout(1500)
        page.screenshot(path=os.path.join(OUT, "diag4_viewer_set.png"))
        try:
            print("role button now:", frame.locator('button[aria-label*="change permission"]').first
                  .get_attribute("aria-label"), flush=True)
        except Exception:
            pass

        # ---- send -----------------------------------------------------------
        try:
            frame.locator('button:has-text("Send")').first.click(timeout=5000)
            print(">> Send clicked", flush=True)
        except Exception as exc:
            print("!! send failed:", exc, flush=True)
        page.wait_for_timeout(5000)
        page.screenshot(path=os.path.join(OUT, "diag4_after_send.png"))

        # ---- general access --------------------------------------------------
        frame2 = open_share(TEST_FOLDER)
        if frame2:
            try:
                frame2.locator('button[aria-label*="change general access"]').first.click(timeout=5000)
                page.wait_for_timeout(1500)
                frame2.locator('span:has-text("Anyone with the link")').last.click(timeout=5000)
                print(">> Anyone with the link clicked", flush=True)
                page.wait_for_timeout(2500)
                page.screenshot(path=os.path.join(OUT, "diag4_general.png"))
                for el in page.locator('[role="dialog"]').all()[:4]:
                    txt = (el.inner_text() or "").strip()
                    if "Permission denied" in txt:
                        print("!! permission denied dialog:", txt[:120], flush=True)
                        ok = el.locator('button:has-text("OK")')
                        if ok.count():
                            ok.first.click()
                            print(">> dismissed the error dialog", flush=True)
                            page.wait_for_timeout(2500)
                try:
                    print("general access now:", frame2.locator(
                        'button[aria-label*="change general access"]').first.get_attribute("aria-label"),
                        flush=True)
                    print("link permission now:", frame2.locator(
                        'button[aria-label*="change link permission"]').first.get_attribute("aria-label"),
                        flush=True)
                except Exception as exc:
                    print("could not read the access state:", exc, flush=True)
                page.screenshot(path=os.path.join(OUT, "diag4_general_after.png"))
            except Exception as exc:
                print("!! general access failed:", exc, flush=True)

        # ---- what does Drive think now? -------------------------------------
        page.goto("https://drive.google.com/drive/my-drive", timeout=45000)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(4000)
        row = page.locator(f'tr[data-id]:has-text("{TEST_FOLDER}")').first
        try:
            print("drive row:", (row.inner_text() or "").replace("\n", " | ")[:200], flush=True)
        except Exception:
            pass
        page.screenshot(path=os.path.join(OUT, "diag4_drive_row.png"))
        print("done", flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(main())
