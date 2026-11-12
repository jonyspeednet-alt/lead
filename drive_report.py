"""Email-list parsing and run reporting for Google Drive Automation Studio.

Responsibilities
----------------
* read an office e-mail list from a .txt / .csv / .xlsx file
* keep at most MAX_EMAILS addresses (the "1k" cap) for a single run
* track what was shared, what is left over and what failed
* export everything as an Excel workbook so the leftover list can be
  downloaded and fed back into the app for a later run
"""

import os
import re
from datetime import datetime

MAX_EMAILS = 1000        # hard cap for one run
PER_FOLDER = 50          # e-mails shared with each created folder

_EMAIL_RE = re.compile(r"^[^@\s,;<>\"']+@[^@\s,;<>\"']+\.[A-Za-z]{2,}$")
_SEPARATORS = re.compile(r"[,;\s]+")


# --------------------------------------------------------------------------- parsing
def _tokens_from_text(text):
    for line in text.splitlines():
        line = line.strip().strip('"').strip("'")
        if not line:
            continue
        for token in _SEPARATORS.split(line):
            token = token.strip().strip('"').strip("'")
            if token:
                yield token


def _tokens_from_xlsx(path):
    from openpyxl import load_workbook

    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        for sheet in workbook.worksheets:
            for row in sheet.iter_rows(values_only=True):
                for cell in row:
                    if cell is None:
                        continue
                    text = str(cell).strip()
                    if not text:
                        continue
                    for token in _SEPARATORS.split(text):
                        token = token.strip().strip('"').strip("'")
                        if token:
                            yield token
    finally:
        workbook.close()


def parse_emails_from_file(path, limit=MAX_EMAILS):
    """Parse an e-mail list file.

    Returns a dict with:
        found     - total address-looking tokens seen in the file
        valid     - unique, valid addresses (already capped to `limit`)
        invalid   - tokens that were not valid addresses
        dropped   - valid addresses beyond the limit (they stay "remaining")
        limited   - True when the file contained more than `limit` addresses
    """
    result = {"found": 0, "valid": [], "invalid": [], "dropped": [], "limited": False}
    if not path or not os.path.isfile(path):
        return result

    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        tokens = list(_tokens_from_xlsx(path))
    else:
        text = ""
        for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                with open(path, "r", encoding=encoding) as handle:
                    text = handle.read()
                break
            except (UnicodeDecodeError, LookupError):
                continue
        tokens = list(_tokens_from_text(text))

    seen = set()
    valid = []
    invalid = []

    for token in tokens:
        result["found"] += 1
        candidate = token.strip()
        if not _EMAIL_RE.match(candidate):
            invalid.append(candidate)
            continue
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        valid.append(candidate)

    result["invalid"] = invalid
    if len(valid) > limit:
        result["limited"] = True
        result["dropped"] = valid[limit:]
        valid = valid[:limit]
    result["valid"] = valid
    return result


def chunk_emails(emails, size=PER_FOLDER):
    """Split the list into per-folder chunks of `size` addresses."""
    return [emails[i:i + size] for i in range(0, len(emails), size)]


# --------------------------------------------------------------------------- report
class RunReport:
    """Collects everything that happened during one automation run."""

    def __init__(self, source_file=None, planned_folders=0, parsed=None):
        self.started_at = datetime.now()
        self.source_file = source_file or ""
        self.planned_folders = planned_folders
        self.parsed = parsed or {"found": 0, "valid": [], "invalid": [], "dropped": [], "limited": False}
        self.folder_rows = []     # per folder outcome
        self.processed = []       # (folder name, email)
        self.remaining = []       # emails that were not shared
        self.errors = []

    # -- recording ---------------------------------------------------------
    def add_folder(self, name, assigned, shared, status, folder_id="", note=""):
        self.folder_rows.append({
            "name": name,
            "assigned": assigned,
            "shared": shared,
            "status": status,
            "folder_id": folder_id or "",
            "note": note,
        })

    def add_error(self, message):
        self.errors.append(message)

    def finalize(self):
        """Compute the leftover list once every folder has been processed."""
        shared_emails = {email.lower() for _, email in self.processed}
        self.remaining = []
        for email in self.parsed.get("valid", []):
            if email.lower() not in shared_emails:
                self.remaining.append(email)
        for email in self.parsed.get("dropped", []):
            if email.lower() not in shared_emails:
                self.remaining.append(email)
        return self.remaining

    # -- reporting ---------------------------------------------------------
    @property
    def processed_count(self):
        return len(self.processed)

    @property
    def remaining_count(self):
        return len(self.remaining)

    def summary_lines(self):
        created = sum(1 for row in self.folder_rows if row["status"].startswith("Created"))
        failed = sum(1 for row in self.folder_rows if "Failed" in row["status"])
        lines = [
            f"Run finished: {self.started_at:%Y-%m-%d %H:%M:%S}",
            f"Source file: {os.path.basename(self.source_file) if self.source_file else '-'}",
            f"Folders created: {created} of {self.planned_folders}" + (f" ({failed} failed)" if failed else ""),
            f"Emails in file: {self.parsed.get('found', 0)} (invalid skipped: {len(self.parsed.get('invalid', []))})",
            f"Emails shared: {self.processed_count}  |  Remaining: {self.remaining_count}",
        ]
        if self.parsed.get("limited"):
            lines.append(
                f"Limit reached: only the first {MAX_EMAILS} addresses were used, "
                f"{len(self.parsed.get('dropped', []))} kept for a later run."
            )
        if self.errors:
            lines.append(f"Errors: {len(self.errors)}")
        return lines

    def write_excel(self, path):
        """Write the full run report as an .xlsx workbook."""
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter

        workbook = Workbook()
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill("solid", fgColor="2563EB")
        title_font = Font(bold=True, size=12)

        def style_header(sheet, row=1):
            for cell in sheet[row]:
                if cell.value is not None:
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = Alignment(horizontal="center")

        def autofit(sheet, widths):
            for index, width in enumerate(widths, start=1):
                sheet.column_dimensions[get_column_letter(index)].width = width

        # --- Summary ---
        summary = workbook.active
        summary.title = "Summary"
        summary["A1"] = "Google Drive Automation Studio - Run Report"
        summary["A1"].font = title_font
        row = 3
        summary.cell(row=row, column=1, value="Field").font = Font(bold=True)
        summary.cell(row=row, column=2, value="Value").font = Font(bold=True)
        for field, value in [
            ("Report generated", self.started_at.strftime("%Y-%m-%d %H:%M:%S")),
            ("Source e-mail file", os.path.basename(self.source_file) if self.source_file else "-"),
            ("Source folder", os.path.dirname(self.source_file) if self.source_file else "-"),
            ("Folders planned", self.planned_folders),
            ("Folders created", sum(1 for r in self.folder_rows if r["status"].startswith("Created"))),
            ("Addresses found in file", self.parsed.get("found", 0)),
            ("Invalid entries skipped", len(self.parsed.get("invalid", []))),
            ("Addresses allowed per run", MAX_EMAILS),
            ("Addresses shared", self.processed_count),
            ("Addresses remaining", self.remaining_count),
            ("Errors", len(self.errors)),
        ]:
            row += 1
            summary.cell(row=row, column=1, value=field)
            summary.cell(row=row, column=2, value=value)
        autofit(summary, [32, 60])

        # --- Folders ---
        folders = workbook.create_sheet("Folders")
        folders.append(["Folder", "Assigned e-mails", "Shared e-mails", "Status", "Folder ID", "Notes"])
        for row_data in self.folder_rows:
            folders.append([
                row_data["name"],
                row_data["assigned"],
                row_data["shared"],
                row_data["status"],
                row_data["folder_id"],
                row_data["note"],
            ])
        style_header(folders)
        autofit(folders, [22, 18, 16, 24, 40, 50])
        folders.freeze_panes = "A2"

        # --- Processed ---
        processed = workbook.create_sheet("Processed Emails")
        processed.append(["Folder", "Email"])
        for folder, email in self.processed:
            processed.append([folder, email])
        style_header(processed)
        autofit(processed, [22, 46])
        processed.freeze_panes = "A2"

        # --- Remaining (can be uploaded again as the input file) ---
        remaining = workbook.create_sheet("Remaining Emails")
        remaining.append(["Email"])
        for email in self.remaining:
            remaining.append([email])
        style_header(remaining)
        autofit(remaining, [46])
        remaining.freeze_panes = "A2"

        # --- Skipped ---
        skipped = workbook.create_sheet("Skipped Invalid")
        skipped.append(["Entry"])
        for entry in self.parsed.get("invalid", []):
            skipped.append([entry])
        style_header(skipped)
        autofit(skipped, [46])

        # --- Errors ---
        if self.errors:
            errors = workbook.create_sheet("Errors")
            errors.append(["Error"])
            for message in self.errors:
                errors.append([message])
            style_header(errors)
            autofit(errors, [90])

        workbook.save(path)
        return path
