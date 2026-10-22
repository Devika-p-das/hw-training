# %%
# Libraries
# =========
import os
import random
import re
import sys
from collections import Counter
from datetime import datetime
from urllib.parse import urlparse
 
import ijson
import pandas as pd
import requests
 
pd.set_option("display.max_colwidth", 100)
pd.set_option("display.width", 220)
 
 
# %%
# Inputs
# ======
FOLDER = "/home/user/Downloads/"
 
file_name = input("Enter the JSON file name: ").strip().strip('"').strip("'")
location = input("Enter the location (press Enter to keep 'abudhabi'): ").strip() or "abudhabi"
count_text = input("Enter the expected data count (press Enter to keep 11458): ").strip()
expected_count = int(count_text.replace(",", "")) if count_text else 11458
purpose = input("Enter the purpose, for-sale or for-rent (press Enter to keep 'for-sale'): ").strip().lower() or "for-sale"
while purpose not in ("for-sale", "for-rent"):
    purpose = input("Please enter for-sale or for-rent: ").strip().lower()
 
file_path = os.path.join(FOLDER, file_name)
SAMPLE_LIMIT = 5
RANDOM_CHECK_COUNT = 10
LISTING_DOMAIN = "bayut.com"
 
 
# %%
# Save all QA outputs to a report file
# ====================================
report_path = os.path.join(FOLDER, os.path.splitext(file_name)[0] + "_QA_Report.txt")
 
 
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
sys.stdout = Tee(original_stdout, report_file)
 
print("=" * 70)
print("QA REPORT")
print("=" * 70)
print("Started   :", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
print("Data file :", file_path)
print("Report    :", report_path)
print(f"Location  : {location}")
print(f"Data count: {expected_count:,}")
print(f"Purpose   : {purpose}")
 
 
# %%
# Helper functions
# ================
def header(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)
 
 
def normalize(text):
    return re.sub(r"[^a-z0-9]", "", str(text).lower())
 
 
class Issues:
    """Counts every issue but keeps only a few samples, preferring different values."""
 
    def __init__(self):
        self.count = 0
        self.unique = []
        self.others = []
        self.seen = set()
 
    def add(self, row, value_key):
        self.count += 1
        value = str(row.get(value_key))
        if value not in self.seen and len(self.unique) < SAMPLE_LIMIT:
            self.unique.append(row)
            self.seen.add(value)
        elif len(self.others) < SAMPLE_LIMIT:
            self.others.append(row)
 
    def sample(self):
        return (self.unique + self.others)[:SAMPLE_LIMIT]
 
 
def show(issues, fail_text, success_text, info=False):
    if issues.count == 0:
        print(f"✅ SUCCESS: {success_text}")
        return
    icon = "ℹ️ INFO" if info else "❌ FAIL"
    print(f"{icon}: {issues.count:,} {fail_text}:")
    print(pd.DataFrame(issues.sample()).to_string(index=False))
 
 
def url_problem(url):
    if not isinstance(url, str) or not url.strip():
        return "Empty URL"
    if url != url.strip():
        return "Space at start/end"
    if any(ch.isspace() for ch in url):
        return "Space inside URL"
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or "." not in parsed.netloc:
        return "Not a valid URL"
    return None
 
 
def find_urls(value):
    if isinstance(value, dict):
        for val in value.values():
            yield from find_urls(val)
    elif isinstance(value, list):
        for val in value:
            yield from find_urls(val)
    elif isinstance(value, str) and (value.startswith("http") or "://" in value or value.startswith("www.")):
        yield value
 
 
def city_of(location_value):
    if isinstance(location_value, list):
        levels = [x for x in location_value if isinstance(x, dict)]
        city = [x for x in levels if x.get("level") == 1]
        if city:
            return city[0].get("name") or city[0].get("slug")
        if len(levels) > 1:
            return levels[1].get("name")
    if isinstance(location_value, dict):
        return location_value.get("name")
    if isinstance(location_value, str):
        return location_value
    return None
 
 
def reservoir_add(sample, item, seen_count):
    if len(sample) < RANDOM_CHECK_COUNT:
        sample.append(item)
    else:
        j = random.randint(0, seen_count - 1)
        if j < RANDOM_CHECK_COUNT:
            sample[j] = item
 
 
# %%
# 1. Check file name structure
# ============================
header("1. File name structure")
 
name_word = "buy" if purpose == "for-sale" else "rent"
expected_name = f"bayut_{location}_properties_{name_word}_residential_YYYY_MM_DD.json"
name_match = re.fullmatch(
    rf"bayut_{re.escape(location)}_properties_{name_word}_residential_(\d{{4}}_\d{{2}}_\d{{2}})\.json",
    file_name,
)
name_date_ok = False
if name_match:
    try:
        datetime.strptime(name_match.group(1), "%Y_%m_%d")
        name_date_ok = True
    except ValueError:
        pass
 
if name_match and name_date_ok:
    print(f"✅ SUCCESS: File name is '{file_name}'.")
else:
    print("❌ FAIL: File name mismatch:")
    print(f" Expected '{expected_name}',")
    print(f" found '{file_name}'")
    if name_match and not name_date_ok:
        print(" (the date in the file name is not a real date)")
 
 
# %%
# Scan the whole file once (works for small and large files)
# ==========================================================
total = 0
not_object = 0
json_error = None
starts_with_list = False
 
id_counts = Counter()
purpose_counts = Counter()
city_counts = Counter()
 
listing_issues = Issues()
location_issues = Issues()
purpose_issues = Issues()
rental_issues = Issues()
image_issues = Issues()
missing_cover = Issues()
image_url_total = 0
listing_sample, image_sample = [], []
valid_listing_seen, valid_image_seen = 0, 0
 
if not os.path.exists(file_path):
    json_error = "File not found"
else:
    with open(file_path, "rb") as f:
        first_char = b""
        while True:
            ch = f.read(1)
            if not ch or not ch.isspace():
                first_char = ch
                break
        starts_with_list = first_char == b"["
        f.seek(0)
 
        if starts_with_list:
            try:
                for item in ijson.items(f, "item", use_float=True):
                    total += 1
                    if total % 20000 == 0:
                        print(f"\r  Scanned {total:,} records...", end="", file=original_stdout)
 
                    if not isinstance(item, dict):
                        not_object += 1
                        continue
 
                    pid = item.get("id")
                    pid = str(pid) if pid not in (None, "") else f"Record {total}"
                    id_counts[pid] += 1
 
                    # listing_url
                    url = item.get("listing_url")
                    problem = "Missing listing_url" if "listing_url" not in item else url_problem(url)
                    if not problem and LISTING_DOMAIN not in urlparse(url).netloc:
                        problem = f"Not a {LISTING_DOMAIN} URL"
                    if not problem:
                        url_id = re.search(r"details-(\d+)", url)
                        ext_id = item.get("externalID")
                        if url_id and ext_id not in (None, "") and url_id.group(1) != str(ext_id):
                            problem = "URL id does not match externalID"
                    if problem:
                        listing_issues.add({"id": pid, "listing_url": url if url else "Missing",
                                            "issue": problem}, "issue")
                    else:
                        valid_listing_seen += 1
                        reservoir_add(listing_sample, (pid, url), valid_listing_seen)
 
                    # location
                    city = city_of(item.get("location"))
                    city_counts[city if city else "Missing"] += 1
                    if not city or normalize(city) != normalize(location):
                        location_issues.add({"id": pid, "city": city if city else "Missing"}, "city")
 
                    # purpose and rental products
                    item_purpose = item.get("purpose")
                    purpose_counts[item_purpose if item_purpose else "Missing"] += 1
                    if item_purpose != purpose:
                        purpose_issues.add({"id": pid, "purpose": item_purpose}, "purpose")
                    if purpose == "for-sale" and (item.get("rentFrequency") or item.get("isShortTermRental") is True):
                        rental_issues.add({"id": pid, "rentFrequency": item.get("rentFrequency"),
                                           "isShortTermRental": item.get("isShortTermRental")},
                                          "rentFrequency")
 
                    # image urls
                    cover = item.get("coverPhoto")
                    if cover in (None, "", {}, []):
                        missing_cover.add({"id": pid, "listing_url": url}, "id")
                    for field in ("coverPhoto", "photos"):
                        for img in find_urls(item.get(field)):
                            image_url_total += 1
                            problem = url_problem(img)
                            if problem:
                                image_issues.add({"id": pid, "field": field, "image_url": img}, "image_url")
                            else:
                                valid_image_seen += 1
                                reservoir_add(image_sample, (pid, img), valid_image_seen)
            except ijson.JSONError as e:
                json_error = f"Invalid JSON after record {total:,}: {str(e).splitlines()[0]}"
            print("\r" + " " * 50 + "\r", end="", file=original_stdout)
 
 
# %%
# 2. Check JSON is valid (JSON list)
# ==================================
header("2. JSON valid (JSON list)")
 
if json_error == "File not found":
    print(f"❌ FAIL: File not found: {file_path}")
elif not starts_with_list:
    print("❌ FAIL: The file is not a JSON list (it must start with '[').")
elif json_error:
    print(f"❌ FAIL: {json_error}")
elif not_object:
    print(f"❌ FAIL: {not_object:,} items in the list are not objects {{...}}.")
else:
    print(f"✅ SUCCESS: Valid JSON list with {total:,} records.")
 
if json_error or not starts_with_list:
    print("\n❌ QA STOPPED: Fix the JSON file and run again.")
    sys.stdout = original_stdout
    report_file.close()
    raise SystemExit("QA stopped - invalid JSON file.")
 
 
# %%
# 3. Check data count
# ===================
header("3. Data count")
 
if total == expected_count:
    print(f"✅ SUCCESS: Data count is {total:,}.")
else:
    print("❌ FAIL: Data count mismatch:")
    print(f" Expected {expected_count:,},")
    print(f" found {total:,}")
 
 
# %%
# 4. Check duplicate id
# =====================
header("4. Duplicate id")
 
duplicates = {pid: n for pid, n in id_counts.items() if n > 1}
if not duplicates:
    print("✅ SUCCESS: All ids are unique.")
else:
    print(f"❌ FAIL: {len(duplicates):,} duplicate id(s):")
    print(pd.DataFrame([{"id": k, "times": v} for k, v in list(duplicates.items())[:SAMPLE_LIMIT]])
          .to_string(index=False))
 
 
# %%
# 5. Check listing_url
# ====================
header("5. listing_url")
show(listing_issues, "invalid listing_url(s)", "Every record has a valid listing_url.")
 
 
# %%
# 6. Check location
# =================
header(f"6. Location (only {location})")
 
print("Cities found:")
for city, n in city_counts.most_common():
    print(f"   {city}: {n:,}")
print()
show(location_issues, f"record(s) not in {location}", f"All records are in {location}.")
 
 
# %%
# 7. Check purpose (only sale or only rent)
# =========================================
header(f"7. Purpose (only {purpose})")
 
print("Purpose values found:")
for value, n in purpose_counts.most_common():
    print(f"   {value}: {n:,}")
print()
show(purpose_issues, f"record(s) are not {purpose}", f"All records are {purpose}.")
if purpose == "for-sale":
    print()
    show(rental_issues, "record(s) look like rental products",
         "No rental products found (rentFrequency empty, isShortTermRental not true).")
 
 
# %%
# 8. Check image URLs (coverPhoto and photos)
# ===========================================
header("8. Image URLs")
 
print(f"Image URLs checked: {image_url_total:,}")
if image_url_total == 0:
    print("ℹ️ INFO: No image URLs found in coverPhoto or photos.")
else:
    show(image_issues, "invalid image URL(s)", "All image URLs are valid.")
print()
show(missing_cover, "record(s) with missing coverPhoto", "Every record has a coverPhoto.", info=True)
 
 
# %%
# 9. Check random URLs are working (live check)
# =============================================
header(f"9. Live URL check ({RANDOM_CHECK_COUNT} random listing URLs + {RANDOM_CHECK_COUNT} random image URLs)")
 
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
 
 
def url_status(url):
    try:
        r = requests.head(url, headers=HEADERS, timeout=15, allow_redirects=True)
        if r.status_code in (403, 405) or r.status_code >= 500:
            r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True, stream=True)
            r.close()
        return r.status_code
    except requests.RequestException as e:
        return type(e).__name__
 
 
def live_check(title, sample):
    if not sample:
        print(f"\n▶ {title}\nℹ️ INFO: No valid URLs to check.")
        return
    rows = []
    for pid, url in sample:
        status = url_status(url)
        if isinstance(status, int) and status < 400:
            result = "OK"
        elif status in (403, 429):
            result = "Blocked by site, check manually"
        else:
            result = "Not working"
        rows.append({"id": pid, "status": status, "result": result, "url": url})
    print(f"\n▶ {title}")
    if all(not isinstance(r["status"], int) for r in rows):
        print(f"⚠️ SKIPPED: Could not connect to the internet ({rows[0]['status']}). "
              "Check your connection and run this cell again.")
        return
    bad = [r for r in rows if r["result"] == "Not working"]
    if bad:
        print(f"❌ FAIL: {len(bad)} of {len(rows)} URL(s) not working:")
        print(pd.DataFrame(bad)[["id", "status", "url"]].to_string(index=False))
    else:
        blocked = sum(r["result"] != "OK" for r in rows)
        note = f" ({blocked} blocked by the site, check manually)" if blocked else ""
        print(f"✅ SUCCESS: {len(rows) - blocked} of {len(rows)} URL(s) working{note}.")
 
 
live_check("listing_url", listing_sample)
live_check("image URLs", image_sample)
 
 
# %%
# Save the report
# ===============
print("\nFinished:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
print("=" * 70)
 
sys.stdout = original_stdout
report_file.close()
print(f"✅ Report saved to: {report_path}")
 
Claude finished the response
