"""Diagnostic 3: explore the 'Add people' role dropdown and the permission-denied dialog."""
import os
import sys

from playwright.sync_api import sync_playwright

EMAIL = "yearj6940@ttdistrict205.net"
PASSWORD = "1090RabbiR5$#@"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_verify")
TEST_FOLDER = "ZZZ People Probe Test"
PROBE_MAIL = "accessorysurpluscom@yahoo.com"


def dump_buttons(frame, label):
    print(f"\n--- {label} ---", flush=True)
    try:
        for el in frame.locator("button").all()[:20]:
            try:
                print(f"   aria={(el.get_attribute('aria-label') or '-')[:60]:60s} "
                      f"text={(el.inner_text() or '').strip()[:30]!r}", flush=True)
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

        # ---- is a "Permission denied" dialog on the page already? ----------
        print("\n=== page-level dialogs ===", flush=True)
        for el in page.locator('[role="dialog"]').all()[:5]:
            try:
                print("   dialog text:", (el.inner_text() or "").strip()[:120].replace("\n", " | "), flush=True)
            except Exception:
                pass

        dump_buttons(frame, "buttons right after opening share")

        # ---- focus the add-people input to reveal the role dropdown -------
        inp = frame.locator('input[role="combobox"][aria-label*="Add people"]').first
        inp.click(force=True)
        page.wait_for_timeout(1200)
        dump_buttons(frame, "buttons after focusing the Add people input")
        page.screenshot(path=os.path.join(OUT, "diag3_input_focus.png"))

        # find a role trigger: a button whose aria mentions the current role
        role_trigger = None
        for el in frame.locator("button").all()[:20]:
            try:
                aria = el.get_attribute("aria-label") or ""
                if "change" in aria.lower() and ("role" in aria.lower() or "permission" in aria.lower()):
                    role_trigger = el
                    print("ROLE TRIGGER:", aria, flush=True)
                    break
            except Exception:
                pass

        if role_trigger is not None:
            role_trigger.click(timeout=5000)
            page.wait_for_timeout(1500)
            page.screenshot(path=os.path.join(OUT, "diag3_role_menu.png"))
            print("\n--- role menu items ---", flush=True)
            for el in frame.locator('[role="menuitem"]').all()[:15]:
                try:
                    print(f"   item: {(el.inner_text() or '').strip()[:50]!r}", flush=True)
                except Exception:
                    pass
            # pick Viewer
            try:
                frame.locator('[role="menuitem"]:has-text("Viewer")').first.click(timeout=5000)
                print("selected Viewer in the role menu", flush=True)
            except Exception as exc:
                print("could not pick Viewer:", exc, flush=True)
            page.wait_for_timeout(1000)
            dump_buttons(frame, "buttons after choosing Viewer")

        # ---- type one address and check the row ---------------------------
        inp.fill(PROBE_MAIL)
        page.wait_for_timeout(1500)
        page.screenshot(path=os.path.join(OUT, "diag3_suggestion.png"))
        page.keyboard.press("Enter")
        page.wait_for_timeout(2500)
        page.screenshot(path=os.path.join(OUT, "diag3_added.png"))
        print("\n--- people list ---", flush=True)
        try:
            for el in frame.locator('[role="menu"]').all()[:3]:
                print("   ", (el.inner_text() or "").strip()[:300].replace("\n", " | "), flush=True)
        except Exception:
            pass
        dump_buttons(frame, "buttons after adding the person")

        print("probe done (nothing sent)", flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(main())
