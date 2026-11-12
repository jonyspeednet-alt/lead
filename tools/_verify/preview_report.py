"""Preview the new UI + report window without running a real Drive session.

Uses the real application module (no copy of the UI code) and feeds it a
demo report so the report window can be inspected.
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import tkinter

RealTk = tkinter.Tk


class NoLoopTk(RealTk):
    def mainloop(self, *args, **kwargs):
        pass


tkinter.Tk = NoLoopTk

import gmail_drive_login as app  # noqa: E402
from drive_report import PER_FOLDER, RunReport, parse_emails_from_file  # noqa: E402

sample = os.path.join(ROOT, "tools", "_verify", "emails_1200.txt")

app.root.wm_deiconify()
app.root.lift()

# --- show the parsed e-mail file in the new card -----------------------------
app.email_file_path.set(sample)
app.refresh_email_info()

# --- build a demo report ------------------------------------------------------
parsed = parse_emails_from_file(sample)
report = RunReport(source_file=sample, planned_folders=20, parsed=parsed)
emails = parsed["valid"]
for index in range(20):
    name = f"Folder {index + 1}"
    chunk = emails[index * PER_FOLDER:(index + 1) * PER_FOLDER]
    report.processed.extend((name, email) for email in chunk)
    report.add_folder(name, len(chunk), len(chunk), "Created + shared", f"1AbCdEf-{index}", "")
report.finalize()
app.LAST_REPORT = report
app.enable_report_buttons(True)
app.report_info.set(
    f"{report.processed_count} e-mail(s) shared across {report.planned_folders} folder(s), "
    f"{report.remaining_count} remaining."
)

app.root.update()
if "--with-report" in sys.argv:
    app.open_report_window()
    app.root.update()
time.sleep(45)
