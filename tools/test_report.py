"""Offline checks for the e-mail list parsing and the Excel report."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from drive_report import MAX_EMAILS, PER_FOLDER, RunReport, chunk_emails, parse_emails_from_file

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_verify")
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- fixtures
txt_path = os.path.join(OUT, "emails_1200.txt")
with open(txt_path, "w", encoding="utf-8") as handle:
    for i in range(1200):
        handle.write(f"user{i}@office.com\n")
    handle.write("not-an-email\n")
    handle.write("user5@office.com\n")  # duplicate

csv_path = os.path.join(OUT, "emails_csv.csv")
with open(csv_path, "w", encoding="utf-8") as handle:
    handle.write("a@office.com,b@office.com,c@office.com\n")
    handle.write("d@office.com,e@office.com\n")

xlsx_path = os.path.join(OUT, "emails_xlsx.xlsx")
from openpyxl import Workbook
wb = Workbook()
ws = wb.active
ws.title = "Sheet1"
ws.append(["f@office.com", "g@office.com"])
ws.append(["h@office.com"])
wb.save(xlsx_path)

# ---------------------------------------------------------------- parsing
parsed = parse_emails_from_file(txt_path)
assert parsed["found"] == 1202, parsed["found"]
assert len(parsed["valid"]) == MAX_EMAILS, len(parsed["valid"])
assert parsed["limited"] is True
assert len(parsed["dropped"]) == 200, len(parsed["dropped"])
assert len(parsed["invalid"]) == 1, parsed["invalid"]
print(f"txt   : found={parsed['found']} valid={len(parsed['valid'])} dropped={len(parsed['dropped'])} invalid={len(parsed['invalid'])}")

parsed_csv = parse_emails_from_file(csv_path)
assert len(parsed_csv["valid"]) == 5, parsed_csv["valid"]
print(f"csv   : valid={len(parsed_csv['valid'])} -> {parsed_csv['valid']}")

parsed_xlsx = parse_emails_from_file(xlsx_path)
assert len(parsed_xlsx["valid"]) == 3, parsed_xlsx["valid"]
print(f"xlsx  : valid={len(parsed_xlsx['valid'])} -> {parsed_xlsx['valid']}")

# ---------------------------------------------------------------- chunking
chunks = chunk_emails(parsed["valid"], PER_FOLDER)
assert len(chunks) == 20, len(chunks)
assert all(len(c) == PER_FOLDER for c in chunks)
print(f"chunk : {len(chunks)} chunks x {PER_FOLDER} e-mails")

# ---------------------------------------------------------------- report
report = RunReport(source_file=txt_path, planned_folders=3, parsed=parsed)
for i, name in enumerate(["Folder 1", "Folder 2", "Folder 3"]):
    chunk = chunks[i]
    report.processed.extend((name, email) for email in chunk[:40])  # 10 shared, 10 failed each
    report.add_folder(name, len(chunk), 40, "Created (partial share)", f"fid-{i}", "10 e-mail(s) rejected")
report.add_error("sample error")
report.finalize()

assert report.processed_count == 120, report.processed_count
# leftover = 880 unshared (valid) + 200 beyond the 1k limit
assert report.remaining_count == 1080, report.remaining_count
print(f"report: shared={report.processed_count} remaining={report.remaining_count}")
for line in report.summary_lines():
    print("   ", line)

xlsx_out = os.path.join(OUT, "report_test.xlsx")
report.write_excel(xlsx_out)

check = Workbook()
check = __import__("openpyxl").load_workbook(xlsx_out)
print("sheets:", check.sheetnames)
assert check.sheetnames == ["Summary", "Folders", "Processed Emails", "Remaining Emails", "Skipped Invalid", "Errors"]
assert check["Processed Emails"].max_row == 121
assert check["Remaining Emails"].max_row == 1081  # header + 1080 remaining
assert check["Folders"].max_row == 4
print("excel : written and verified ->", xlsx_out)

# the leftover sheet must be usable as a fresh input file
leftover_path = os.path.join(OUT, "remaining_as_input.xlsx")
wb2 = Workbook()
ws2 = wb2.active
ws2.title = "Emails"
for row in check["Remaining Emails"].iter_rows(min_row=2, values_only=True):
    ws2.append([row[0]])
wb2.save(leftover_path)
reparsed = parse_emails_from_file(leftover_path)
assert len(reparsed["valid"]) == 1000, len(reparsed["valid"])
assert reparsed["limited"] is True
print("roundtrip: leftover file re-parsed ->", len(reparsed["valid"]), "e-mails (80 deferred again)")

print("\nALL CHECKS PASSED")
