"""Frozen-build smoke test: verifies the Excel report works in a bundle."""
import os
import tempfile

from drive_report import RunReport, parse_emails_from_file

out = os.path.join(tempfile.gettempdir(), "frozen_selftest.xlsx")
report = RunReport(
    source_file="",
    planned_folders=1,
    parsed={"found": 2, "valid": ["a@b.com"], "invalid": [], "dropped": [], "limited": False},
)
report.processed.append(("Folder 1", "a@b.com"))
report.finalize()
report.write_excel(out)
print("written", out, os.path.getsize(out), flush=True)

from openpyxl import load_workbook

workbook = load_workbook(out)
print("sheets", workbook.sheetnames, flush=True)
print("SELFTEST_OK", flush=True)
