"""
Vehicle Part Lookup

Serves a small UI + JSON API backed by parts_index.json (built by
extract_parts.py from the PDF catalogues in testdata/).

Flow the UI drives:
  1) GET /api/vehicles                -> list of vehicle names
  2) GET /api/versions?vehicle=X      -> list of variant/version tags for X
  3) GET /api/suggest?vehicle=X&version=Y&q=partial
       -> part-name suggestions (for the autocomplete-as-you-type box)
  4) GET /api/part?vehicle=X&version=Y&name=exact_part_name
       -> the matching part number(s) + details
"""
import os
import re
import json
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, static_folder="public", static_url_path="")
APP_ROOT = os.path.dirname(__file__)
INDEX_PATH = os.path.join(APP_ROOT, "parts_index.json")

PARTS = []                 # full list of part rows
VEHICLES = []               # sorted vehicle names
VEHICLE_VERSIONS = {}       # vehicle -> sorted list of version tags
VEHICLE_PARTS = {}          # vehicle -> list of part rows (for fast lookup)

TAG_SPLIT_RE = re.compile(r"[/,]")
TAG_CLEAN_RE = re.compile(r"\s+")


def derive_tags(version_str: str):
    tags = []
    for raw in TAG_SPLIT_RE.split(version_str or ""):
        t = TAG_CLEAN_RE.sub(" ", raw).strip(" .-")
        if t and len(t) <= 40:
            tags.append(t)
    return tags


def load_index():
    global PARTS, VEHICLES, VEHICLE_VERSIONS, VEHICLE_PARTS
    if not os.path.exists(INDEX_PATH):
        PARTS = []
        return
    with open(INDEX_PATH, "r", encoding="utf-8") as fh:
        PARTS = json.load(fh)

    veh_set = set()
    veh_versions = {}
    veh_parts = {}
    for p in PARTS:
        v = p.get("vehicle", "").strip()
        if not v:
            continue
        veh_set.add(v)
        veh_parts.setdefault(v, []).append(p)
        tags = derive_tags(p.get("version", ""))
        s = veh_versions.setdefault(v, set())
        for t in tags:
            s.add(t)

    VEHICLES = sorted(veh_set)
    VEHICLE_VERSIONS = {v: sorted(s) for v, s in veh_versions.items()}
    VEHICLE_PARTS = veh_parts
    print(f"Loaded {len(PARTS)} parts across {len(VEHICLES)} vehicles")


load_index()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/vehicles")
def api_vehicles():
    return jsonify(VEHICLES)


@app.route("/api/versions")
def api_versions():
    vehicle = request.args.get("vehicle", "").strip()
    return jsonify(VEHICLE_VERSIONS.get(vehicle, []))


def _row_matches_version(row, version):
    if not version or version == "Any":
        return True
    haystack = f"{row.get('version','')} {row.get('remarks','')}".lower()
    return version.lower() in haystack


@app.route("/api/suggest")
def api_suggest():
    """Part-name suggestions as the user types, scoped to a vehicle
    (and optional version), used to power the autocomplete input."""
    vehicle = request.args.get("vehicle", "").strip()
    version = request.args.get("version", "Any").strip()
    q = request.args.get("q", "").strip().lower()
    try:
        limit = max(1, min(int(request.args.get("limit", 15)), 50))
    except ValueError:
        limit = 15

    if not vehicle or vehicle not in VEHICLE_PARTS:
        return jsonify([])

    rows = VEHICLE_PARTS[vehicle]
    seen = set()
    starts_with = []
    contains = []
    for r in rows:
        name = r.get("part_name", "")
        if not name:
            continue
        nl = name.lower()
        if q and q not in nl:
            continue
        if not _row_matches_version(r, version):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        entry = {"name": name}
        if q and nl.startswith(q):
            starts_with.append(entry)
        else:
            contains.append(entry)
        if len(seen) >= limit * 4:
            break

    ordered = starts_with + contains
    ordered.sort(key=lambda e: (len(e["name"]), e["name"]))
    return jsonify(ordered[:limit])


@app.route("/api/part")
def api_part():
    """Return all matching rows (part number + details) for an exact
    (or best-effort partial) part name within a vehicle/version scope."""
    vehicle = request.args.get("vehicle", "").strip()
    version = request.args.get("version", "Any").strip()
    name = request.args.get("name", "").strip().lower()

    if not vehicle or vehicle not in VEHICLE_PARTS or not name:
        return jsonify([])

    results = []
    for r in VEHICLE_PARTS[vehicle]:
        if r.get("part_name", "").lower() != name:
            continue
        if not _row_matches_version(r, version):
            continue
        results.append({
            "part_number": r.get("part_number", ""),
            "part_name": r.get("part_name", ""),
            "vehicle": r.get("vehicle", ""),
            "version": r.get("version", ""),
            "section": r.get("section", ""),
            "remarks": r.get("remarks", ""),
            "qty": r.get("qty", ""),
            "source_file": r.get("source_file", ""),
            "page": r.get("page", ""),
        })

    # Fallback: if no exact match (rare), do a loose contains match.
    if not results:
        for r in VEHICLE_PARTS[vehicle]:
            if name in r.get("part_name", "").lower() and _row_matches_version(r, version):
                results.append({
                    "part_number": r.get("part_number", ""),
                    "part_name": r.get("part_name", ""),
                    "vehicle": r.get("vehicle", ""),
                    "version": r.get("version", ""),
                    "section": r.get("section", ""),
                    "remarks": r.get("remarks", ""),
                    "qty": r.get("qty", ""),
                    "source_file": r.get("source_file", ""),
                    "page": r.get("page", ""),
                })

    # de-duplicate identical part numbers
    dedup = []
    seen_pn = set()
    for r in results:
        k = (r["part_number"], r["remarks"])
        if k in seen_pn:
            continue
        seen_pn.add(k)
        dedup.append(r)

    return jsonify(dedup[:30])


@app.route("/api/search")
def api_search():
    """Reverse lookup: search across ALL vehicles by part number (or part
    name) when the vehicle isn't known. Matches part_number first (exact,
    then prefix, then contains), falling back to part_name contains."""
    q = request.args.get("q", "").strip()
    try:
        limit = max(1, min(int(request.args.get("limit", 25)), 100))
    except ValueError:
        limit = 25
    if not q or len(q) < 2:
        return jsonify([])

    ql = q.lower()
    exact, prefix, contains, name_hits = [], [], [], []
    seen = set()

    for r in PARTS:
        pn = (r.get("part_number") or "").lower()
        nm = (r.get("part_name") or "").lower()
        key = (pn, nm, r.get("vehicle"), r.get("source_file"), r.get("page"))
        if key in seen:
            continue

        bucket = None
        if pn and pn != "---":
            if pn == ql:
                bucket = exact
            elif pn.startswith(ql):
                bucket = prefix
            elif ql in pn:
                bucket = contains
        if bucket is None and ql in nm:
            bucket = name_hits

        if bucket is not None:
            seen.add(key)
            bucket.append({
                "part_number": r.get("part_number", ""),
                "part_name": r.get("part_name", ""),
                "vehicle": r.get("vehicle", ""),
                "version": r.get("version", ""),
                "section": r.get("section", ""),
                "remarks": r.get("remarks", ""),
                "source_file": r.get("source_file", ""),
                "page": r.get("page", ""),
            })

        if len(exact) + len(prefix) + len(contains) + len(name_hits) >= limit * 4:
            break

    ordered = exact + prefix + contains + name_hits
    return jsonify(ordered[:limit])


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """Reload parts_index.json from disk (e.g. after re-running extract_parts.py)."""
    load_index()
    return jsonify({"vehicles": len(VEHICLES), "parts": len(PARTS)})


if __name__ == "__main__":
    app.run(debug=False, port=5000)
