"""Functional checks of the new frontend (no browser, no Drive)."""
import os
import sys
import tkinter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

RealTk = tkinter.Tk


class NoLoopTk(RealTk):
    def mainloop(self, *args, **kwargs):
        pass


tkinter.Tk = NoLoopTk

import gmail_drive_login as app  # noqa: E402
from drive_report import parse_emails_from_file  # noqa: E402

sample = os.path.join(ROOT, "tools", "_verify", "emails_1200.txt")
app.root.update_idletasks()

# 1. credentials validation
app.entry_user.delete(0, "end")
app.entry_pass.delete(0, "end")
app.on_submit()
assert app.status.get() == "Please enter both Gmail Username & Password!", app.status.get()
print("OK  empty credentials rejected")

# 2. missing e-mail file
app.entry_user.insert(0, "user@gmail.com")
app.entry_pass.insert(0, "secret")
app.on_submit()
assert app.status.get() == "Please select the office e-mail list file first!", app.status.get()
print("OK  missing e-mail file rejected")

# 3. invalid folder count
app.email_file_path.set(sample)
app.refresh_email_info()
app.folder_count.delete(0, "end")
app.folder_count.insert(0, "0")
app.on_submit()
assert app.status.get() == "Total Folders must be at least 1!", app.status.get()
print("OK  folder count < 1 rejected")

# 4. live plan preview reacts to folder count + parsed list
app.CURRENT_PARSED = parse_emails_from_file(sample)
app.folder_count.delete(0, "end")
app.folder_count.insert(0, "20")
app.rebuild_folders()
assert "20 folder(s) x 50 = 1,000 e-mail(s)" in app.plan_hint.get(), app.plan_hint.get()
assert "200 more are over the 1000 limit" in app.plan_hint.get(), app.plan_hint.get()
print("OK  plan preview:", app.plan_hint.get())

app.folder_count.delete(0, "end")
app.folder_count.insert(0, "5")
app.rebuild_folders()
assert "5 folder(s) x 50 = 250 e-mail(s)" in app.plan_hint.get(), app.plan_hint.get()
assert "750 left over for the next run" in app.plan_hint.get(), app.plan_hint.get()
print("OK  plan preview:", app.plan_hint.get())

# 5. folder names are kept and can be renamed
assert len(app.FOLDER_NAMES) == 5, app.FOLDER_NAMES
app.FOLDER_NAMES[0] = "Batch A"
for entry_var, name in zip(app.FOLDER_ENTRIES, app.FOLDER_NAMES):
    entry_var.set(name)
assert app.FOLDER_ENTRIES[0].get() == "Batch A"
print("OK  folder names:", app.FOLDER_NAMES)

# 6. no scrollbar widget in the main window
def walk(widget):
    found = []
    for child in widget.winfo_children():
        found.append(child)
        found.extend(walk(child))
    return found


scrolls = [w for w in walk(app.root) if w.__class__.__name__ == "Scrollbar"]
assert not scrolls, scrolls
print("OK  no scrollbar in the main window")

# 7. the window can never shrink below the content
app.root.update_idletasks()
assert app.root.winfo_reqheight() <= app.root.wm_minsize()[1] + 1, (
    app.root.winfo_reqheight(), app.root.wm_minsize())
print("OK  min size protects the content:", app.root.wm_minsize())

# 8. log file path is stable (one file per run)
first = app.current_log_path()
assert first == app.current_log_path(), (first, app.current_log_path())
app.log("hello from the test")
assert os.path.isfile(first)
with open(first, encoding="utf-8") as handle:
    assert "hello from the test" in handle.read()
print("OK  single log file:", os.path.basename(first))

# 9. report window opens with a demo report
from drive_report import RunReport  # noqa: E402

report = RunReport(source_file=sample, planned_folders=20, parsed=app.CURRENT_PARSED)
for index in range(20):
    chunk = app.CURRENT_PARSED["valid"][index * 50:(index + 1) * 50]
    report.processed.extend((f"Folder {index + 1}", email) for email in chunk)
    report.add_folder(f"Folder {index + 1}", len(chunk), len(chunk), "Created + shared")
report.finalize()
app.LAST_REPORT = report
app.enable_report_buttons(True)
assert app.view_report_btn["state"] == "normal"
app.open_report_window()
app.root.update()
print("OK  report window opened, shared:", report.processed_count, "remaining:", report.remaining_count)

print("\nALL FRONTEND CHECKS PASSED")
