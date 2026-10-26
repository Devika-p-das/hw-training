# %% [markdown]
# # 🤖 dm Austria — QA AI Agent
# For `DataHut_AT_Dm_PriceExtractions_yyyymmdd.CSV`
#
# **How to use:** Run All → paste the file path in the input box.
# Saved next to your data file:
# - `<file>_QA_Report.txt` → simple PASS / FAIL report (max 5 examples per issue)
# - `<file>_QA_Issues.csv` → every affected row
# - `<file>_AI_Analysis.txt` → only if the AI agent (Ollama) is running
#
# Row numbers = LibreOffice Calc row numbers (header = row 1, first product = row 2).
 
# %%
# ── Cell 1: Imports ──────────────────────────────────────────────────────────
import csv
import json
import re
import urllib.request
import warnings
from datetime import datetime, timedelta
from pathlib import Path
 
import numpy as np
import pandas as pd
 
warnings.filterwarnings("ignore", message="This pattern is interpreted as a regular expression")
 
# %%
# ── Cell 2: ✏️ SETTINGS ─────────────────────────────────────────────────────
ASK_FOR_PATH = True      # True = input box asks for the file path
INPUT_FILE = r"/home/user/Downloads/DataHut_AT_Dm_PriceExtractions_20261023.CSV"  # used if ASK_FOR_PATH = False
PREVIOUS_FILE = None     # optional: previous delivery, used only by the AI agent
 
EXAMPLES = 5             # examples shown per issue
RANDOM_CHECK_COUNT = 3   # random URLs for manual website check
ROW_OFFSET = 0           # added to every row number (0 = LibreOffice row number)
 
USE_AI_AGENT = True      # needs Ollama (https://ollama.com) + "ollama pull qwen3:8b"; skipped if not running
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen3:8b"
OLLAMA_CONTEXT = 16384
AI_MAX_STEPS = 10
 
# %%
# ── Cell 3: ✏️ DM REQUIREMENTS ──────────────────────────────────────────────
EXPECTED_COLUMNS = [
    "unique_id", "competitor_name", "extraction_date", "product_name", "grammage_quantity",
    "grammage_unit", "regular_price", "selling_price", "price_valid_from", "price_per_unit",
    "percentage_discount", "promotion_price", "promotion_valid_from", "promotion_valid_upto",
    "promotion_description", "currency", "breadcrumb", "pdp_url", "region", "pack_size", "site_shown_uom",
]
FILE_NAME_REGEX = r"^DataHut_AT_Dm_PriceExtractions_\d{8}\.CSV$"
FILE_NAME_FORMAT = "DataHut_AT_Dm_PriceExtractions_yyyymmdd.CSV"
EXPECTED_DELIMITER = "|"
EXPECTED_ROW_COUNT = 16642       # data count must match exactly
COMPETITOR_NAME = "dm"
 
MANDATORY_COLUMNS = ["unique_id", "competitor_name", "extraction_date", "product_name",
                     "grammage_quantity", "grammage_unit", "regular_price", "selling_price",
                     "breadcrumb", "pdp_url", "site_shown_uom"]
MUST_BE_EMPTY_COLUMNS = ["promotion_valid_upto", "region", "pack_size", "promotion_description",
                         "percentage_discount"]
 
NULL_TOKENS = ["null", "nan", "none", "n/a", "na", "undefined", "nil", "nat", "nul", "-", "--", "?",
               "#n/a", "#na", "#value!", "#ref!", "[]", "{}", "missing", "not available"]
 
UNIQUE_ID_REGEX = r"^[A-Za-z0-9]+$"
URL_REGEX = r"^https://www\.dm\.at/p/d/\d+/\S+$"      # e.g. https://www.dm.at/p/d/3117220/bali-bronze-...
 
PRICE_COLUMNS = ["regular_price", "selling_price", "promotion_price"]   # must look like 3.99
PRICE_PER_UNIT_COLUMN = "price_per_unit"                               # number part must look like 1.10
 
EXTRACTION_DATE_FORMAT = "%Y-%m-%d"
DATE_COLUMNS = ["price_valid_from", "promotion_valid_from", "promotion_valid_upto"]
DATE_FORMATS = ["%Y-%m-%d", "%d.%m.%Y"]
DATE_FORMATS_TEXT = "yyyy-mm-dd or dd.mm.yyyy"
FUTURE_DATE_LIMIT_DAYS = 730     # later than extraction_date + 730 days -> wrong (e.g. 9999)
 
# grammage_quantity may contain: digits . , spaces and x/× (multipack). Anything else = issue
GRAMMAGE_QTY_BAD_CHARS = r"[^0-9.,xX×\s]"
VALID_UNITS = ["g", "kg", "mg", "ml", "l", "cl", "dl", "m", "cm", "mm", "m²", "btl", "stuck", "wg",
               "stück", "st", "paar", "blatt", "tabs", "kapseln", "portionen", "anzahl"]
 
BREADCRUMB_REGEX = r"^[^>]+( > [^>]+)*$"     # valid: 'aaa' or 'aaa > bb > cc' (your rule)
SITE_UOM_BAD_CHARS = r"[^\w\s.,×/²³%()\-]"
 
UOM_KEYWORD_RULES = [
    (r"(?i)teebeutel|beutel|\bbtl\b", "btl", "Teebeutel/Beutel/Btl"),
    (r"(?i)portion\s*packung|\bANW\b", "stuck", "Portion Packung/ANW"),
    (r"(?i)\bwg\b|waschg(ä|a)nge?", "wg", "wg/Waschgänge"),
]
 
# %%
# ── Cell 4: Load file ───────────────────────────────────────────────────────
STARTED = datetime.now()
VERSION = "dm QA v6 (2026-10-23)"
if ASK_FOR_PATH:
    INPUT_FILE = input("📂 Paste the dm data file path: ").strip().strip('"').strip("'").strip()
if not Path(INPUT_FILE).is_file():
    raise FileNotFoundError(f"File not found: {INPUT_FILE}")
FILE = Path(INPUT_FILE)
OUT_DIR = FILE.resolve().parent
INFO = {"bad_rows": [], "blank_rows": [], "delimiter": None, "encoding": None}
 
 
def load_csv(path):
    for enc in ["utf-8-sig", "cp1252", "latin-1"]:
        try:
            Path(path).read_text(encoding=enc)
            INFO["encoding"] = enc
            break
        except UnicodeDecodeError:
            pass
    with open(path, encoding=INFO["encoding"], errors="replace") as f:
        head = f.readline()
    counts = {d: head.count(d) for d in ["|", ",", ";", "\t"]}
    INFO["delimiter"] = delim = max(counts, key=counts.get) if max(counts.values()) else ","
    rows, calc_rows = [], []
    with open(path, encoding=INFO["encoding"], newline="") as f:
        reader = csv.reader(f, delimiter=delim)
        header = next(reader)
        calc_row = 1                                   # LibreOffice row of the header
        for rec in reader:
            calc_row += 1                              # every record = one LibreOffice row
            if not rec or (len(rec) == 1 and not rec[0].strip()):
                INFO["blank_rows"].append(calc_row + ROW_OFFSET)
            elif len(rec) != len(header):
                INFO["bad_rows"].append((calc_row + ROW_OFFSET, len(rec)))
            else:
                rows.append(rec)
                calc_rows.append(calc_row + ROW_OFFSET)
    data = pd.DataFrame(rows, columns=[h.replace("﻿", "").strip() for h in header], dtype=object)
    data["_row"] = calc_rows
    return data, header
 
 
try:
    if FILE.suffix.lower() in (".xlsx", ".xlsm"):
        df = pd.read_excel(FILE, dtype=object, keep_default_na=False).astype(str).astype(object)
        RAW_HEADER = list(df.columns)
        df["_row"] = np.arange(len(df)) + 2 + ROW_OFFSET
        INFO.update(delimiter="n/a", encoding="n/a")
    else:
        df, RAW_HEADER = load_csv(FILE)
    LOAD_STATUS = "✅ SUCCESS"
except Exception as e:
    LOAD_STATUS = f"❌ FAILED ({e})"
    raise
 
COLS = [c for c in df.columns if c != "_row"]
N = len(df)
V = {c: df[c].fillna("").astype(str) for c in COLS}     # raw text
S = {c: V[c].str.strip() for c in COLS}                  # trimmed text
has = lambda c: c in COLS
URL = "pdp_url" if has("pdp_url") else None
print(f"✅ Loaded {FILE.name}: {N:,} rows × {len(COLS)} columns")
 
# %%
# ── Cell 5: Check helpers ───────────────────────────────────────────────────
SECTIONS = {}     # section title -> {"ok": text shown when all pass, "lines": [...], "issues": [...]}
NULLS = [t.lower() for t in NULL_TOKENS]
 
 
def section(title, ok_text):
    SECTIONS[title] = {"ok": ok_text, "lines": [], "issues": []}
    return title
 
 
def blank(c):
    return S[c] == ""
 
 
def nullish(c):
    return S[c].str.lower().isin(NULLS)
 
 
def filled(c):
    return ~blank(c) & ~nullish(c)
 
 
def num(c):
    return pd.to_numeric(S[c], errors="coerce")
 
 
def hits(mask, field, show=None, reason=None):
    """Rows where mask is True. show = columns whose VALUES are printed."""
    m = pd.Series(mask, index=df.index).fillna(False).astype(bool)
    out = pd.DataFrame({"row": df.loc[m, "_row"].values, "field": field,
                        "pdp_url": V[URL][m].values if URL else ""})
    text = pd.Series("", index=df.index[m])
    for c in (show or []):
        part = c + ": " + V[c][m].map(repr)
        text = part if (text == "").all() else text + " | " + part
    if reason is not None:
        text = text + " (" + pd.Series(reason, index=df.index)[m] + ")"
    out["values"] = text.values
    return out
 
 
def issue(sec, text, found=None, fail=None):
    """Row issue: found = hits(...) or list of hits. File issue: fail=True with text only."""
    if found is not None:
        parts = [f for f in (found if isinstance(found, list) else [found]) if len(f)]
        if not parts:
            return
        found = pd.concat(parts, ignore_index=True).sort_values("row", kind="stable")
        SECTIONS[sec]["issues"].append({"text": text, "found": found, "count": len(found)})
    elif fail:
        SECTIONS[sec]["issues"].append({"text": text, "found": None, "count": None})
 
 
def info(sec, line):
    SECTIONS[sec]["lines"].append(line)
 
 
def cols_ok(sec, *cols):
    miss = [c for c in cols if not has(c)]
    if miss:
        issue(sec, f"Column missing: {', '.join(miss)} (check skipped)", fail=True)
    return not miss
 
 
print("✅ Ready")
 
# %%
# ── Cell 6: Checks ──────────────────────────────────────────────────────────
# 1. File name
s1 = section("1. File name", f"File name is '{FILE.name}'.")
issue(s1, f"File name '{FILE.name}' does not match {FILE_NAME_FORMAT}", fail=not re.match(FILE_NAME_REGEX, FILE.name))
 
# 2. File format
s2 = section("2. File format", f"'{EXPECTED_DELIMITER}' delimited CSV, all rows have {len(RAW_HEADER)} fields.")
issue(s2, f"Delimiter is {INFO['delimiter']!r}, expected {EXPECTED_DELIMITER!r}",
      fail=INFO["delimiter"] not in (EXPECTED_DELIMITER, "n/a"))
issue(s2, f"{len(INFO['bad_rows'])} row(s) with wrong number of fields: "
          + ", ".join(f"Row {r} ({k} fields)" for r, k in INFO["bad_rows"][:EXAMPLES]), fail=bool(INFO["bad_rows"]))
issue(s2, f"{len(INFO['blank_rows'])} blank row(s): " + ", ".join(map(str, INFO["blank_rows"][:EXAMPLES])),
      fail=bool(INFO["blank_rows"]))
 
# 3. Data count
s3 = section("3. Data count", f"Data count matches ({N:,}).")
info(s3, f"Requirement - required data count: {EXPECTED_ROW_COUNT:,}")
issue(s3, f"Expected {EXPECTED_ROW_COUNT:,}, found {N:,} (difference {N - EXPECTED_ROW_COUNT:+,})",
      fail=N != EXPECTED_ROW_COUNT)
 
# 4. Fields and field order
s4 = section("4. Fields and field order", "Field names, count and order match.")
info(s4, f"Required fields: {len(EXPECTED_COLUMNS)}")
info(s4, f"Fields in data : {len(COLS)}")
missing_cols = [c for c in EXPECTED_COLUMNS if not has(c)]
extra_cols = [c for c in COLS if c not in EXPECTED_COLUMNS]
issue(s4, "Missing field(s): " + ", ".join(missing_cols), fail=bool(missing_cols))
issue(s4, "Extra field(s): " + ", ".join(extra_cols), fail=bool(extra_cols))
issue(s4, "Field order does not match the requirement",
      fail=[c for c in COLS if c in EXPECTED_COLUMNS] != [c for c in EXPECTED_COLUMNS if has(c)])
issue(s4, "Spaces in field names: " + ", ".join(repr(h) for h in RAW_HEADER if h != h.strip()),
      fail=[h.strip() for h in RAW_HEADER] != RAW_HEADER)
 
# 5. Empty fields (requirement)
s5 = section("5. Empty fields", "All required empty fields are empty: " + ", ".join(MUST_BE_EMPTY_COLUMNS) + ".")
for c in MUST_BE_EMPTY_COLUMNS:
    if cols_ok(s5, c):
        issue(s5, f"{c} is filled (must be empty)", hits(~blank(c), c))
 
# 6. Missing values (info)
s6 = section("6. Missing values per field (info)", "No missing values.")
for c in COLS:
    n = int((blank(c) | nullish(c)).sum())
    if n:
        info(s6, f"{c:<24}{n:>8,}  ({n / max(N, 1) * 100:.1f}%)")
 
# 7. Extraction date
s7 = section("7. Extraction date", "extraction_date is valid (yyyy-mm-dd).")
 
 
def parse_dates(series, formats):
    cache = {}
    for v in series.unique():
        d = None
        for f in formats:
            try:
                d = datetime.strptime(v, f)
                break
            except ValueError:
                pass
        cache[v] = d
    return pd.Series([cache[v] for v in series], index=series.index, dtype=object)
 
 
isd = lambda x: isinstance(x, datetime) and not pd.isna(x)
m = re.search(r"(\d{8})", FILE.name)
try:
    FILE_DATE = datetime.strptime(m.group(1), "%Y%m%d") if m else None
except ValueError:
    FILE_DATE = None
REF = pd.Series([FILE_DATE or datetime.now()] * N, index=df.index, dtype=object)
if cols_ok(s7, "extraction_date"):
    ed = parse_dates(S["extraction_date"], [EXTRACTION_DATE_FORMAT])
    issue(s7, "extraction_date not in yyyy-mm-dd format",
          hits(filled("extraction_date") & ~ed.map(isd), "extraction_date", show=["extraction_date"]))
    issue(s7, "extraction_date is in the future",
          hits(ed.map(lambda d: isd(d) and d > datetime.now()), "extraction_date", show=["extraction_date"]))
    REF = pd.Series([d if isd(d) else r for d, r in zip(ed, REF)], index=df.index, dtype=object)
 
# 8. Competitor name
s8 = section("8. Competitor name", f"competitor_name is '{COMPETITOR_NAME}' in all rows.")
if cols_ok(s8, "competitor_name"):
    issue(s8, f"competitor_name is not '{COMPETITOR_NAME}'",
          hits(S["competitor_name"] != COMPETITOR_NAME, "competitor_name", show=["competitor_name"]))
 
# 9. Breadcrumb
s9 = section("9. Breadcrumb", "breadcrumb is filled and in format 'aaa > bb > cc'.")
if cols_ok(s9, "breadcrumb"):
    bf = filled("breadcrumb")
    issue(s9, "Empty breadcrumb found", hits(~bf, "breadcrumb"))
    issue(s9, "Invalid breadcrumb format found (must be 'aaa > bb > cc')",
          hits(bf & ~V["breadcrumb"].str.fullmatch(BREADCRUMB_REGEX, na=False), "breadcrumb", show=["breadcrumb"]))
    issue(s9, "NULL / nan level found inside breadcrumb",
          hits(bf & S["breadcrumb"].str.split(">", regex=False).map(lambda ps: any(p.strip().lower() in NULLS for p in ps)),
               "breadcrumb", show=["breadcrumb"]))
 
# 10. PDP URL
s10 = section("10. PDP URL", "pdp_url is filled, valid and unique.")
if cols_ok(s10, "pdp_url"):
    p, pf = S["pdp_url"], filled("pdp_url")
    issue(s10, "pdp_url is empty", hits(~pf, "pdp_url"))
    issue(s10, "pdp_url is not a valid dm URL (https://www.dm.at/p/d/<id>/<name>)", hits(pf & ~p.str.match(URL_REGEX), "pdp_url"))
    issue(s10, "pdp_url is duplicated", hits(pf & p.duplicated(keep=False), "pdp_url"))
 
# 11. Prices (values shown)
s11 = section("11. Prices", "regular_price, selling_price, promotion_price, price_per_unit are in 0.00 format "
                             "and regular_price ≥ selling_price / promotion_price.")
 
 
def price_problem(c):
    s, f = S[c], filled(c)
    r = pd.Series("", index=df.index)
    r[f & s.str.contains(",", regex=False)] = "comma"
    r[(r == "") & f & (s.str.count(r"\.") > 1)] = "extra dot"
    r[(r == "") & f & s.str.contains(r"[^0-9.]", regex=True)] = "symbol / letter / minus"
    r[(r == "") & f & ~s.str.match(r"^\d+\.\d{2}$")] = "not 2 decimals"
    r[(r == "") & f & (num(c) == 0)] = "zero"
    return r
 
 
for c in PRICE_COLUMNS:
    if cols_ok(s11, c):
        r = price_problem(c)
        issue(s11, f"{c} not in 0.00 format", hits(r != "", c, show=[c], reason=r))
c = PRICE_PER_UNIT_COLUMN
if cols_ok(s11, c):
    s, f = S[c], filled(c)
    numpart = s.str.extract(r"^([0-9.,]+)")[0].fillna("")
    r = pd.Series("", index=df.index)
    r[f & (numpart == "")] = "no price at start"
    r[(r == "") & f & numpart.str.contains(",", regex=False)] = "comma"
    r[(r == "") & f & (numpart.str.count(r"\.") > 1)] = "extra dot"
    r[(r == "") & f & ~numpart.str.match(r"^\d+\.\d{2}$")] = "not 2 decimals"
    issue(s11, f"{c} not in 0.00 format", hits(r != "", c, show=[c], reason=r))
for big, small in [("regular_price", "selling_price"), ("regular_price", "promotion_price")]:
    if cols_ok(s11, big, small):
        a, b2 = num(big), num(small)
        issue(s11, f"{big} is lower than {small}", hits(a.notna() & b2.notna() & (a < b2), big, show=[big, small]))
if cols_ok(s11, "promotion_description", "promotion_price", "selling_price"):
    pp, sp = num("promotion_price"), num("selling_price")
    bad = filled("promotion_description") & (pp.isna() | sp.isna() | ~np.isclose(pp.fillna(-1), sp.fillna(-2)))
    issue(s11, "promotion_description present but promotion_price ≠ selling_price",
          hits(bad, "promotion_price", show=["promotion_description", "promotion_price", "selling_price"]))
 
# 12. unique_id
s12 = section("12. Unique ID", "unique_id is unique and has no symbols.")
if cols_ok(s12, "unique_id"):
    u = S["unique_id"]
    issue(s12, "unique_id is duplicated", hits((u != "") & u.duplicated(keep=False), "unique_id"))
    issue(s12, "Symbol found in unique_id", hits(filled("unique_id") & ~u.str.match(UNIQUE_ID_REGEX), "unique_id"))
 
# 13. Mandatory fields
s13 = section("13. Mandatory fields", "All mandatory fields are filled.")
for c in MANDATORY_COLUMNS:
    if cols_ok(s13, c):
        issue(s13, f"Mandatory field {c} is empty", hits(blank(c), c))
 
# 14. NULL-like values
s14 = section("14. NULL / nan / None / N/A / undefined values", "No NULL-like values.")
for c in COLS:
    issue(s14, f"NULL-like text (NULL, nan, None, N/A, undefined) found in {c}", hits(nullish(c), c))
 
# 15. Whitespace (visible spaces and tabs only)
s15 = section("15. Extra whitespace", "No extra spaces or tabs.")
for c in COLS:
    v = V[c]
    issue(s15, f"Space at start or end of value found in {c}", hits(v.str.contains(r"^[ \t]+\S|\S[ \t]+$", regex=True), c))
    issue(s15, f"Value with only spaces found in {c}", hits(v.str.match(r"^[ \t]+$"), c))
    issue(s15, f"Double space found in {c}", hits(v.str.contains(r"\S {2,}\S", regex=True), c))
    issue(s15, f"Tab or line break found in {c}", hits(v.str.contains(r"[\t\r\n]", regex=True), c))
 
# 16. Dates (values shown)
s16 = section("16. Price / promotion dates", f"Dates are valid ({DATE_FORMATS_TEXT}), not in far future, from ≤ upto.")
PARSED, INVALID, FUTURE = {}, [], []
promo_cols = [c for c in ["promotion_valid_from", "promotion_valid_upto"] if has(c)]
 
 
def one_line_per_row(parts):
    """Same row in several date fields -> one line: 'price_valid_from: x | promotion_valid_from: y'."""
    parts = [p for p in parts if len(p)]
    if not parts:
        return []
    allp = pd.concat(parts, ignore_index=True)
    return allp.groupby("row", sort=True).agg(
        field=("field", ", ".join), pdp_url=("pdp_url", "first"), values=("values", " | ".join)).reset_index()
 
 
for c in DATE_COLUMNS:
    if not cols_ok(s16, c):
        continue
    d = PARSED[c] = parse_dates(S[c], DATE_FORMATS)
    INVALID.append(hits(filled(c) & ~d.map(isd), c, show=[c]))
    FUTURE.append(hits(pd.Series([isd(x) and x > r + timedelta(days=FUTURE_DATE_LIMIT_DAYS)
                                  for x, r in zip(d, REF)], index=df.index), c, show=[c]))
issue(s16, f"Invalid date (wrong format or impossible date; allowed {DATE_FORMATS_TEXT})", one_line_per_row(INVALID))
issue(s16, f"Date too far in the future (more than {FUTURE_DATE_LIMIT_DAYS // 365} years after extraction_date, "
           f"e.g. 29.12.9999)", one_line_per_row(FUTURE))
if "promotion_valid_from" in PARSED and "promotion_valid_upto" in PARSED:
    f_, t_ = PARSED["promotion_valid_from"], PARSED["promotion_valid_upto"]
    issue(s16, "promotion_valid_from is after promotion_valid_upto",
          hits(pd.Series([isd(a) and isd(b) and a > b for a, b in zip(f_, t_)], index=df.index),
               "promotion_valid_from", show=promo_cols))
 
# 17. Grammage
s17 = section("17. Grammage", "grammage_quantity and grammage_unit are valid.")
if cols_ok(s17, "grammage_quantity"):
    gq = S["grammage_quantity"]
    issue(s17, "Letters or symbols found in grammage_quantity",
          hits(filled("grammage_quantity") & gq.str.contains(GRAMMAGE_QTY_BAD_CHARS, regex=True),
               "grammage_quantity", show=["grammage_quantity"]))
    issue(s17, "grammage_quantity is zero", hits(pd.to_numeric(gq, errors="coerce") == 0, "grammage_quantity"))
if cols_ok(s17, "grammage_unit"):
    gu = S["grammage_unit"]
    letters = gu.str.match(r"^[A-Za-zäöüÄÖÜß²³]+$")
    issue(s17, "Symbols or digits found in grammage_unit",
          hits(filled("grammage_unit") & ~letters, "grammage_unit", show=["grammage_unit"]))
    issue(s17, "Unknown grammage_unit found (add it to VALID_UNITS if correct)",
          hits(filled("grammage_unit") & letters & ~gu.str.lower().isin([x.lower() for x in VALID_UNITS]),
               "grammage_unit", show=["grammage_unit"]))
 
# 18. site_shown_uom
s18 = section("18. site_shown_uom", "site_shown_uom is valid and grammage_unit rules are followed.")
if cols_ok(s18, "site_shown_uom"):
    su = S["site_shown_uom"]
    issue(s18, "Unexpected symbols found in site_shown_uom",
          hits(filled("site_shown_uom") & su.str.contains(SITE_UOM_BAD_CHARS, regex=True),
               "site_shown_uom", show=["site_shown_uom"]))
    if has("grammage_unit"):
        for pattern, unit, words in UOM_KEYWORD_RULES:
            issue(s18, f"{words} in site_shown_uom but grammage_unit is not '{unit}'",
                  hits(su.str.contains(pattern, regex=True) & (S["grammage_unit"] != unit), "grammage_unit",
                       show=["site_shown_uom", "grammage_unit"]))
 
# 19. Text and duplicates
s19 = section("19. Text and duplicate rows", "No HTML, no broken characters, no duplicate rows.")
for c in [c for c in ["product_name", "breadcrumb", "site_shown_uom"] if has(c)]:
    issue(s19, f"HTML found in {c}", hits(V[c].str.contains(r"<[^>]+>|&(?:amp|nbsp|quot|lt|gt|#\d+);", regex=True), c))
    issue(s19, f"Broken characters (ä ö ü ß) found in {c}", hits(V[c].str.contains(r"Ã.|â€|Â|�", regex=True), c))
issue(s19, "Duplicate rows found", hits(df.duplicated(subset=COLS, keep=False), "(all fields)"))
print("✅ Checks done")
 
# %%
# ── Cell 7: Write the report and the issue CSV ──────────────────────────────
LINE = "=" * 70
REPORT_PATH = OUT_DIR / f"{FILE.stem}_QA_Report.txt"
CSV_PATH = OUT_DIR / f"{FILE.stem}_QA_Issues.csv"
RANDOM_ROWS = df.sample(n=min(RANDOM_CHECK_COUNT, N)) if N else df.head(0)
FAILED = [(t, i) for t, s in SECTIONS.items() for i in s["issues"]]
 
L = [LINE, "QA REPORT", LINE,
     f"Version  : {VERSION}",
     f"Started  : {STARTED:%Y-%m-%d %H:%M:%S}",
     f"Data file: {FILE.resolve()}",
     f"Report   : {REPORT_PATH}",
     f"File load: {LOAD_STATUS}"]
for title, sec in SECTIONS.items():
    L += ["", LINE, title, LINE]
    L += sec["lines"]
    if title.startswith("6."):          # info section
        if not sec["lines"]:
            L.append(sec["ok"])
        continue
    if not sec["issues"]:
        L.append(f"✅ PASS: {sec['ok']}")
        continue
    for i in sec["issues"]:
        if i["found"] is None:
            L.append(f"❌ FAIL: {i['text']}")
            continue
        shown = min(EXAMPLES, i["count"])
        L.append(f"❌ FAIL: {i['text']} — {i['count']:,} issue(s) found. Showing {shown}:")
        for _, h in i["found"].head(EXAMPLES).iterrows():
            L.append(f"     Row {h['row']} | {h['values'] or h['field']} | {h['pdp_url']}")
L += ["", LINE, "20. Manual check on website (random rows)", LINE]
L += [f"Row {r['_row']} | {r[URL] if URL else ''}" for _, r in RANDOM_ROWS.iterrows()]
L += ["", LINE,
      f"RESULT: {'❌ FAIL' if FAILED else '✅ PASS'} — {len(FAILED)} issue type(s) found" if FAILED
      else "RESULT: ✅ PASS — no issues found", LINE]
REPORT = "\n".join(L)
REPORT_PATH.write_text(REPORT, encoding="utf-8")
 
frames = []
for title, i in FAILED:
    if i["found"] is None:
        frames.append(pd.DataFrame([{"section": title, "issue": i["text"], "row": "", "field": "",
                                     "pdp_url": "", "values": ""}]))
    else:
        f = i["found"].copy()
        f.insert(0, "issue", i["text"])
        f.insert(0, "section", title)
        frames.append(f)
cols = ["section", "issue", "row", "field", "pdp_url", "values"]
(pd.concat(frames, ignore_index=True)[cols] if frames else pd.DataFrame(columns=cols)).to_csv(
    CSV_PATH, index=False, encoding="utf-8-sig")
print(L[-2])
print(f"📄 Report (text file): {REPORT_PATH}")
print(f"📊 All issue rows    : {CSV_PATH}")
 
# %%
# ── Cell 8: AI agent — root causes of the issues (optional, separate file) ──
def _j(o, limit=5000):
    s = json.dumps(o, ensure_ascii=False, default=str)
    return s if len(s) <= limit else s[:limit] + " ...(truncated)"
 
 
CTX = [c for c in ["unique_id", "product_name", "grammage_quantity", "grammage_unit", "site_shown_uom",
                   "regular_price", "selling_price", "price_per_unit", "breadcrumb", "pdp_url"] if has(c)]
 
 
def _sample(mask, extra=None):
    cols = ["_row"] + list(dict.fromkeys(CTX + [c for c in (extra or []) if has(c)]))
    return df.loc[mask, cols].head(5).astype(str).apply(lambda s: s.str.slice(0, 70)).to_dict("records")
 
 
def get_issue_rows(issue_text):
    """Sample rows (all context columns) for one issue."""
    hit = next((i for _, i in FAILED if i["text"].lower() == issue_text.lower()), None)
    if hit is None or hit["found"] is None:
        return _j({"error": "issue not found", "issues": [i["text"] for _, i in FAILED][:40]})
    fields = list(hit["found"]["field"].unique()[:3])
    return _j({"issue": hit["text"], "count": hit["count"],
               "sample": _sample(df["_row"].isin(set(hit["found"]["row"].head(5))), fields)})
 
 
def profile_column(column):
    """Top values and patterns (digits->9, letters->a)."""
    if not has(column):
        return _j({"error": "unknown column", "columns": COLS})
    s = S[column][S[column] != ""]
    pat = s.str.replace(r"\d+", "9", regex=True).str.replace(r"[^\W\d_]+", "a", regex=True)
    return _j({"filled": len(s), "empty": N - len(s), "top_values": s.value_counts().head(10).to_dict(),
               "top_patterns": pat.value_counts().head(10).to_dict()})
 
 
def find_rows(column, operator, value=""):
    """operator: equals | contains | regex | empty | not_empty"""
    if not has(column):
        return _j({"error": "unknown column"})
    s = S[column]
    ops = {"equals": lambda: s == value, "contains": lambda: s.str.contains(value, case=False, regex=False),
           "regex": lambda: s.str.contains(value, regex=True, na=False), "empty": lambda: s == "",
           "not_empty": lambda: s != ""}
    if operator not in ops:
        return _j({"error": f"operator must be one of {list(ops)}"})
    mk = ops[operator]()
    return _j({"matches": int(mk.sum()), "sample": _sample(mk, [column])})
 
 
def compare_with_previous():
    """Row count and new/removed IDs vs PREVIOUS_FILE."""
    if not PREVIOUS_FILE:
        return _j({"error": "no previous file"})
    prev, _ = load_csv(Path(PREVIOUS_FILE))
    out = {"rows_previous": len(prev), "rows_current": N}
    if has("unique_id") and "unique_id" in prev:
        p_, c_ = set(prev["unique_id"].str.strip()), set(S["unique_id"])
        out.update(new_ids=len(c_ - p_), removed_ids=len(p_ - c_))
    return _j(out)
 
 
TOOLS = {"get_issue_rows": get_issue_rows, "profile_column": profile_column, "find_rows": find_rows,
         "compare_with_previous": compare_with_previous}
_T = lambda n, d, p, r: {"type": "function", "function": {"name": n, "description": d, "parameters": {
    "type": "object", "properties": p, "required": r}}}
TOOL_SCHEMAS = [
    _T("get_issue_rows", "Sample rows for one issue", {"issue_text": {"type": "string"}}, ["issue_text"]),
    _T("profile_column", "Top values and patterns of a column", {"column": {"type": "string"}}, ["column"]),
    _T("find_rows", "Find rows by condition", {"column": {"type": "string"}, "operator": {
        "type": "string", "enum": ["equals", "contains", "regex", "empty", "not_empty"]},
        "value": {"type": "string"}}, ["column", "operator"]),
    _T("compare_with_previous", "Compare with the previous delivery", {}, []),
]
SYSTEM_PROMPT = """You are a Data QA analyst for a scraped dm Austria price file.
You get the list of issues. Use the tools to look at real rows and find the ROOT CAUSE of each issue.
Use only facts from the tools. Max 8 tool calls. Answer in plain text, one short line per issue, no paragraphs:
VERDICT: Deliver | Fix and re-run
1. <issue> -> <root cause> -> <fix>   (SCRAPER BUG | SOURCE DATA | RULE TOO STRICT)
"""
 
 
def llm(messages, tools):
    body = {"model": OLLAMA_MODEL, "messages": messages, "stream": False, "think": False,
            "options": {"temperature": 0, "num_ctx": OLLAMA_CONTEXT}}
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        msg = json.loads(resp.read())["message"]
    calls = [(c["function"]["name"], c["function"].get("arguments") or {}) for c in msg.get("tool_calls") or []]
    calls = [(n, json.loads(a) if isinstance(a, str) else a) for n, a in calls]
    return re.sub(r"<think>.*?</think>", "", msg.get("content") or "", flags=re.S).strip(), calls, msg
 
 
def run_ai():
    summary = [{"section": t, "issue": i["text"], "count": i["count"],
                "example_rows": list(i["found"]["row"].head(5)) if i["found"] is not None else []}
               for t, i in FAILED]
    msgs = [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"File {FILE.name}, {N} rows. Issues:\n{_j(summary, 8000)}"}]
    for _ in range(AI_MAX_STEPS):
        text, calls, raw = llm(msgs, TOOL_SCHEMAS)
        msgs.append(raw)
        if not calls:
            return text
        for name, args in calls:
            try:
                res = TOOLS[name](**args)
            except Exception as e:
                res = _j({"error": str(e)})
            print(f"   🔧 {name}({json.dumps(args, ensure_ascii=False)[:70]})")
            msgs.append({"role": "tool", "tool_name": name, "content": res})
    msgs.append({"role": "user", "content": "Write the final answer now."})
    return llm(msgs, None)[0]
 
 
if USE_AI_AGENT and FAILED:
    try:
        print("🤖 AI agent investigating ...")
        AI_TEXT = run_ai()
        ai_path = OUT_DIR / f"{FILE.stem}_AI_Analysis.txt"
        ai_path.write_text(f"AI ROOT-CAUSE ANALYSIS (suggestion — verify)\n{FILE.name}\n\n{AI_TEXT}\n", encoding="utf-8")
        print(AI_TEXT, f"\n🤖 {ai_path}")
    except Exception as e:
        print(f"ℹ️ AI agent skipped (Ollama not running: {type(e).__name__}). Rule report is complete.")
 

