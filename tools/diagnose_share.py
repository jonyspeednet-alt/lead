"""Diagnostic: log in with the real account and dump the Drive share dialog DOM.

Run:  python tools/diagnose_share.py
Output: tools/_verify/diag_share.html + diag_share.json + screenshots
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

EMAIL = "yearj6940@ttdistrict205.net"
PASSWORD = "1090RabbiR5$#@"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_verify")
os.makedirs(OUT, exist_ok=True)

TEST_FOLDER = "ZZZ Share Probe Test"


def dump(name, text):
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    print(f"[saved] {path} ({len(text)} chars)", flush=True)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
        )
        context = browser.new_context(
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = context.new_page()

        # ---------------------------------------------------------- login
        page.goto("https://accounts.google.com/signin", timeout=30000)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2000)

        email_field = page.locator('input#identifierId, input[name="identifier"], input[type="email"]').first
        email_field.wait_for(state="visible", timeout=15000)
        email_field.fill(EMAIL)
        page.wait_for_timeout(500)
        try:
            page.locator('#identifierNext, button:has-text("Next")').first.click(timeout=3000)
        except Exception:
            page.keyboard.press("Enter")
        page.wait_for_timeout(3000)

        pw_field = None
        for sel in ['input[type="password"]:not([aria-hidden="true"])', 'input[name="Passwd"]',
                    'input[type="password"]']:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=5000):
                    pw_field = loc
                    break
            except Exception:
                continue
        if pw_field is None:
            print("NO PASSWORD FIELD - maybe CAPTCHA/2FA", flush=True)
            page.screenshot(path=os.path.join(OUT, "diag_no_password.png"))
            dump("diag_no_password.html", page.content())
            return 2

        pw_field.fill(PASSWORD)
        page.wait_for_timeout(500)
        try:
            page.locator('#passwordNext, button:has-text("Next")').first.click(timeout=3000)
        except Exception:
            page.keyboard.press("Enter")
        page.wait_for_timeout(8000)

        print("after login URL:", page.url, flush=True)
        page.screenshot(path=os.path.join(OUT, "diag_after_login.png"))

        if "accounts.google.com" in page.url:
            print("STILL ON LOGIN - 2FA/CAPTCHA needed", flush=True)
            dump("diag_stuck_login.html", page.content())
            return 3

        # ---------------------------------------------------------- drive
        page.goto("https://drive.google.com/drive/my-drive", timeout=45000)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(4000)
        page.screenshot(path=os.path.join(OUT, "diag_drive.png"))

        # create a probe folder
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
        page.keyboard.press("Shift+F")
        page.wait_for_timeout(1500)
        if not page.locator('div[role="dialog"] input[type="text"]').is_visible(timeout=3000):
            try:
                page.locator('button[aria-label="New"]').first.click(timeout=3000)
                page.wait_for_timeout(800)
                page.locator('[role="menuitem"]:has-text("New folder")').first.click(timeout=3000)
            except Exception as exc:
                print("new folder menu failed:", exc, flush=True)
        dialog_input = page.locator('div[role="dialog"] input[type="text"]').last
        dialog_input.wait_for(state="visible", timeout=10000)
        dialog_input.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        dialog_input.press_sequentially(TEST_FOLDER, delay=30)
        page.wait_for_timeout(400)
        page.keyboard.press("Enter")
        page.wait_for_timeout(4000)
        page.screenshot(path=os.path.join(OUT, "diag_folder_created.png"))

        # find the new row and open the share dialog
        row = page.locator(f'tr[data-id]:has-text("{TEST_FOLDER}")').first
        row.wait_for(state="visible", timeout=10000)
        row.click()
        page.wait_for_timeout(500)
        row.click(button="right")
        page.wait_for_timeout(1200)
        page.screenshot(path=os.path.join(OUT, "diag_context_menu.png"))

        try:
            page.locator('[role="menuitem"]').filter(has_text="Share").first.hover()
            page.wait_for_timeout(1000)
            page.locator('[aria-label="Share, Ctrl+Alt+A"]').first.click(timeout=5000)
        except Exception as exc:
            print("share menu failed:", exc, flush=True)
            page.screenshot(path=os.path.join(OUT, "diag_share_menu_failed.png"))
            return 4

        page.wait_for_timeout(4000)
        page.screenshot(path=os.path.join(OUT, "diag_share_dialog.png"))

        # ---------------------------------------------------------- dump iframe
        frame = page.frame_locator('iframe[src*="drivesharing/driveshare"]')
        try:
            html = frame.locator("body").inner_html(timeout=10000)
        except Exception:
            html = ""
            for iframe in page.frames:
                if "drivesharing" in (iframe.url or ""):
                    html = iframe.content()
                    break
        dump("diag_share.html", html)

        info = {"url": page.url, "iframes": [f.url for f in page.frames]}
        # collect every button / combobox / role-ish control inside the share frame
        for iframe in page.frames:
            if "drivesharing" not in (iframe.url or ""):
                continue
            controls = []
            for sel in ["button", "[role=button]", "[role=combobox]", "[role=listbox]",
                        "[aria-label]", "select", "input"]:
                try:
                    for el in iframe.locator(sel).all()[:80]:
                        try:
                            controls.append({
                                "tag": el.evaluate("e => e.tagName"),
                                "role": el.get_attribute("role"),
                                "aria": el.get_attribute("aria-label"),
                                "text": (el.inner_text() or "").strip()[:80],
                                "title": el.get_attribute("title"),
                            })
                        except Exception:
                            pass
                except Exception:
                    pass
            info["controls"] = controls
            break
        dump("diag_share.json", json.dumps(info, indent=2, ensure_ascii=False))
        print("done", flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(main())
