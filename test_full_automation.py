"""Full automation test with real credentials and email list."""
import os
import sys
import tempfile
import time

from playwright.sync_api import sync_playwright

# Import the main module functions
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gmail_drive_login as app
from drive_report import parse_emails_from_file

EMAIL = "yearj6940@ttdistrict205.net"
PASSWORD = "1090RabbiR5$#@"
EMAIL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "1 k data.txt")

def test_full_automation():
    """Test the complete automation flow."""
    print("=" * 60)
    print("FULL AUTOMATION TEST")
    print("=" * 60)
    
    # 1. Parse email file
    print("\n1. Parsing email file...")
    parsed = parse_emails_from_file(EMAIL_FILE)
    print(f"   Found: {parsed['found']}, Valid: {len(parsed['valid'])}, Invalid: {len(parsed['invalid'])}")
    if parsed['limited']:
        print(f"   Limited: True, Dropped: {len(parsed['dropped'])}")
    
    # Use first 10 emails for quick test
    test_emails = parsed['valid'][:10]
    print(f"   Testing with {len(test_emails)} emails")
    
    # 2. Run browser automation
    print("\n2. Starting browser automation...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"]
        )
        context = browser.new_context(
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()

        # 3. Login to Google
        print("\n3. Logging into Google...")
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

        pw_selectors = [
            'input[type="password"]:not([aria-hidden="true"])',
            'input[name="Passwd"]',
            'input[name="password"]',
            'input[type="password"]'
        ]
        pw_field = None
        for sel in pw_selectors:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=5000):
                    pw_field = loc
                    break
            except Exception:
                continue

        if pw_field:
            pw_field.fill(PASSWORD)
            page.wait_for_timeout(500)
            try:
                page.locator('#passwordNext, button:has-text("Next")').first.click(timeout=3000)
            except Exception:
                page.keyboard.press("Enter")
        else:
            print("   WARNING: Password field not visible - may need manual intervention")

        page.wait_for_timeout(8000)
        print(f"   After login URL: {page.url}")

        if "accounts.google.com" in page.url:
            print("   STILL ON LOGIN PAGE - 2FA/CAPTCHA may be needed")
            page.screenshot(path=os.path.join(os.path.dirname(__file__), "test_login_stuck.png"))
            return False

        # 4. Open Google Drive
        print("\n4. Opening Google Drive...")
        page.goto("https://drive.google.com/drive/my-drive", timeout=45000)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(4000)
        page.screenshot(path=os.path.join(os.path.dirname(__file__), "test_drive_loaded.png"))

        # 5. Create test folder
        print("\n5. Creating test folder...")
        folder_name = "TEST_FOLDER_" + str(int(time.time()))
        
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
                print(f"   New folder menu failed: {exc}")

        dialog_input = page.locator('div[role="dialog"] input[type="text"]').last
        dialog_input.wait_for(state="visible", timeout=10000)
        dialog_input.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        dialog_input.press_sequentially(folder_name, delay=30)
        page.wait_for_timeout(400)
        page.keyboard.press("Enter")
        page.wait_for_timeout(4000)
        
        page.screenshot(path=os.path.join(os.path.dirname(__file__), f"test_folder_created.png"))
        print(f"   Folder created: {folder_name}")

        # 6. Find folder ID
        print("\n6. Finding folder ID...")
        row = page.locator(f'tr[data-id]:has-text("{folder_name}")').first
        row.wait_for(state="visible", timeout=10000)
        folder_id = row.get_attribute("data-id")
        print(f"   Folder ID: {folder_id}")

        # 7. Open share dialog
        print("\n7. Opening share dialog...")
        row.click()
        page.wait_for_timeout(500)
        row.click(button="right")
        page.wait_for_timeout(1200)
        
        try:
            page.locator('[role="menuitem"]').filter(has_text="Share").first.hover()
            page.wait_for_timeout(1000)
            page.locator('[aria-label="Share, Ctrl+Alt+A"]').first.click(timeout=5000)
        except Exception as exc:
            print(f"   Share menu failed: {exc}")
            page.screenshot(path=os.path.join(os.path.dirname(__file__), "test_share_menu_failed.png"))
            return False

        page.wait_for_timeout(4000)
        page.screenshot(path=os.path.join(os.path.dirname(__file__), "test_share_dialog.png"))

        # 8. Get share frame
        print("\n8. Getting share iframe...")
        share_frame = None
        for f in page.frames:
            if "drivesharing/driveshare" in (f.url or ""):
                share_frame = f
                break
        
        if share_frame is None:
            print("   NO SHARE FRAME FOUND")
            return False
        
        print(f"   Frame URL: {share_frame.url}")

        # 9. Turn OFF 'Notify people'
        print("\n9. Turning off 'Notify people'...")
        try:
            notify = share_frame.locator('input[type="checkbox"][aria-label*="Notify"]').first
            if notify.count():
                notify.uncheck(force=True)
                print("   Unchecked 'Notify people'")
        except Exception as exc:
            print(f"   Notify toggle error: {exc}")

        # 10. Set general access to "Anyone with the link"
        print("\n10. Setting general access to 'Anyone with the link'...")
        try:
            # Find the button
            button = None
            for sel in [
                'button[aria-label*="change general access"]',
                'button[aria-label*="General access"]',
                'button[aria-label*="general access"]',
                '[role="button"][aria-label*="general"]',
            ]:
                try:
                    btn = share_frame.locator(sel).first
                    if btn.is_visible(timeout=3000):
                        button = btn
                        break
                except Exception:
                    continue
            
            if button is None:
                print("   ERROR: General access button not found")
                share_frame.screenshot(path=os.path.join(os.path.dirname(__file__), "test_general_access_btn.png"))
            else:
                label = (button.get_attribute("aria-label") or "").lower()
                print(f"   Current state: {label}")
                if "anyone with the link" not in label:
                    button.click(timeout=5000)
                    page.wait_for_timeout(1500)
                    
                    # Click "Anyone with the link" option
                    option = None
                    for sel in [
                        'span:has-text("Anyone with the link")',
                        '[role="menuitem"]:has-text("Anyone with the link")',
                        '[role="option"]:has-text("Anyone with the link")',
                        'li:has-text("Anyone with the link")',
                    ]:
                        try:
                            opt = share_frame.locator(sel).last
                            if opt.is_visible(timeout=3000):
                                option = opt
                                break
                        except Exception:
                            continue
                    
                    if option:
                        option.click(timeout=5000)
                        page.wait_for_timeout(3000)
                        print("   Set to 'Anyone with the link'")
                    else:
                        print("   ERROR: 'Anyone with the link' option not found")
                else:
                    print("   Already set to 'Anyone with the link'")
        except Exception as exc:
            print(f"   General access error: {exc}")

        # Check for error dialogs
        print("\n10b. Checking for error dialogs...")
        for phrase in ("Unable to share", "Permission denied", "may violate our Terms of Service"):
            try:
                loc = page.get_by_text(phrase, exact=False)
                if loc.count() and loc.first.is_visible(timeout=500):
                    print(f"   ERROR DIALOG: {phrase}")
                    # Dismiss
                    try:
                        page.locator('button:has-text("OK")').first.click(timeout=3000)
                        page.wait_for_timeout(1000)
                    except:
                        pass
            except Exception:
                pass

        # 11. Set link permission to Viewer
        print("\n11. Setting link permission to Viewer...")
        try:
            button = None
            for sel in [
                'button[aria-label*="change link permission"]',
                'button[aria-label*="link permission"]',
                'button[aria-label*="Link permission"]',
                '[role="button"][aria-label*="link"]',
            ]:
                try:
                    btn = share_frame.locator(sel).first
                    if btn.is_visible(timeout=3000):
                        button = btn
                        break
                except Exception:
                    continue
            
            if button:
                current = (button.get_attribute("aria-label") or "").strip()
                print(f"   Current link permission: {current}")
                if not current.lower().startswith("viewer"):
                    button.click(timeout=5000)
                    page.wait_for_timeout(1200)
                    
                    viewer_option = None
                    for sel in [
                        '[role="menuitem"]:has-text("Viewer")',
                        '[role="option"]:has-text("Viewer")',
                        'span:has-text("Viewer")',
                    ]:
                        try:
                            opt = share_frame.locator(sel).first
                            if opt.is_visible(timeout=3000):
                                viewer_option = opt
                                break
                        except Exception:
                            continue
                    
                    if viewer_option:
                        viewer_option.click(timeout=5000)
                        page.wait_for_timeout(1000)
                        print("   Set link permission to Viewer")
                    else:
                        print("   ERROR: Viewer option not found")
                else:
                    print("   Already Viewer")
            else:
                print("   ERROR: Link permission button not found")
        except Exception as exc:
            print(f"   Link permission error: {exc}")

        # 12. Add test emails
        print("\n12. Adding test emails...")
        added = []
        try:
            email_inp = share_frame.locator('input[role="combobox"][aria-label*="Add people"]').first
            email_inp.wait_for(state="attached", timeout=8000)
            email_inp.click(force=True)
            page.wait_for_timeout(600)

            for index, em in enumerate(test_emails, start=1):
                try:
                    email_inp.fill(em)
                    page.wait_for_timeout(700)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(800)
                    added.append(em)
                    print(f"   Added: {em}")
                except Exception as one_err:
                    print(f"   Could not add '{em}': {one_err}")
                
                if index % 5 == 0:
                    page.wait_for_timeout(1000)

            # Set recipient role to Viewer
            print("\n13. Setting recipient role to Viewer...")
            button = None
            for sel in [
                'button[aria-label*="change permission"]',
                'button[aria-label*="change role"]',
                'button[aria-label*="Editor"]',
                'button[aria-label*="Viewer"]',
                '[role="button"][aria-label*="permission"]',
            ]:
                try:
                    btn = share_frame.locator(sel).first
                    if btn.is_visible(timeout=3000):
                        button = btn
                        break
                except Exception:
                    continue
            
            if button:
                current = (button.get_attribute("aria-label") or "").strip()
                print(f"   Current recipient role: {current}")
                if not current.lower().startswith("viewer"):
                    button.click(timeout=5000)
                    page.wait_for_timeout(1200)
                    
                    viewer_option = None
                    for sel in [
                        '[role="menuitem"]:has-text("Viewer")',
                        '[role="option"]:has-text("Viewer")',
                        'span:has-text("Viewer")',
                    ]:
                        try:
                            opt = share_frame.locator(sel).first
                            if opt.is_visible(timeout=3000):
                                viewer_option = opt
                                break
                        except Exception:
                            continue
                    
                    if viewer_option:
                        viewer_option.click(timeout=5000)
                        page.wait_for_timeout(800)
                        print("   Set recipient role to Viewer")
                    else:
                        print("   ERROR: Viewer option not found")
                else:
                    print("   Already Viewer")
            else:
                print("   ERROR: Recipient role button not found")
        except Exception as exc:
            print(f"   Email adding error: {exc}")

        # 14. Click Send
        print("\n14. Clicking Send...")
        try:
            send_btn = share_frame.locator('button:has-text("Send")').first
            send_btn.wait_for(state="visible", timeout=8000)
            send_btn.click(timeout=8000)
            print("   Send clicked")
        except Exception as exc:
            print(f"   Send failed: {exc}")

        # 15. Wait for result
        print("\n15. Waiting for share result...")
        deadline = time.time() + 60
        outcome = "timeout"
        while time.time() < deadline:
            page.wait_for_timeout(3000)
            
            # Check for errors
            error_found = False
            for phrase in ("Unable to share", "Permission denied", "may violate our Terms of Service"):
                try:
                    loc = page.get_by_text(phrase, exact=False)
                    if loc.count() and loc.first.is_visible(timeout=500):
                        outcome = f"ERROR: {phrase}"
                        print(f"   {outcome}")
                        error_found = True
                        break
                except Exception:
                    continue
            
            if error_found:
                break
            
            # Check if dialog closed
            if not page.locator('iframe[src*="drivesharing/driveshare"]').count():
                outcome = "dialog closed (success?)"
                print(f"   {outcome}")
                break

        page.screenshot(path=os.path.join(os.path.dirname(__file__), "test_after_send.png"))
        
        # Dismiss any remaining dialogs
        try:
            page.locator('button:has-text("OK")').first.click(timeout=3000)
            page.wait_for_timeout(1000)
        except:
            pass
        page.keyboard.press("Escape")
        page.wait_for_timeout(2000)

        # 16. Verify by reopening share dialog
        print("\n16. Verifying permissions by reopening share dialog...")
        try:
            page.goto("https://drive.google.com/drive/my-drive", timeout=30000)
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(3000)
            
            row = page.locator(f'tr[data-id]:has-text("{folder_name}")').first
            row.wait_for(state="visible", timeout=10000)
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
                    print("\n   --- Current permissions state ---")
                    # Check general access
                    try:
                        gen_btn = f.locator('button[aria-label*="change general access"]').first
                        if gen_btn.is_visible(timeout=2000):
                            print(f"   General access: {gen_btn.get_attribute('aria-label')}")
                    except:
                        pass
                    
                    # Check link permission
                    try:
                        link_btn = f.locator('button[aria-label*="change link permission"]').first
                        if link_btn.is_visible(timeout=2000):
                            print(f"   Link permission: {link_btn.get_attribute('aria-label')}")
                    except:
                        pass
                    
                    # Check recipient roles
                    try:
                        for el in f.locator('button[aria-label*="change permission"]').all()[:5]:
                            print(f"   Recipient role: {el.get_attribute('aria-label')}")
                    except:
                        pass
                    
                    # Check people list
                    try:
                        for el in f.locator('[role="menu"]').all()[:4]:
                            txt = (el.inner_text() or "").strip()
                            if txt:
                                print(f"   People: {txt[:200].replace(chr(10), ' | ')}")
                    except:
                        pass
                    
                    page.screenshot(path=os.path.join(os.path.dirname(__file__), "test_verification.png"))
                    break
        except Exception as exc:
            print(f"   Verification failed: {exc}")

        print("\n" + "=" * 60)
        print(f"TEST OUTCOME: {outcome}")
        print(f"Emails added: {len(added)}")
        print("=" * 60)
        
        # Keep browser open for manual inspection
        print("\nBrowser will stay open for 30 seconds for manual inspection...")
        page.wait_for_timeout(30000)
        
        return outcome != "timeout" and "ERROR" not in outcome


if __name__ == "__main__":
    success = test_full_automation()
    sys.exit(0 if success else 1)