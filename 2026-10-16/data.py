# %%
# Libraries
# =========
import json
import os
import re
import sys
from datetime import datetime
 
import numpy as np
import pandas as pd
 
pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
pd.set_option("display.max_colwidth", 90)
pd.set_option("display.width", 220)
 
 
# %%
# Load the JSON file into a DataFrame
# ===================================
file_path = input("Enter the JSON file path: ").strip().strip('"').strip("'")
 
try:
    df = pd.read_json(file_path, dtype=False, convert_dates=False)
    load_ok = True
    print("\n✅ SUCCESS: File loaded successfully.")
except Exception as e:
    df = None
    load_ok = False
    print("\n❌ FAIL: Unable to load the JSON file.")
    print(f"Reason: {e}")
 
 

# %%
# Save all QA outputs to a report file
# ====================================
report_path = os.path.join(os.path.dirname(os.path.abspath(file_path)), "QA_Report.txt")
 
 
class Tee:
    _is_qa_tee = True
 
    def __init__(self, *streams):
        self.streams = streams
 
    def write(self, text):
        for stream in self.streams:
            stream.write(text)
            stream.flush()
        return len(text)
 
    def flush(self):
        for stream in self.streams:
            stream.flush()
 
    def isatty(self):
        return False
 
    @property
    def encoding(self):
        return "utf-8"
 
 
if getattr(sys.stdout, "_is_qa_tee", False):
    sys.stdout = sys.stdout.streams[0]
 
original_stdout = sys.stdout
report_file = open(report_path, "w", encoding="utf-8", buffering=1)
qa_tee = Tee(original_stdout, report_file)
sys.stdout = qa_tee
 
RESULTS = []
 
print("=" * 70)
print("QA REPORT")
print("=" * 70)
print("Started  :", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
print("Data file:", os.path.abspath(file_path))
print("Report   :", report_path)
print("File load:", "✅ SUCCESS" if load_ok else "❌ FAIL")
 
 

# %%
# Input functions
# ===============
def ask(question):
    sys.stdout = original_stdout
    try:
        return input(question).strip()
    finally:
        sys.stdout = qa_tee


def ask_text(label, requirement):
    answer = ask(f"Enter the {label} (press Enter to keep '{requirement}'): ")
    value = answer.strip("'\"") or requirement
    print(f"Requirement - {label}: {value}")
    return value


def ask_number(label, requirement):
    while True:
        answer = ask(f"Enter the {label} (press Enter to keep {requirement}): ")
        if not answer:
            value = requirement
            break
        if answer.isdigit():
            value = int(answer)
            break
        print("Please enter a whole number.", file=original_stdout)
    print(f"Requirement - {label}: {value}")
    return value


def ask_list(label, requirement, show=True):
    answer = ask(f"Enter the {label}, comma separated (press Enter to keep the requirement): ")
    if answer:
        items = [x.strip().strip("'\"[] ") for x in answer.split(",")]
        value = list(dict.fromkeys(x for x in items if x))
    else:
        value = list(requirement)
    if show:
        print(f"Requirement - {label}: {', '.join(value)}")
    return value
 
# %%
# Helper functions
# ================
def is_empty(value):
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (dict, list, tuple, set)):
        return len(value) == 0
    try:
        result = pd.isna(value)
        if np.isscalar(result):
            return bool(result)
    except (TypeError, ValueError):
        pass
    return False
 
 
def type_name(value):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "null"
    return {dict: "dict", list: "list", str: "text", bool: "true/false",
            int: "number", float: "number"}.get(type(value), type(value).__name__)
 
 
def get_value(record, path):
    value = record
    for key in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value
 
 
def iter_strings(value, path):
    if isinstance(value, dict):
        for key, val in value.items():
            yield from iter_strings(val, f"{path}.{key}")
    elif isinstance(value, list):
        for i, val in enumerate(value):
            yield from iter_strings(val, f"{path}[{i}]")
    elif isinstance(value, str):
        yield path, value
 
 
def header(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)
 
 
def show_result(check, issues, success_msg="No issues found.", part=None):
    name = f"{check} - {part}" if part else check
    if part:
        print(f"\n▶ {part}")
    if not issues:
        print(f"✅ SUCCESS: {success_msg}")
        RESULTS.append((name, "PASS", 0))
        return
    shown = issues[:SAMPLE_LIMIT]
    print(f"❌ FAIL: {len(issues)} issue(s) found. Showing {len(shown)}:")
    print(pd.DataFrame(shown).to_string(index=False))
    RESULTS.append((name, "FAIL", len(issues)))
 
 
def show_skipped(check, reason, part=None):
    name = f"{check} - {part}" if part else check
    if part:
        print(f"\n▶ {part}")
    print(f"⚠️ SKIPPED: {reason}")
    RESULTS.append((name, "SKIPPED", 0))
 
 
# %%
# General settings
# ================
SAMPLE_LIMIT = 5
 
# %%
# 1. Check file name
# ==================
CHECK = "1. File name"
header(CHECK)
required_file_name = ask("Enter the required file name (press Enter to keep 'data.json'): ") or "data.json"

actual_file_name = os.path.basename(file_path)

if actual_file_name == required_file_name:
    print(f"✅ SUCCESS: File name is '{actual_file_name}'.")
    RESULTS.append((CHECK, "PASS", 0))
else:
    print("❌ FAIL: File name mismatch:")
    print(f" Expected '{required_file_name}',")
    print(f" found '{actual_file_name}'")
    RESULTS.append((CHECK, "FAIL", 1))
# %%
# 2. Check file format is a JSON array
# ====================================
CHECK = "2. File format (JSON array)"
header(CHECK)
 
data = None
issues = []
try:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        issues.append({"field": "whole file",
                       "issue": f"Must be a JSON array, found {type_name(data)}"})
    elif not all(isinstance(r, dict) for r in data):
        issues.append({"field": "whole file",
                       "issue": "Every item in the array must be an object {...}"})
except json.JSONDecodeError as e:
    issues.append({"field": "whole file",
                   "issue": f"Invalid JSON at line {e.lineno}, column {e.colno}: {e.msg}"})
except Exception as e:
    issues.append({"field": "whole file", "issue": f"Cannot read file: {e}"})
 
show_result(CHECK, issues, "Valid JSON array.")
 
if issues or not load_ok:
    print("\n❌ QA STOPPED: Fix the file format and run again.")
    sys.stdout = original_stdout
    report_file.close()
    raise SystemExit("QA stopped - invalid JSON file.")
 
records = data
df = df.reset_index(drop=True)
 
 
def clean_pn(value):
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()
 
 
PN = [None if is_empty(r.get("project_number")) else clean_pn(r.get("project_number"))
      for r in records]
LABEL = [pn if pn else f"Row {i + 1} (no project_number)" for i, pn in enumerate(PN)]
 
 
# %%
# 3. Check data count
# ===================
CHECK = "3. Data count"
header(CHECK)

while True:
    answer = ask("Enter the required data count (press Enter to keep 3008): ").replace(",", "")
    if not answer:
        required_count = 3008
        break
    if answer.isdigit():
        required_count = int(answer)
        break
    print("Please enter a whole number.", file=original_stdout)

actual_count = len(records)

if actual_count == required_count:
    print(f"✅ SUCCESS: Data count is {actual_count}.")
    RESULTS.append((CHECK, "PASS", 0))
else:
    print("❌ FAIL: Data count mismatch")
    print(f" Expected count: {required_count}")
    print(f" Actual count  : {actual_count}")
    RESULTS.append((CHECK, "FAIL", 1))
 
# %%
# 4. Check fields and field order
# ===============================
CHECK = "4. Fields and field order"
header(CHECK)
required_fields = ask_list("required fields in order", [
    "input_project_number", "project_number", "developer_details",
    "escrow_account", "inspection_details", "management_companies",
    "project_name_en", "project_name_ar", "project_worth",
    "building_detail", "main_developer", "project_rooms",
    "project_sizing", "buildings", "lands", "project_dates",
    "total_units", "total_area", "project_status", "project_status_ar",
    "project_primarymedia_id", "primary_media", "facilities",
    "project_is_followed", "project_ar_file_url", "location_details",
    "completion_ratio",
], show=False)

required_set = set(required_fields)
data_fields = list(dict.fromkeys(k for r in records for k in r))

missing = [f for f in required_fields if f not in data_fields]
extra = [f for f in data_fields if f not in required_set]
order_ok = all([k for k in r if k in required_set] == [f for f in required_fields if f in r]
               for r in records)

print(f"Required fields: {len(required_fields)}")
print(f"Fields in data : {len(data_fields)}")

if not missing and not extra:
    print("✅ PASS: Field names and count match.")
else:
    print(f"❌ FAIL: Field names do not match "
          f"(missing: {len(missing)}, extra: {len(extra)}).")
    if missing:
        print(f"   Missing: {', '.join(missing)}")
    if extra:
        print(f"   Extra  : {', '.join(extra)}")

print("✅ PASS: Field order matches." if order_ok else "❌ FAIL: Field order does not match.")


# %%
# 5. Check completely empty fields
# ================================
CHECK = "5. Completely empty fields"
header(CHECK)

empty_mask = {col: df[col].map(is_empty) for col in required_fields if col in df.columns}
empty_fields = [col for col, mask in empty_mask.items() if mask.all()]

if empty_fields:
    print("❌ FAIL: Completely empty field found:")
    for col in empty_fields:
        print(f"   {col}")
    RESULTS.append((CHECK, "FAIL", len(empty_fields)))
else:
    print("✅ SUCCESS: No completely empty field.")
    RESULTS.append((CHECK, "PASS", 0))
 
# %%
# 6. Check missing / empty count per field
# ========================================
CHECK = "6. Missing / empty count"
header(CHECK)

empty_counts = pd.DataFrame(
    [{"field": col, "empty_count": int(mask.sum())}
     for col, mask in empty_mask.items() if mask.any() and not mask.all()]
)

if empty_counts.empty:
    print("✅ SUCCESS: No partly empty fields.")
    RESULTS.append((CHECK, "PASS", 0))
else:
    print("ℹ️ INFO: Fields with some empty values :")
    print(empty_counts.to_string(index=False))
    RESULTS.append((CHECK, "INFO", int(empty_counts["empty_count"].sum())))
# %%
# 7. Check project_number is unique and not empty
# ===============================================
CHECK = "7. project_number unique and not empty"
header(CHECK)
 
issues = [{"project_number": LABEL[i], "field": "project_number", "issue": "Empty / missing"}
          for i, pn in enumerate(PN) if pn is None]
 
counts = pd.Series([pn for pn in PN if pn is not None]).value_counts()
issues += [{"project_number": pn, "field": "project_number", "issue": f"Duplicate ({n} records)"}
           for pn, n in counts[counts > 1].items()]
 
show_result(CHECK, issues, "All project numbers are unique and filled.")
 
 
# %%
# 8. Check extra spaces, new lines and hidden characters
# ======================================================
CHECK = "8. Extra spaces / new lines / hidden characters"
header(CHECK)
whitespace_fields = ask_list("fields to check for extra spaces and new lines", [
    "developer_details", "escrow_account", "inspection_details",
    "management_companies", "input_project_number",
    "project_name_en", "project_name_ar",
])
 
 
def text_problems(text):
    problems = []
    if text != text.strip():
        problems.append("Space at start/end")
    if "  " in text:
        problems.append("Double space")
    if "\n" in text or "\r" in text:
        problems.append("New line")
    if "\t" in text:
        problems.append("Tab")
    if any((ch.isspace() and ch not in " \n\r\t") or (not ch.isprintable() and not ch.isspace())
           for ch in text):
        problems.append("Hidden character")
    return problems
 
 
for field in whitespace_fields:
    if field not in df.columns:
        show_skipped(CHECK, "Field not in data.", part=field)
        continue
    issues = []
    for i, record in enumerate(records):
        for path, text in iter_strings(record.get(field), field):
            problems = text_problems(text)
            if problems:
                issues.append({"project_number": LABEL[i], "field": path,
                               "issue": ", ".join(problems)})
    show_result(CHECK, issues, part=field)
 
 
# %%
# 9. Check list fields (empty must be [])
# =======================================
CHECK = "9. List fields"
header(CHECK)
list_fields = ask_list("fields that must be a list", [
    "inspection_details", "building_detail", "buildings", "lands",
    "project_rooms", "project_sizing", "facilities",
])
 
for field in list_fields:
    if field not in df.columns:
        show_result(CHECK, [{"field": field, "issue": "Field not in data"}], part=field)
        continue
    issues = []
    for i, record in enumerate(records):
        value = record.get(field)
        if isinstance(value, list):
            continue
        if is_empty(value):
            issue = f"Empty value must be [] (found {type_name(value)})"
        else:
            issue = f"Must be a list (found {type_name(value)})"
        issues.append({"project_number": LABEL[i], "field": field, "issue": issue})
    show_result(CHECK, issues, "All values are lists.", part=field)
 
 
# %%
# 10. Check dict fields
# =====================
CHECK = "10. Dict fields"
header(CHECK)
dict_fields = ask_list("fields that must be a dict", ["developer_details", "escrow_account"])
 
for field in dict_fields:
    if field not in df.columns:
        show_result(CHECK, [{"field": field, "issue": "Field not in data"}], part=field)
        continue
    issues = [{"project_number": LABEL[i], "field": field,
               "issue": f"Must be a dict (found {type_name(r.get(field))})"}
              for i, r in enumerate(records) if not isinstance(r.get(field), dict)]
    show_result(CHECK, issues, "All values are dicts.", part=field)
 
 
# %%
# 11. Check Arabic-language fields
# ================================
CHECK = "11. Arabic-language fields"
header(CHECK)
arabic_fields = ask_list("Arabic-language fields (use parent.key for nested fields)",
                         ["project_name_ar", "project_status_ar"])

arabic_pattern = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")

for field in arabic_fields:
    if field.split(".")[0] not in df.columns:
        show_skipped(CHECK, "Field not in data.", part=field)
        continue
    issues = []
    for i, record in enumerate(records):
        value = get_value(record, field)
        if is_empty(value):
            continue
        if not (isinstance(value, str) and arabic_pattern.search(value)):
            issues.append({"project_number": LABEL[i], "value": str(value).strip()})
    show_result(CHECK, issues, "All filled values contain Arabic text.", part=field)
 
# %%
# 12. Check primary_media is a dict with required keys
# ====================================================
CHECK = "12. primary_media"
header(CHECK)
primary_media_keys = ask_list("primary_media required keys",
                              ["type", "url", "thumbnail", "description", "file_name"])
 
if "primary_media" not in df.columns:
    show_skipped(CHECK, "Field not in data.")
else:
    issues = []
    empty_count = 0
    for i, record in enumerate(records):
        value = record.get("primary_media")
        if isinstance(value, dict) and not value:
            empty_count += 1
            continue
        if not isinstance(value, dict):
            issues.append({"project_number": LABEL[i], "field": "primary_media",
                           "issue": f"Must be a dict (found {type_name(value)})"})
            continue
        missing = [k for k in primary_media_keys if k not in value]
        if missing:
            issues.append({"project_number": LABEL[i], "field": "primary_media",
                           "issue": f"Missing keys: {', '.join(missing)}"})
    print(f"ℹ️ INFO: Empty primary_media {{}} records: {empty_count}")
    show_result(CHECK, issues, "All filled primary_media values have the required keys.")
 
 
# %%
# 13. Check inspection_images keys
# ================================
CHECK = "13. inspection_images keys"
header(CHECK)
image_keys = ask_list("inspection_images required keys",
                      ["id", "type", "thumbnail", "description", "file_name"])
allowed_extra_keys = ["image_url"]

if "inspection_details" not in df.columns:
    show_skipped(CHECK, "Field not in data.")
else:
    image_key_set = set(image_keys) | set(allowed_extra_keys)
    issues = []
    for i, record in enumerate(records):
        details = record.get("inspection_details")
        if not isinstance(details, list):
            continue
        for d, inspection in enumerate(details):
            field = f"inspection_details[{d}]"
            if not isinstance(inspection, dict):
                issues.append({"project_number": LABEL[i], "field": field,
                               "issue": "Must be a dict"})
                continue
            images = inspection.get("inspection_images", [])
            if not isinstance(images, list):
                issues.append({"project_number": LABEL[i], "field": f"{field}.inspection_images",
                               "issue": "Must be a list"})
                continue
            for m, image in enumerate(images):
                img_field = f"{field}.inspection_images[{m}]"
                if not isinstance(image, dict):
                    issues.append({"project_number": LABEL[i], "field": img_field,
                                   "issue": "Must be a dict"})
                    continue
                missing = [k for k in image_keys if k not in image]
                extra = [k for k in image if k not in image_key_set]
                if missing:
                    issues.append({"project_number": LABEL[i], "field": img_field,
                                   "issue": f"Missing keys: {', '.join(missing)}"})
                if extra:
                    issues.append({"project_number": LABEL[i], "field": img_field,
                                   "issue": f"Extra keys: {', '.join(extra)}"})
    show_result(CHECK, issues, "All inspection images have the required keys.")
 

# %%
# 14. Check file_name format (primary_media and inspection_images)
# ================================================================
CHECK = "14. file_name format"
header(CHECK)
file_name_format = ask_text(
    "file_name format",
    "s3://pf-datahut-data-prod-ap/datahut/dld/projects/YYYY_MM_DD/dld_number/images/"
    "{project_number}_{order}.{image_extension}",
)

valid_image_extensions = {"png", "jpg", "jpeg", "webp", "gif", "bmp", "tif", "tiff",
                          "avif", "heic", "heif", "svg", "ico"}

file_name_pattern = re.escape(file_name_format)
for token, regex in {"YYYY_MM_DD": r"\d{4}_\d{2}_\d{2}",
                     "{project_number}": r"(?P<pn>[^/]+?)",
                     "{order}": r"\d+",
                     "{image_extension}": r"(?P<ext>[A-Za-z0-9]+)"}.items():
    file_name_pattern = file_name_pattern.replace(re.escape(token), regex)
file_name_pattern = re.compile(file_name_pattern)


def file_name_problem(file_name, pn):
    match = file_name_pattern.fullmatch(file_name.strip())
    if not match:
        return "Wrong path format"
    if pn is None:
        return "project_number missing, cannot compare"
    if "pn" in match.groupdict() and match.group("pn") != pn:
        return "project_number in file_name does not match"
    if "ext" in match.groupdict() and match.group("ext").lower() not in valid_image_extensions:
        return f"Not a valid image extension (.{match.group('ext')})"
    return None


def check_file_name(file_name, i, field, issues, empty_list):
    if is_empty(file_name):
        empty_list.append(LABEL[i])
        return
    problem = file_name_problem(str(file_name), PN[i])
    if problem:
        issues.append({"project_number": LABEL[i], "field": field, "issue": problem})


primary_issues, image_issues = [], []
primary_empty, image_empty = [], []

for i, record in enumerate(records):
    media = record.get("primary_media")
    if isinstance(media, dict) and media:
        check_file_name(media.get("file_name"), i, "primary_media.file_name",
                        primary_issues, primary_empty)

    details = record.get("inspection_details")
    if not isinstance(details, list):
        continue
    for d, inspection in enumerate(details):
        images = inspection.get("inspection_images") if isinstance(inspection, dict) else None
        if not isinstance(images, list):
            continue
        for m, image in enumerate(images):
            if isinstance(image, dict):
                check_file_name(image.get("file_name"), i,
                                f"inspection_details[{d}].inspection_images[{m}].file_name",
                                image_issues, image_empty)


def show_empty_info(empty_list):
    if empty_list:
        unique = list(dict.fromkeys(empty_list))
        print(f"ℹ️ INFO: Empty file_name in {len(empty_list)} place(s). "
              f"Project numbers: {', '.join(unique[:SAMPLE_LIMIT])}")


show_result(CHECK, primary_issues, part="primary_media.file_name")
show_empty_info(primary_empty)
show_result(CHECK, image_issues, part="inspection_images.file_name")
show_empty_info(image_empty)
 

# %%
# 15. Check project_is_followed is true/false
# ===========================================
CHECK = "15. project_is_followed true/false"
header(CHECK)
 
if "project_is_followed" not in df.columns:
    show_skipped(CHECK, "Field not in data.")
else:
    issues = [{"project_number": LABEL[i], "field": "project_is_followed",
               "issue": f"Must be true/false (found {type_name(r.get('project_is_followed'))})"}
              for i, r in enumerate(records) if not isinstance(r.get("project_is_followed"), bool)]
    show_result(CHECK, issues, "All values are true/false.")
 
 
# %%
# 16. Check inspection dates are within 4 weeks of the file date
# ==============================================================
CHECK = "16. Inspection dates"
header(CHECK)

MAX_WEEKS = 4
DATE_FORMAT = "%d/%m/%Y"
today = pd.Timestamp.today().normalize().strftime(DATE_FORMAT)

while True:
    answer = ask(f"Enter the file date as DD/MM/YYYY (press Enter to keep {today}): ") or today
    file_date = pd.to_datetime(answer, format=DATE_FORMAT, errors="coerce")
    if pd.notna(file_date):
        break
    print("Please enter a valid date like 21/10/2026.", file=original_stdout)

cutoff = file_date - pd.Timedelta(weeks=MAX_WEEKS)
print(f"ℹ️ INFO: File date is {file_date.strftime(DATE_FORMAT)}. "
      f"Inspections before {cutoff.strftime(DATE_FORMAT)} ({MAX_WEEKS} weeks older) are not allowed.")


def unique_date_sample(rows, limit):
    picked, seen = [], set()
    for row in rows:
        if row["inspection_date"] not in seen:
            picked.append(row)
            seen.add(row["inspection_date"])
        if len(picked) == limit:
            return picked
    for row in rows:
        if row not in picked:
            picked.append(row)
        if len(picked) == limit:
            break
    return picked


def show_dates(title, rows):
    print(f"❌ FAIL: {len(rows)} {title}:")
    print(pd.DataFrame(unique_date_sample(rows, SAMPLE_LIMIT)).to_string(index=False))


if "inspection_details" not in df.columns:
    show_skipped(CHECK, "Field not in data.")
else:
    old_dates, wrong_format = [], []
    for i, record in enumerate(records):
        details = record.get("inspection_details")
        if not isinstance(details, list):
            continue
        for inspection in details:
            if not isinstance(inspection, dict):
                continue
            raw = inspection.get("inspection_date")
            if is_empty(raw):
                continue
            row = {"project_number": LABEL[i], "inspection_date": str(raw).strip()}
            date = pd.to_datetime(row["inspection_date"], format=DATE_FORMAT, errors="coerce")
            if pd.isna(date):
                wrong_format.append(row)
            elif date < cutoff:
                old_dates.append(row)

    if old_dates:
        show_dates(f"inspection(s) older than {MAX_WEEKS} weeks from the file date", old_dates)
    else:
        print(f"✅ SUCCESS: No inspection is older than {MAX_WEEKS} weeks from the file date.")
    if wrong_format:
        print()
        show_dates("inspection date(s) with wrong format (expected DD/MM/YYYY)", wrong_format)

    total = len(old_dates) + len(wrong_format)
    RESULTS.append((CHECK, "FAIL" if total else "PASS", total))
# %%
# 17. Check phone numbers and emails
# ==================================
CHECK = "17. Phone and email"
header(CHECK)

CONTACT_FIELDS = ["developer_details", "management_companies"]
PHONE_KEYS = ("phone", "mobile", "tel", "fax")
EMAIL_KEYS = ("email", "mail")

email_pattern = re.compile(
    r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*\.[A-Za-z]{2,}"
)


def is_bad_phone(text):
    return any(ch.isalpha() for ch in text) or not any(ch.isdigit() for ch in text)


def is_bad_email(text):
    return not email_pattern.fullmatch(text) or ".." in text


def find_contacts(value):
    if isinstance(value, dict):
        for key, val in value.items():
            name = str(key).lower()
            if isinstance(val, (dict, list)):
                yield from find_contacts(val)
            elif not is_empty(val):
                if any(k in name for k in EMAIL_KEYS):
                    yield "email", str(val).strip()
                elif any(k in name for k in PHONE_KEYS):
                    yield "phone", str(val).strip()
    elif isinstance(value, list):
        for val in value:
            yield from find_contacts(val)


for field in CONTACT_FIELDS:
    if field not in df.columns:
        show_skipped(CHECK, "Field not in data.", part=field)
        continue

    bad = {"phone": [], "email": []}
    found = {"phone": 0, "email": 0}
    for i, record in enumerate(records):
        for kind, text in find_contacts(record.get(field)):
            found[kind] += 1
            if (is_bad_phone(text) if kind == "phone" else is_bad_email(text)):
                bad[kind].append({"project_number": LABEL[i], f"invalid_{kind}": text})

    for kind in ("phone", "email"):
        part = f"{field} - {kind}"
        print(f"\n▶ {part}")
        if not found[kind]:
            print(f"ℹ️ INFO: No {kind} values found.")
            RESULTS.append((f"{CHECK} - {part}", "INFO", 0))
        elif not bad[kind]:
            print(f"✅ SUCCESS: All {found[kind]} {kind} values are valid.")
            RESULTS.append((f"{CHECK} - {part}", "PASS", 0))
        else:
            print(f"❌ FAIL: {len(bad[kind])} invalid {kind} value(s):")
            print(pd.DataFrame(bad[kind][:SAMPLE_LIMIT]).to_string(index=False))
            RESULTS.append((f"{CHECK} - {part}", "FAIL", len(bad[kind])))

# %%
# Save the report
# ===============
print("\nFinished:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
print("=" * 70)

sys.stdout = original_stdout
report_file.close()
print(f"✅ Report saved to: {report_path}")
 


# %%
