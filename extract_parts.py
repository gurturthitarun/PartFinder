"""
Extract vehicle / part information from the PDF catalogues in testdata/ and
write a single parts_index.json used by the web app.

Each source PDF is a TVS Motor "PARTS CATALOGUE" — a table per assembly with
columns:  REF NO | PART NO | DESCRIPTION | (model qty columns) | REMARKS

There is no explicit "model year" printed in these documents. What IS present
is a per-document "version" line on the cover page (e.g. "BSIV / BSVI /
OBDIIA / OBDIIB") describing engine/emission variants the catalogue covers,
plus per-row remarks (e.g. "BSIV", "OBDIIB") showing which variant a specific
part applies to. We capture both.

Run: python extract_parts.py
"""
import os
import re
import json
from pypdf import PdfReader

ROOT = os.path.dirname(__file__)
TESTDATA = os.path.join(ROOT, "testdata")
OUT = os.path.join(ROOT, "parts_index.json")

REF_RE = re.compile(r"^\d{1,3}[A-Z]?$")
PARTNO_RE = re.compile(r"^(---|[A-Z0-9]{5,15})$")
FIGNO_RE = re.compile(r"FIG\.?\s*NO\.?\s*(\d+)\s+(.+?)\s+FIG\.?\s*NO\.?\s*\d+", re.IGNORECASE)
PUREDIGIT_RE = re.compile(r"^\d+$")
CATALOGUE_RE = re.compile(r"PARTS\s+CATALOGUE", re.IGNORECASE)


def clean_vehicle_name(filename: str) -> str:
    name = os.path.splitext(filename)[0]
    name = name.replace("_", " ")
    name = re.sub(r"\(\s*\d+\s*\)", "", name)  # drop "(2)" style suffixes
    name = re.sub(r"[-\s]*OBD[\s-]*2[A-Z]?\b", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\bCatalogue\b", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+", " ", name).strip(" -")
    return name.title() if name.isupper() else name.strip()


def extract_version_line(first_page_text: str) -> str:
    """The cover page has a 'PARTS CATALOGUE' line plus a nearby line of
    slash-separated variant codes (BSIV / BSVI / OBDIIA / OBDIIB, etc.)."""
    lines = [ln.strip() for ln in first_page_text.splitlines() if ln.strip()]
    variant_lines = []
    for ln in lines:
        if CATALOGUE_RE.search(ln):
            continue
        if "TVS MOTOR" in ln.upper():
            continue
        if "/" in ln or re.search(r"OBDII|BS[IV46]|GEN\d", ln, re.IGNORECASE):
            variant_lines.append(ln)
    combined = " ".join(variant_lines)
    combined = re.sub(r"\s+", " ", combined).strip(" /-")
    return combined


def parse_row(line: str):
    """Try to parse one table row into ref/part_number/description/qty/remarks."""
    tokens = line.split()
    if len(tokens) < 3:
        return None
    if not REF_RE.match(tokens[0]):
        return None
    if not PARTNO_RE.match(tokens[1]):
        return None
    ref_no, part_no = tokens[0], tokens[1]
    rest = tokens[2:]
    if not rest:
        return None

    qty_idx = None
    for i, tok in enumerate(rest):
        if PUREDIGIT_RE.match(tok):
            qty_idx = i
            break

    if qty_idx is not None:
        desc_tokens = rest[:qty_idx]
        qty = rest[qty_idx]
        remarks = " ".join(rest[qty_idx + 1:])
    else:
        desc_tokens = rest
        qty = ""
        remarks = ""

    description = " ".join(desc_tokens).strip(" -")
    if len(description) < 3:
        return None
    if part_no == "---" and qty == "" and not remarks:
        # too little signal to be useful
        return None

    return {
        "ref_no": ref_no,
        "part_number": part_no,
        "part_name": description,
        "qty": qty,
        "remarks": remarks,
    }


def extract_from_pdf(path: str, filename: str):
    reader = PdfReader(path)
    if not reader.pages:
        return []
    vehicle = clean_vehicle_name(filename)
    first_page_text = reader.pages[0].extract_text() or ""
    doc_version = extract_version_line(first_page_text)

    entries = []
    current_section = ""
    seen = set()

    for pnum, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            continue
        if not text.strip():
            continue
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for ln in lines:
            m = FIGNO_RE.search(ln)
            if m:
                current_section = m.group(2).strip()
                continue
            row = parse_row(ln)
            if not row:
                continue
            key = (row["part_number"], row["part_name"], filename, pnum)
            if key in seen:
                continue
            seen.add(key)
            entries.append({
                "vehicle": vehicle,
                "version": doc_version,
                "section": current_section,
                "ref_no": row["ref_no"],
                "part_number": row["part_number"],
                "part_name": row["part_name"],
                "qty": row["qty"],
                "remarks": row["remarks"],
                "source_file": filename,
                "page": pnum,
            })
    return entries


def main():
    import sys
    if not os.path.isdir(TESTDATA):
        print("No testdata/ folder found at", TESTDATA)
        return
    files = sorted(f for f in os.listdir(TESTDATA) if f.lower().endswith(".pdf"))

    # Optional CLI args let us process a slice of files at a time, merging
    # results into the existing parts_index.json (used to stay under
    # per-command time limits in this sandbox).
    if len(sys.argv) >= 3:
        start, end = int(sys.argv[1]), int(sys.argv[2])
        files = files[start:end]
        existing = []
        if os.path.exists(OUT):
            with open(OUT, "r", encoding="utf-8") as fh:
                existing = json.load(fh)
    else:
        existing = []

    print(f"Processing {len(files)} PDF files: {files}")

    all_entries = existing
    for fname in files:
        path = os.path.join(TESTDATA, fname)
        try:
            entries = extract_from_pdf(path, fname)
        except Exception as e:
            print(f"  ERROR reading {fname}: {e}")
            continue
        print(f"  {fname}: {len(entries)} parts")
        all_entries.extend(entries)

    print(f"\nTotal parts in index now: {len(all_entries)}")
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(all_entries, fh, indent=2, ensure_ascii=False)
    print("Wrote", OUT)


if __name__ == "__main__":
    main()
