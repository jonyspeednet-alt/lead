import os
import sys
import tempfile
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from playwright.sync_api import sync_playwright

from drive_report import MAX_EMAILS, PER_FOLDER, RunReport, chunk_emails, parse_emails_from_file

FOLDER_ENTRIES = []
FOLDER_NAMES = []
RUN_LOG_LINES = []
LAST_REPORT = None
LOG_FILE = None

EMAIL_FILE_TYPES = [
    ("Email list files", "*.txt *.csv *.xlsx *.xlsm"),
    ("Text files", "*.txt"),
    ("CSV files", "*.csv"),
    ("Excel files", "*.xlsx *.xlsm"),
    ("All files", "*.*"),
]


def log(msg):
    line = str(msg)
    print(line, flush=True)
    RUN_LOG_LINES.append(line)
    try:
        with open(current_log_path(), "a", encoding="utf-8") as handle:
            handle.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {line}\n")
    except OSError:
        pass


def current_log_path():
    """One log file per run - the path is cached so every line lands in it."""
    global LOG_FILE
    if LOG_FILE:
        return LOG_FILE
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
    folder = os.path.join(base, "logs")
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        folder = tempfile.gettempdir()
    LOG_FILE = os.path.join(folder, f"run_{datetime.now():%Y%m%d_%H%M%S}.log")
    return LOG_FILE


def set_status(var, text):
    """Tkinter variables must be touched on the main thread."""
    try:
        root.after(0, lambda: var.set(text))
    except Exception:
        try:
            var.set(text)
        except Exception:
            pass


MAX_FOLDERS = 200


def rebuild_folders():
    """Rebuild the folder plan (count + names).

    The main window stays compact: the per-folder name fields live in the
    'Rename folders' dialog, so 200 folders still fit in one screen.
    """
    global FOLDER_NAMES
    try:
        n = int(folder_count.get())
    except ValueError:
        n = 1
    n = max(1, min(MAX_FOLDERS, n))
    folder_count.delete(0, "end")
    folder_count.insert(0, str(n))

    while len(FOLDER_NAMES) < n:
        FOLDER_NAMES.append(f"Folder {len(FOLDER_NAMES) + 1}")
    FOLDER_NAMES = FOLDER_NAMES[:n]

    FOLDER_ENTRIES.clear()
    for name in FOLDER_NAMES:
        FOLDER_ENTRIES.append(tk.StringVar(value=name))

    update_plan_preview()
    update_folder_preview()


# --------------------------------------------------------------------------- email list
def choose_email_file():
    path = filedialog.askopenfilename(title="Select office e-mail list", filetypes=EMAIL_FILE_TYPES)
    if not path:
        return
    email_file_path.set(path)
    refresh_email_info()


def refresh_email_info():
    path = email_file_path.get().strip()
    if not path or not os.path.isfile(path):
        email_info.set("No file selected yet.")
        update_plan_preview()
        return
    parsed = parse_emails_from_file(path)
    valid = len(parsed["valid"])
    if valid == 0:
        email_info.set(f"No valid e-mail address found in {os.path.basename(path)}.")
        update_plan_preview()
        return
    text = f"{parsed['found']} address line(s) found - {valid} usable"
    if parsed["invalid"]:
        text += f" - {len(parsed['invalid'])} invalid skipped"
    if parsed["limited"]:
        text += f" - limit {MAX_EMAILS} hit, {len(parsed['dropped'])} kept for the next run"
    email_info.set(text)
    update_plan_preview()


# --------------------------------------------------------------------------- drive helpers
def create_folder(page, name, status):
    """Create one folder in Drive and return its data-id (may be None)."""
    set_status(status, f"Creating folder '{name}'...")
    log(f"creating folder {name}")

    pre_existing_ids = set()
    try:
        existing_elements = page.locator('tr[data-id], [role="row"][data-id]').all()
        for elem in existing_elements:
            did = elem.get_attribute("data-id")
            if did:
                pre_existing_ids.add(did)
    except Exception:
        pass

    page.keyboard.press("Escape")
    page.wait_for_timeout(400)
    page.keyboard.press("Shift+F")
    page.wait_for_timeout(1000)

    if not page.locator('div[role="dialog"] input[type="text"]').is_visible(timeout=2500):
        try:
            page.locator('button[aria-label="New"]').first.click(timeout=3000)
            page.wait_for_timeout(800)
            page.locator('[role="menuitem"]:has-text("New folder")').first.click(timeout=3000)
        except Exception:
            pass

    dialog_input = page.locator('div[role="dialog"] input[type="text"]').last
    dialog_input.wait_for(state="visible", timeout=10000)
    dialog_input.click()
    page.wait_for_timeout(300)
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    page.wait_for_timeout(200)
    dialog_input.press_sequentially(name, delay=40)
    page.wait_for_timeout(500)
    page.keyboard.press("Enter")
    page.wait_for_timeout(3500)

    # 1. selected row
    newly_found_id = None
    try:
        selected_row = page.locator('tr[aria-selected="true"][data-id], [role="row"][aria-selected="true"][data-id]').first
        if selected_row.is_visible(timeout=2000):
            newly_found_id = selected_row.get_attribute("data-id")
            log(f"Captured new folder data-id via aria-selected: {newly_found_id}")
    except Exception:
        pass

    # 2. diff against pre-existing ids
    if not newly_found_id:
        try:
            current_elements = page.locator('tr[data-id], [role="row"][data-id]').all()
            for elem in current_elements:
                cid = elem.get_attribute("data-id")
                if cid and cid not in pre_existing_ids and name in (elem.inner_text() or ""):
                    newly_found_id = cid
                    log(f"Captured new folder data-id via ID diff: {newly_found_id}")
                    break
        except Exception:
            pass

    # 3. toast snackbar
    if not newly_found_id:
        try:
            toast_link = page.locator('div[role="status"] a[href*="folders"], div[role="alert"] a[href*="folders"]').first
            if toast_link.is_visible(timeout=1500):
                href = toast_link.get_attribute("href")
                if "folders/" in href:
                    newly_found_id = href.split("folders/")[-1].split("?")[0].strip()
                    log(f"Captured new folder data-id from toast snackbar: {newly_found_id}")
        except Exception:
            pass

    # 4. first matching row
    if not newly_found_id:
        try:
            matching_rows = page.locator(f'tr[data-id]:has-text("{name}")').all()
            if matching_rows:
                newly_found_id = matching_rows[0].get_attribute("data-id")
                log(f"Captured folder data-id via first matching row: {newly_found_id}")
        except Exception:
            pass

    log(f"created folder: {name} (ID: {newly_found_id})")
    set_status(status, f"Created: {name}")
    return newly_found_id


def enter_folder(page, folder_name, folder_id, status):
    """Open the freshly created folder so files can be uploaded into it."""
    set_status(status, f"Opening folder '{folder_name}'...")
    if folder_id:
        folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
        log(f"Navigating to folder direct URL: {folder_url}")
        page.goto(folder_url, timeout=30000)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(3000)
        log(f"Inside targeted folder. URL: {page.url}")
        return True
    log("Warning: no folder data-id, navigating via keyboard Enter...")
    page.keyboard.press("Enter")
    page.wait_for_timeout(3000)
    return True


def upload_file_into_folder(page, path, folder_name, status):
    """Upload a single file into the folder that is currently open."""
    set_status(status, f"Uploading file into '{folder_name}'...")
    log(f"Uploading {path} inside folder: {page.url}")
    uploaded = False
    try:
        new_btn = page.locator('button[aria-label="New"]').first
        new_btn.wait_for(state="visible", timeout=5000)
        with page.expect_file_chooser(timeout=12000) as fc_info:
            new_btn.click()
            page.wait_for_timeout(900)
            upload_item = page.locator('[role="menu"] [role="menuitem"]').filter(has_text="File upload").first
            upload_item.wait_for(state="visible", timeout=5000)
            upload_item.click()
        fc_info.value.set_files(path)
        uploaded = True
        log("File upload triggered via '+ New > File upload'")
    except Exception as ex1:
        log(f"File upload error: {ex1}")

    if uploaded:
        page.wait_for_timeout(7000)
        set_status(status, f"File uploaded into '{folder_name}'.")
    else:
        set_status(status, "File upload failed - continuing to share...")
    return uploaded


# --------------------------------------------------------------------------- share helpers
def dismiss_error_dialogs(page, frame=None, label=""):
    """Close Google's error popups (Unable to share / Permission denied) and report them.

    The popup is rendered INSIDE the share iframe, so it has to be searched
    there as well - a page level search never finds it.
    """
    scopes = []
    if frame is not None:
        scopes.append(("share dialog", frame))
    scopes.append(("page", page))

    messages = []
    chosen = None
    for scope_name, scope in scopes:
        for phrase in ("Unable to share", "Permission denied",
                       "may violate our Terms of Service"):
            try:
                locator = scope.get_by_text(phrase, exact=False)
                if locator.count() and locator.first.is_visible(timeout=600):
                    messages.append(f"{scope_name}: {phrase}")
                    chosen = scope
                    break
            except Exception:
                continue
        if messages:
            break

    if not messages:
        return messages

    try:
        oks = chosen.locator('button:has-text("OK")')
        for index in range(oks.count() - 1, -1, -1):
            button = oks.nth(index)
            if button.is_visible(timeout=500):
                button.click(timeout=3000)
                page.wait_for_timeout(900)
                break
    except Exception:
        pass

    log(f"{label} - Google blocked the action: {messages[0]}")
    return messages


def share_dialog_open(page):
    return page.locator('iframe[src*="drivesharing/driveshare"]').count() > 0


def close_share_dialog(page):
    """Make sure the share dialog is gone so the next folder is not blocked."""
    for _ in range(8):
        if not share_dialog_open(page):
            return True
        clicked = False
        try:
            frame = page.frame_locator('iframe[src*="drivesharing/driveshare"]')
            for selector in ('button[aria-label="Back"]', 'button:has-text("Done")',
                             'button:has-text("Cancel")'):
                try:
                    loc = frame.locator(selector).first
                    if loc.is_visible(timeout=1200):
                        loc.click(timeout=2500)
                        page.wait_for_timeout(1200)
                        clicked = True
                        break
                except Exception:
                    continue
        except Exception:
            pass
        if not clicked:
            try:
                page.keyboard.press("Escape")
                page.wait_for_timeout(1000)
            except Exception:
                pass
    return not share_dialog_open(page)


def set_general_access(share_frame, page):
    """Switch general access to 'Anyone with the link' (may be blocked by policy)."""
    try:
        # Try multiple selectors for the general access button
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
            return False, "general access control not found"
        
        label = (button.get_attribute("aria-label") or "").lower()
        if "anyone with the link" in label:
            return True, "already set to Anyone with the link"
        
        button.click(timeout=5000)
        page.wait_for_timeout(1500)
        
        # Try multiple selectors for the "Anyone with the link" option
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
        
        if option is None:
            return False, "Anyone with the link option not found"
        
        option.click(timeout=5000)
        page.wait_for_timeout(3000)
        return True, "switched to Anyone with the link"
    except Exception as exc:
        return False, str(exc)


def set_link_permission_viewer(share_frame, page):
    """Make sure the public link permission is 'Viewer' and not 'Editor'."""
    try:
        # Try multiple selectors for the link permission button
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
        
        if button is None:
            return False
        
        current = (button.get_attribute("aria-label") or "").strip()
        if current.lower().startswith("viewer"):
            return True
        
        button.click(timeout=5000)
        page.wait_for_timeout(1200)
        
        # Try multiple selectors for the Viewer option
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
        
        if viewer_option is None:
            log("Viewer option not found in link permission menu")
            return False
        
        viewer_option.click(timeout=5000)
        page.wait_for_timeout(1000)
        log(f"link permission changed to Viewer (was '{current}')")
        return True
    except Exception as exc:
        log(f"could not change the link permission: {exc}")
        return False


def set_recipient_role_viewer(share_frame, page, label=""):
    """Force the role dropdown next to the recipient input to 'Viewer'."""
    try:
        # Try multiple selectors for the recipient role button
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
        
        if button is None:
            return False
        
        current = (button.get_attribute("aria-label") or "").strip()
        if current.lower().startswith("viewer"):
            return True
        
        button.click(timeout=5000)
        page.wait_for_timeout(1200)
        
        # Try multiple selectors for the Viewer option
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
        
        if viewer_option is None:
            log(f"{label} Viewer option not found in recipient role menu")
            return False
        
        viewer_option.click(timeout=5000)
        page.wait_for_timeout(800)
        log(f"{label} recipient role changed to Viewer (was '{current}')")
        return True
    except Exception as exc:
        log(f"{label} could not change the recipient role: {exc}")
        return False


def wait_for_share_result(page, frame=None, timeout_s=60):
    """Wait until the share dialog closes; returns (ok, error_message)."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        page.wait_for_timeout(1500)
        errors = dismiss_error_dialogs(page, frame, "share")
        if errors:
            return False, errors[0]
        if not share_dialog_open(page):
            return True, ""
    return False, "the share dialog stayed open (no confirmation received)"


def share_folder(page, folder_name, folder_id, emails, status):
    """Share the folder: public link (Viewer) + the given e-mail addresses (Viewer)."""
    set_status(status, f"Configuring sharing for '{folder_name}'...")
    log(f"Opening context menu to launch Share dialog for {folder_name}")

    result = {
        "opened": False,
        "general": False,
        "shared": 0,
        "shared_list": [],
        "failed_emails": [],
        "error": "",
        "notes": [],
    }

    try:
        page.goto("https://drive.google.com/drive/my-drive", timeout=30000)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(3000)

        if folder_id:
            folder_row = page.locator(f'tr[data-id="{folder_id}"]').first
        else:
            folder_row = page.locator(f'tr[role="row"]:has-text("{folder_name}")').first

        folder_row.wait_for(state="visible", timeout=8000)
        folder_row.click()
        page.wait_for_timeout(400)
        folder_row.click(button="right")
        page.wait_for_timeout(1200)

        share_trigger = page.locator('[role="menuitem"]').filter(has_text="Share").first
        share_trigger.hover()
        page.wait_for_timeout(1000)

        share_action = page.locator('[aria-label="Share, Ctrl+Alt+A"]').first
        if share_action.is_visible(timeout=4000):
            share_action.click()
            result["opened"] = True
            log("Clicked Share action in context menu")
    except Exception as so_err:
        log(f"Error launching share menu: {so_err}")
        result["error"] = f"share menu: {so_err}"
        return result

    if not result["opened"]:
        result["error"] = "Share dialog could not be opened"
        return result

    try:
        share_frame = page.frame_locator('iframe[src*="drivesharing/driveshare"]')
        page.wait_for_timeout(3500)

        # ---- 0. Turn OFF 'Notify people' to reduce spam triggers ------------
        try:
            notify = share_frame.locator('input[type="checkbox"][aria-label*="Notify"]').first
            if notify.count():
                notify.uncheck(force=True)
                log("unchecked 'Notify people'")
        except Exception as exc:
            log(f"notify toggle: {exc}")

        # ---- 1. general access: anyone with the link (OPTIONAL) ---------------
        # If organization policy blocks this, we'll still try specific people sharing
        ok, message = set_general_access(share_frame, page)
        result["general"] = ok
        if ok:
            log(f"general access: {message}")
        else:
            result["notes"].append(f"general access failed: {message}")
            log(f"general access failed (will try specific people only): {message}")

        blocked = dismiss_error_dialogs(page, share_frame, "general access")
        if blocked:
            result["general"] = False
            result["notes"].append(f"general access blocked: {blocked[0]}")

        # ---- 2. public link permission must be Viewer (only if general worked) -
        if result["general"]:
            set_link_permission_viewer(share_frame, page)

        # ---- 3. add the e-mail addresses ----------------------------------
        if emails:
            log(f"Adding {len(emails)} email(s) to '{folder_name}'")
            added = []
            try:
                email_inp = share_frame.locator(
                    'input[role="combobox"][aria-label*="Add people"]').first
                email_inp.wait_for(state="attached", timeout=8000)
                email_inp.click(force=True)
                page.wait_for_timeout(600)

                for index, em in enumerate(emails, start=1):
                    try:
                        email_inp.fill(em)
                        page.wait_for_timeout(1000)  # Increased delay
                        page.keyboard.press("Enter")
                        page.wait_for_timeout(1200)  # Increased delay for Google to process
                        added.append(em)
                    except Exception as one_err:
                        log(f"Could not add '{em}': {one_err}")
                        result["failed_emails"].append(em)
                    if index % 5 == 0:  # More frequent status updates, smaller batches
                        set_status(status, f"Adding people to '{folder_name}' ({index}/{len(emails)})...")
                        page.wait_for_timeout(2000)  # Extra delay every 5 emails

                # every recipient must end up as Viewer
                set_recipient_role_viewer(share_frame, page, folder_name)

                page.wait_for_timeout(2000)
                send_btn = share_frame.locator('button:has-text("Send")').first
                send_btn.wait_for(state="visible", timeout=8000)
                send_btn.click(timeout=8000)
                log(f"Clicked Send for '{folder_name}' ({len(added)} recipient(s), Viewer)")
            except Exception as ee:
                log(f"Error entering emails: {ee}")
                result["error"] = str(ee)

            ok, error = wait_for_share_result(page, share_frame)
            if ok:
                result["shared"] = len(added)
                result["shared_list"] = list(added)
                log(f"'{folder_name}' shared with {len(added)} recipient(s) as Viewer")
            else:
                result["error"] = error
                result["failed_emails"].extend(added)
                result["shared"] = 0
                log(f"'{folder_name}' share failed: {error}")
        else:
            try:
                done_btn = share_frame.locator('button:has-text("Done")').first
                if done_btn.is_visible(timeout=4000):
                    done_btn.click(timeout=5000)
                    page.wait_for_timeout(1500)
                    log("Clicked Done (no recipients for this folder)")
            except Exception:
                pass
            ok, error = wait_for_share_result(page, share_frame, timeout_s=20)
            if not ok and error:
                result["notes"].append(error)

    except Exception as sfe:
        log(f"Share iframe processing error: {sfe}")
        result["error"] = str(sfe)
    finally:
        dismiss_error_dialogs(page, locals().get("share_frame"), "share")
        close_share_dialog(page)

    return result


# --------------------------------------------------------------------------- main flow
def launch_browser(username, password, status):
    global LAST_REPORT
    try:
        set_status(status, "Opening browser...")
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

            # 1. Login to Google
            set_status(status, "Loading Google login...")
            page.goto("https://accounts.google.com/signin", timeout=30000)
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(2000)

            set_status(status, "Entering email...")
            page.wait_for_selector('input#identifierId, input[name="identifier"], input[type="email"]', timeout=15000)
            email_field = page.locator('input#identifierId, input[name="identifier"], input[type="email"]').first
            email_field.fill(username)
            page.wait_for_timeout(500)

            next_clicked = False
            try:
                next_btn = page.locator('#identifierNext, button:has-text("Next"), div[role="button"]:has-text("Next")').first
                if next_btn.is_visible(timeout=3000):
                    next_btn.click()
                    next_clicked = True
            except Exception:
                pass
            if not next_clicked:
                page.keyboard.press("Enter")

            page.wait_for_timeout(3000)

            set_status(status, "Entering password...")
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
                pw_field.fill(password)
                page.wait_for_timeout(500)
                try:
                    pw_next = page.locator('#passwordNext, button:has-text("Next")').first
                    if pw_next.is_visible(timeout=3000):
                        pw_next.click()
                    else:
                        page.keyboard.press("Enter")
                except Exception:
                    page.keyboard.press("Enter")
            else:
                log("Password field not immediately visible. User might need to solve CAPTCHA or already logged in.")

            set_status(status, "Waiting for login verification...")
            page.wait_for_timeout(6000)

            # 2. Open Google Drive
            set_status(status, "Opening Drive...")
            page.goto("https://drive.google.com/drive/my-drive", timeout=45000)
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(3500)

            names = [e.get().strip() for e in FOLDER_ENTRIES if e.get().strip()]
            emails = CURRENT_EMAILS[:]
            content_file = content_file_path.get().strip()

            report = RunReport(
                source_file=email_file_path.get().strip(),
                planned_folders=len(names),
                parsed=CURRENT_PARSED,
            )
            LAST_REPORT = report

            total_folders = len(names)
            for index, name in enumerate(names):
                chunk = emails[index * PER_FOLDER:(index + 1) * PER_FOLDER]
                set_status(status, f"[{index + 1}/{total_folders}] Creating folder '{name}'")
                log(f"--- folder {index + 1}/{total_folders}: {name} ({len(chunk)} e-mail(s)) ---")

                folder_id = create_folder(page, name, status)

                uploaded = False
                if content_file and os.path.exists(content_file):
                    enter_folder(page, name, folder_id, status)
                    uploaded = upload_file_into_folder(page, content_file, name, status)

                # Always try sharing - don't skip remaining folders if one fails
                share_result = share_folder(page, name, folder_id, chunk, status)

                shared_emails = share_result.get("shared_list") or chunk[:share_result["shared"]]
                for em in shared_emails:
                    report.processed.append((name, em))

                notes = []
                if share_result["failed_emails"]:
                    notes.append(f"{len(share_result['failed_emails'])} e-mail(s) not shared")
                if share_result["error"]:
                    notes.append(share_result["error"])
                for note in share_result.get("notes", []):
                    notes.append(note)
                if uploaded:
                    notes.append("file uploaded")

                if share_result["opened"] and share_result["shared"] == len(chunk):
                    folder_status = "Created + shared"
                elif share_result["opened"]:
                    folder_status = "Created (partial share)"
                else:
                    folder_status = "Created - sharing failed"

                report.add_folder(
                    name=name,
                    assigned=len(chunk),
                    shared=share_result["shared"],
                    status=folder_status,
                    folder_id=folder_id or "",
                    note="; ".join(notes),
                )

            report.finalize()
            LAST_REPORT = report

            summary = f"Done - {report.processed_count} e-mail(s) shared across {total_folders} folder(s)"
            if report.remaining_count:
                summary += f", {report.remaining_count} remaining (see report)"
            set_status(status, summary)
            try:
                set_status(report_info, (
                    f"{report.processed_count} e-mail(s) shared across {total_folders} folder(s) - "
                    f"{report.remaining_count} remaining. Open 'View Report' for the details."
                ))
            except Exception:
                pass
            log(summary)
            for line in report.summary_lines():
                log(line)

            root.after(0, lambda: enable_report_buttons(True))
            page.wait_for_timeout(2000)

            # ---- the browser stays open until the user closes it -------------
            try:
                root.after(0, lambda: btn.config(
                    state="normal", text="🚀 Start Automation (Login & Create)"))
            except Exception:
                pass
            set_status(status, summary + " - Chrome stays open, close it when you are done.")
            log("Automation finished. Waiting for the user to close Chrome...")
            
            # Keep the browser open by waiting in a loop
            # The context manager will keep the browser alive until this block exits
            try:
                while browser.is_connected():
                    page.wait_for_timeout(1000)
            except Exception as e:
                log(f"Browser connection check error: {e}")
            log("Chrome was closed - finishing up.")

    except Exception as e:
        set_status(status, f"Error: {e}")
        log(f"Process error: {e}")
    finally:
        try:
            root.after(0, lambda: btn.config(state="normal", text="🚀 Start Automation (Login & Create)"))
        except Exception:
            pass


def on_submit():
    global CURRENT_EMAILS, CURRENT_PARSED

    u = entry_user.get().strip()
    pw = entry_pass.get()
    if not u or not pw:
        status.set("Please enter both Gmail Username & Password!")
        return

    try:
        planned = int(folder_count.get())
    except ValueError:
        status.set("Total Folders must be a number!")
        return
    if planned < 1:
        status.set("Total Folders must be at least 1!")
        return
    if planned > MAX_FOLDERS:
        status.set(f"Total Folders cannot be more than {MAX_FOLDERS}!")
        return

    path = email_file_path.get().strip()
    if not path or not os.path.isfile(path):
        status.set("Please select the office e-mail list file first!")
        return

    parsed = parse_emails_from_file(path)
    if not parsed["valid"]:
        status.set("No valid e-mail address found in the selected file!")
        return

    CURRENT_PARSED = parsed
    CURRENT_EMAILS = parsed["valid"]

    if parsed["limited"]:
        log(f"Limit {MAX_EMAILS} reached - {len(parsed['dropped'])} address(es) deferred to a later run")

    btn.config(state="disabled", text="⏳ Running Automation...")
    enable_report_buttons(False)
    t = threading.Thread(target=launch_browser, args=(u, pw, status), daemon=False)
    t.start()


# --------------------------------------------------------------------------- report UI
def enable_report_buttons(enabled):
    state = "normal" if enabled else "disabled"
    try:
        view_report_btn.config(state=state)
        export_report_btn.config(state=state)
    except Exception:
        pass


def open_report_window():
    if LAST_REPORT is None:
        messagebox.showinfo("Report", "No run has been completed yet.")
        return

    window = tk.Toplevel(root)
    window.title("Automation Report")
    window.geometry("900x620")
    window.configure(bg="#f3f4f6")

    header = tk.Frame(window, bg="#1e293b", padx=18, pady=14)
    header.pack(fill="x")
    tk.Label(
        header,
        text="Run Report",
        font=("Segoe UI", 14, "bold"),
        fg="#ffffff",
        bg="#1e293b",
    ).pack(anchor="w")
    tk.Label(
        header,
        text=f"Shared {LAST_REPORT.processed_count} e-mail(s) - {LAST_REPORT.remaining_count} remaining",
        font=("Segoe UI", 9),
        fg="#94a3b8",
        bg="#1e293b",
    ).pack(anchor="w")

    summary_box = tk.Frame(window, bg="#ffffff", highlightthickness=1, highlightbackground="#e5e7eb", padx=16, pady=12)
    summary_box.pack(fill="x", padx=18, pady=14)
    for line in LAST_REPORT.summary_lines():
        tk.Label(summary_box, text=line, font=("Segoe UI", 9), bg="#ffffff", fg="#374151", anchor="w").pack(anchor="w")

    table_frame = tk.Frame(window, bg="#ffffff", highlightthickness=1, highlightbackground="#e5e7eb")
    table_frame.pack(fill="both", expand=True, padx=18)

    columns = ("folder", "assigned", "shared", "status", "note")
    tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
    tree.heading("folder", text="Folder")
    tree.heading("assigned", text="Assigned")
    tree.heading("shared", text="Shared")
    tree.heading("status", text="Status")
    tree.heading("note", text="Notes")
    tree.column("folder", width=180)
    tree.column("assigned", width=80, anchor="center")
    tree.column("shared", width=80, anchor="center")
    tree.column("status", width=180)
    tree.column("note", width=300)
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    for row in LAST_REPORT.folder_rows:
        tree.insert("", "end", values=(
            row["name"], row["assigned"], row["shared"], row["status"], row["note"]
        ))

    footer = tk.Frame(window, bg="#f3f4f6", pady=12)
    footer.pack(fill="x")
    tk.Button(
        footer,
        text="Download Excel Report",
        font=("Segoe UI", 10, "bold"),
        bg="#2563eb",
        fg="#ffffff",
        activebackground="#1d4ed8",
        bd=0,
        padx=20,
        pady=7,
        cursor="hand2",
        command=export_report,
    ).pack(side="right", padx=(0, 18))
    tk.Button(
        footer,
        text="Close",
        font=("Segoe UI", 10),
        bg="#e5e7eb",
        fg="#111827",
        bd=0,
        padx=20,
        pady=7,
        cursor="hand2",
        command=window.destroy,
    ).pack(side="right")


def export_report():
    if LAST_REPORT is None:
        messagebox.showinfo("Report", "No run has been completed yet.")
        return

    default_name = f"DriveAutomation_Report_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
    target = filedialog.asksaveasfilename(
        title="Save Excel report",
        defaultextension=".xlsx",
        initialfile=default_name,
        filetypes=[("Excel workbook", "*.xlsx")],
    )
    if not target:
        return
    try:
        LAST_REPORT.write_excel(target)
        log(f"Excel report written: {target}")
        messagebox.showinfo(
            "Report saved",
            f"Report saved to:\n{target}\n\n"
            f"Remaining e-mails: {LAST_REPORT.remaining_count}\n"
            "(sheet 'Remaining Emails' can be uploaded again for the next run)",
        )
    except Exception as exc:
        log(f"Excel export failed: {exc}")
        messagebox.showerror("Export failed", str(exc))


# ----------------- MODERN GUI DESIGN -----------------
BG = "#f3f4f6"
CARD_BG = "#ffffff"
BORDER = "#e5e7eb"
INK = "#111827"
MUTED = "#6b7280"
ACCENT = "#2563eb"

root = tk.Tk()
root.title("Google Drive Automation Studio")
root.configure(bg=BG)

# responsive start size - the whole app fits on screen, no scrollbar
screen_w = root.winfo_screenwidth()
screen_h = root.winfo_screenheight()
max_h = max(640, screen_h - 70)          # never taller than the screen
COMPACT = screen_h < 900 or os.environ.get("DRIVE_COMPACT") == "1"
PAD_X = 12 if COMPACT else 14
PAD_Y = 5 if COMPACT else 10
HEAD_PADY = 5 if COMPACT else 8
ENTRY_PADY = 2 if COMPACT else 4
CARD_GAP = 3 if COMPACT else 5
TITLE_FONT = ("Segoe UI", 13 if COMPACT else 15, "bold")
CARD_FONT = ("Segoe UI", 9 if COMPACT else 10, "bold")
HINT_FONT = ("Segoe UI", 7 if COMPACT else 8, "italic")
BODY_FONT = ("Segoe UI", 8 if COMPACT else 9)
ENTRY_FONT = ("Segoe UI", 9 if COMPACT else 10)

root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(1, weight=1)

try:
    if getattr(sys, "frozen", False):
        root.iconbitmap(sys.executable)
except Exception:
    pass

CURRENT_EMAILS = []
CURRENT_PARSED = {"found": 0, "valid": [], "invalid": [], "dropped": [], "limited": False}
WRAPPABLE = []
pos_x = 0
pos_y = 0


# --------------------------------------------------------------------------- previews
def update_plan_preview():
    """Live summary of how many e-mails the current folder count will use."""
    try:
        n = int(folder_count.get())
    except ValueError:
        n = 0
    valid = CURRENT_PARSED.get("valid", [])
    if n <= 0:
        plan_hint.set(f"Set the number of folders (1-{MAX_FOLDERS}).")
        return
    if not valid:
        plan_hint.set(f"Each folder receives the next {PER_FOLDER} e-mails from the list below.")
        return
    usable = min(n * PER_FOLDER, len(valid))
    left = len(valid) - usable
    dropped = len(CURRENT_PARSED.get("dropped", []))
    if left > 0:
        text = (f"{n} folder(s) x {PER_FOLDER} = {usable:,} e-mail(s) will be shared - "
                f"{left:,} left over for the next run.")
    else:
        text = (f"{n} folder(s) x {PER_FOLDER} = {usable:,} e-mail(s) will be shared - "
                "the whole list is used.")
    if dropped:
        text += f" ({dropped:,} more are over the {MAX_EMAILS} limit - they stay in the report)"
    plan_hint.set(text)


def update_folder_preview():
    count = len(FOLDER_NAMES)
    if count == 0:
        folder_preview.set("")
    elif count <= 3:
        folder_preview.set(", ".join(FOLDER_NAMES))
    else:
        folder_preview.set(
            f"{FOLDER_NAMES[0]} ... {FOLDER_NAMES[-1]}   ({count} folders - use 'Rename folders' to customise)"
        )


def open_rename_dialog():
    """Edit the folder names in a separate window so the main one stays compact."""
    window = tk.Toplevel(root)
    window.title("Rename folders")
    window.geometry("560x460")
    window.configure(bg=BG)
    window.transient(root)
    
    # Center the dialog on the parent window first
    window.update_idletasks()
    x = root.winfo_x() + (root.winfo_width() - window.winfo_width()) // 2
    y = root.winfo_y() + (root.winfo_height() - window.winfo_height()) // 2
    window.geometry(f"+{x}+{y}")
    
    # Now make it modal after it's positioned
    window.grab_set()

    canvas = tk.Canvas(window, bg=BG, highlightthickness=0)
    scrollbar = ttk.Scrollbar(window, orient="vertical", command=canvas.yview)
    inner = tk.Frame(canvas, bg=BG)
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    window_item = canvas.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>", lambda e: canvas.itemconfig(window_item, width=e.width))
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=14)
    scrollbar.pack(side="right", fill="y", padx=(0, 14), pady=14)

    name_vars = [tk.StringVar(value=name) for name in FOLDER_NAMES]
    for index, var in enumerate(name_vars):
        row = tk.Frame(inner, bg=BG)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=f"Folder {index + 1}:", width=10, anchor="w",
                 font=("Segoe UI", 9), bg=BG, fg=MUTED).pack(side="left")
        entry = tk.Entry(row, textvariable=var, font=("Segoe UI", 10), bg=CARD_BG, relief="flat",
                 highlightthickness=1, highlightbackground="#d1d5db")
        entry.pack(side="left", fill="x", expand=True, ipady=3)

    def apply_names():
        global FOLDER_NAMES
        FOLDER_NAMES = [
            var.get().strip() or f"Folder {index + 1}" for index, var in enumerate(name_vars)
        ]
        for entry_var, name in zip(FOLDER_ENTRIES, FOLDER_NAMES):
            entry_var.set(name)
        update_folder_preview()
        window.destroy()

    footer = tk.Frame(window, bg=BG, pady=12)
    footer.pack(fill="x")
    tk.Button(footer, text="Cancel", font=("Segoe UI", 10), bg="#e5e7eb", fg=INK, bd=0,
              padx=20, pady=7, cursor="hand2", command=window.destroy).pack(side="right")
    tk.Button(footer, text="Apply names", font=("Segoe UI", 10, "bold"), bg=ACCENT, fg="#ffffff",
              activebackground="#1d4ed8", bd=0, padx=20, pady=7, cursor="hand2",
              command=apply_names).pack(side="right", padx=(0, 10))


# --------------------------------------------------------------------------- header
header_frame = tk.Frame(root, bg="#1e293b", padx=20, pady=(14 if not COMPACT else 8))
header_frame.grid(row=0, column=0, sticky="ew")

title_lbl = tk.Label(header_frame, text="⚡ Google Drive Automation", font=TITLE_FONT,
                     fg="#ffffff", bg="#1e293b")
title_lbl.pack(anchor="w")
if not COMPACT:
    sub_lbl = tk.Label(header_frame, text="Auto Login, Create Folders, Upload Files & Share with Team",
                        font=("Segoe UI", 9), fg="#94a3b8", bg="#1e293b")
    sub_lbl.pack(anchor="w", pady=(2, 0))

body_frame = tk.Frame(root, bg=BG)
body_frame.grid(row=1, column=0, sticky="nsew", padx=14, pady=(10 if not COMPACT else 6))
body_frame.grid_columnconfigure(0, weight=1)


def create_card(parent, title, hint=""):
    card = tk.Frame(parent, bg=CARD_BG, bd=0, highlightthickness=1, highlightbackground=BORDER)
    card.pack(fill="x", pady=CARD_GAP)

    head = tk.Frame(card, bg=CARD_BG, padx=PAD_X, pady=HEAD_PADY)
    head.pack(fill="x")
    tk.Label(head, text=title, font=CARD_FONT, fg=INK, bg=CARD_BG).pack(side="left")
    if hint:
        tk.Label(head, text=hint, font=HINT_FONT, fg=MUTED, bg=CARD_BG).pack(side="right")

    separator = tk.Frame(card, bg=BORDER, height=1)
    separator.pack(fill="x")

    body = tk.Frame(card, bg=CARD_BG, padx=PAD_X, pady=PAD_Y)
    body.pack(fill="x")
    return body


def section_title(parent, text):
    tk.Label(parent, text=text, font=("Segoe UI", 8, "bold"), bg=CARD_BG,
             fg="#374151").pack(anchor="w", pady=(0, 2))


def section_rule(parent):
    tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", pady=(6, 6))


# --------------------------------------------------------------------------- sections
def build_credentials(parent):
    """Render the credential fields into the given parent (no card wrapper)."""
    global entry_user, entry_pass
    holder = tk.Frame(parent, bg=CARD_BG)
    holder.pack(fill="x")
    c = holder
    c.grid_columnconfigure(1, weight=1)

    tk.Label(c, text="Gmail Address", font=("Segoe UI", 9, "bold"), bg=CARD_BG,
             fg="#374151").grid(row=0, column=0, sticky="w", padx=(0, 10))
    entry_user = tk.Entry(c, font=ENTRY_FONT, bg="#f9fafb", relief="flat", highlightthickness=1,
                          highlightbackground="#d1d5db", highlightcolor=ACCENT)
    entry_user.grid(row=0, column=1, sticky="ew", ipady=ENTRY_PADY)

    tk.Label(c, text="Password", font=("Segoe UI", 9, "bold"), bg=CARD_BG,
             fg="#374151").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(6, 0))
    entry_pass = tk.Entry(c, font=ENTRY_FONT, show="•", bg="#f9fafb", relief="flat",
                          highlightthickness=1, highlightbackground="#d1d5db", highlightcolor=ACCENT)
    entry_pass.grid(row=1, column=1, sticky="ew", ipady=ENTRY_PADY, pady=(6, 0))
    return c


def build_folder_section(parent):
    global folder_count, folder_preview, plan_hint
    folder_row = tk.Frame(parent, bg=CARD_BG)
    folder_row.pack(fill="x")

    left_box = tk.Frame(folder_row, bg=CARD_BG)
    left_box.pack(side="left")
    tk.Label(left_box, text="Total Folders:", font=("Segoe UI", 9, "bold"), bg=CARD_BG,
             fg="#374151").pack(side="left")
    folder_count = tk.Entry(left_box, width=6, font=("Segoe UI", 10), justify="center",
                            bg="#f9fafb", relief="flat", highlightthickness=1,
                            highlightbackground="#d1d5db")
    folder_count.pack(side="left", padx=8, ipady=2)
    folder_count.insert(0, "1")
    set_btn = tk.Button(left_box, text="Set Quantity", font=("Segoe UI", 9, "bold"), bg="#f1f5f9",
                         fg="#0f172a", activebackground="#e2e8f0", bd=0, padx=12, pady=4,
                         cursor="hand2", command=rebuild_folders)
    set_btn.pack(side="left")

    rename_btn = tk.Button(folder_row, text="Rename folders...", font=("Segoe UI", 9, "bold"),
                           bg="#f1f5f9", fg="#0f172a", activebackground="#e2e8f0", bd=0, padx=12,
                           pady=4, cursor="hand2", command=open_rename_dialog)
    rename_btn.pack(side="right")

    folder_preview = tk.StringVar(value="")
    preview_label = tk.Label(parent, textvariable=folder_preview, font=HINT_FONT, bg=CARD_BG,
                             fg=MUTED, anchor="w")
    preview_label.pack(fill="x", pady=(5, 0))
    WRAPPABLE.append(preview_label)

    plan_hint = tk.StringVar(value=f"Each folder receives the next {PER_FOLDER} e-mails from the list below.")
    plan_hint_label = tk.Label(parent, textvariable=plan_hint, font=BODY_FONT, bg=CARD_BG,
                               fg="#0369a1", anchor="w")
    plan_hint_label.pack(fill="x", pady=(2, 0))
    WRAPPABLE.append(plan_hint_label)


def build_file_section(parent):
    global content_file_path
    content_file_path = tk.StringVar()
    file_row = tk.Frame(parent, bg=CARD_BG)
    file_row.pack(fill="x")
    entry_file = tk.Entry(file_row, textvariable=content_file_path, font=BODY_FONT, bg="#f9fafb",
                          relief="flat", highlightthickness=1, highlightbackground="#d1d5db")
    entry_file.pack(side="left", fill="x", expand=True, ipady=ENTRY_PADY)

    def browse_content():
        chosen = filedialog.askopenfilename(title="Select file to upload into every folder")
        if chosen:
            content_file_path.set(chosen)

    browse_btn = tk.Button(file_row, text="Browse...", font=("Segoe UI", 9, "bold"), bg="#0284c7",
                           fg="#ffffff", activebackground="#0369a1", activeforeground="#ffffff",
                           bd=0, padx=14, pady=4, cursor="hand2", command=browse_content)
    browse_btn.pack(side="right", padx=(8, 0))


def build_email_section(parent):
    global email_file_path, email_info
    email_file_path = tk.StringVar()
    email_row = tk.Frame(parent, bg=CARD_BG)
    email_row.pack(fill="x")
    entry_emails_file = tk.Entry(email_row, textvariable=email_file_path, font=BODY_FONT,
                                 bg="#f9fafb", relief="flat", highlightthickness=1,
                                 highlightbackground="#d1d5db", state="readonly")
    entry_emails_file.pack(side="left", fill="x", expand=True, ipady=ENTRY_PADY)

    browse_emails_btn = tk.Button(email_row, text="Browse...", font=("Segoe UI", 9, "bold"),
                                   bg="#0284c7", fg="#ffffff", activebackground="#0369a1",
                                   activeforeground="#ffffff", bd=0, padx=14, pady=4,
                                   cursor="hand2", command=choose_email_file)
    browse_emails_btn.pack(side="right", padx=(8, 0))

    email_info = tk.StringVar(value="No file selected yet.")
    email_info_label = tk.Label(parent, textvariable=email_info, font=BODY_FONT, bg=CARD_BG,
                                fg="#0369a1", anchor="w")
    email_info_label.pack(fill="x", pady=(5, 0))
    WRAPPABLE.append(email_info_label)

    general_row = tk.Frame(parent, bg=CARD_BG)
    general_row.pack(fill="x", pady=(4, 0))
    tk.Label(general_row, text="General Access:", font=("Segoe UI", 9, "bold"), bg=CARD_BG,
             fg="#374151").pack(side="left")
    tk.Label(general_row, text="✓ Anyone with the link can view", font=HINT_FONT,
             bg=CARD_BG, fg="#16a34a").pack(side="left", padx=(8, 0))


def build_report_card(parent):
    global report_info, view_report_btn, export_report_btn
    c = create_card(parent, "📊 Run Report")
    report_info = tk.StringVar(value="Run the automation to generate a report.")
    report_info_label = tk.Label(c, textvariable=report_info, font=BODY_FONT, bg=CARD_BG,
                                 fg=MUTED, anchor="w")
    report_info_label.pack(fill="x", pady=(0, 6))
    WRAPPABLE.append(report_info_label)

    report_row = tk.Frame(c, bg=CARD_BG)
    report_row.pack(fill="x")
    view_report_btn = tk.Button(report_row, text="View Report", font=("Segoe UI", 9, "bold"),
                                 bg="#f1f5f9", fg="#0f172a", activebackground="#e2e8f0", bd=0,
                                 padx=16, pady=5, cursor="hand2", state="disabled",
                                 command=open_report_window)
    view_report_btn.pack(side="left")
    export_report_btn = tk.Button(report_row, text="Download Excel Report",
                                  font=("Segoe UI", 9, "bold"), bg="#0f766e", fg="#ffffff",
                                  activebackground="#115e59", bd=0, padx=16, pady=5,
                                  cursor="hand2", state="disabled", command=export_report)
    export_report_btn.pack(side="left", padx=(10, 0))
    return c


# --------------------------------------------------------------------------- assemble
if COMPACT:
    combined = create_card(body_frame, "⚙ Setup", f"{PER_FOLDER} e-mails per folder")
    section_title(combined, "Google account")
    build_credentials(combined)
    section_rule(combined)
    section_title(combined, "Folder setup")
    build_folder_section(combined)
    section_rule(combined)
    section_title(combined, "File to upload into every folder")
    build_file_section(combined)
    section_rule(combined)
    section_title(combined, "Office e-mail list (.txt / .csv / .xlsx)")
    build_email_section(combined)
else:
    c1 = create_card(body_frame, "🔑 Google Account Credentials")
    build_credentials(c1)

    c2 = create_card(body_frame, "📁 Folder Management")
    build_folder_section(c2)

    c3 = create_card(body_frame, "📤 File Upload (Optional)", "uploaded into every created folder")
    build_file_section(c3)

    c4 = create_card(body_frame, "👥 Office E-mail List (File)", f"{PER_FOLDER} e-mails per folder")
    build_email_section(c4)

build_report_card(body_frame)

# --------------------------------------------------------------------------- action area
action_frame = tk.Frame(root, bg=BG)
action_frame.grid_columnconfigure(0, weight=1)
if COMPACT:
    # on short screens the action bar follows the cards directly, so the
    # Start button stays reachable even if the window is cut off
    action_frame.pack(fill="x", pady=(8, 0), in_=body_frame)
else:
    action_frame.grid(row=2, column=0, sticky="ew", padx=14, pady=(10, 12))

status = tk.StringVar(value="Ready to execute")
status_card = tk.Frame(action_frame, bg="#e0f2fe", highlightthickness=1,
                       highlightbackground="#bae6fd", padx=12, pady=6)
status_card.grid(row=0, column=0, sticky="ew")
tk.Label(status_card, text="Status:", font=("Segoe UI", 9, "bold"), bg="#e0f2fe",
         fg="#0369a1").pack(side="left")
status_label = tk.Label(status_card, textvariable=status, font=("Segoe UI", 9), bg="#e0f2fe",
                        fg="#0c4a6e", justify="left", anchor="w")
status_label.pack(side="left", padx=6, fill="x", expand=True)
WRAPPABLE.append(status_label)

btn = tk.Button(
    action_frame,
    text="🚀 Start Automation (Login & Create)",
    font=("Segoe UI", 11, "bold"),
    bg=ACCENT,
    fg="#ffffff",
    activebackground="#1d4ed8",
    activeforeground="#ffffff",
    bd=0,
    pady=8,
    cursor="hand2",
    command=on_submit,
)
btn.grid(row=1, column=0, sticky="ew", pady=(6, 0))


def copy_status():
    text = status.get()
    text += "\n\nLog file: " + current_log_path()
    if RUN_LOG_LINES:
        text += "\n\n--- LOG ---\n" + "\n".join(RUN_LOG_LINES[-80:])
    root.clipboard_clear()
    root.clipboard_append(text)
    root.update()
    set_status(status, "Status log copied to the clipboard.")


copy_btn = tk.Button(
    action_frame,
    text="📋 Copy Current Status Log",
    font=("Segoe UI", 8),
    bg=BG,
    fg=MUTED,
    activebackground="#e5e7eb",
    bd=0,
    cursor="hand2",
    command=copy_status,
)
copy_btn.grid(row=2, column=0, sticky="e", pady=(3, 0))


# --------------------------------------------------------------------------- responsiveness
def set_wrap(width):
    for label in WRAPPABLE:
        try:
            label.config(wraplength=max(240, width))
        except Exception:
            pass


fitted = {"done": False}


def ensure_fits():
    """Grow the window when the wrapped text needs more room than the client area."""
    try:
        client = root.winfo_height()
        needed = root.winfo_reqheight()
    except Exception:
        return
    if needed > client:
        target = min(needed + 12, max_h)
        if target > client:
            root.geometry(f"{root.winfo_width()}x{target}+{pos_x}+{pos_y}")


def shrink_to_fit():
    """Remove the leftover space once the window is on screen."""
    try:
        client = root.winfo_height()
        needed = root.winfo_reqheight()
    except Exception:
        return
    if needed and client - needed > 40:
        root.geometry(f"{root.winfo_width()}x{needed + 20}+{pos_x}+{pos_y}")


def on_resize(event):
    if event.widget is not root:
        return
    set_wrap(event.width - 90)
    ensure_fits()
    if not fitted["done"] and root.winfo_height() > 1:
        fitted["done"] = True
        root.after(400, shrink_to_fit)


root.bind("<Configure>", on_resize)
folder_count.bind("<Return>", lambda e: rebuild_folders())

# --- auto-fit: the window can never become smaller than the content ---------
win_w = max(620, min(980, screen_w - 120))
set_wrap(win_w - 90)
root.update_idletasks()

req_w = root.winfo_reqwidth()
req_h = root.winfo_reqheight()

win_h = min(max(req_h + 40, 600), max_h)
pos_x = max(0, (screen_w - win_w) // 2)
pos_y = max(0, min(40, (screen_h - win_h) // 3))
root.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
root.update_idletasks()

root.minsize(max(560, req_w), max(600, req_h))

rebuild_folders()
root.update_idletasks()
ensure_fits()
root.mainloop()
