# Part Finder — TVS Parts Catalogue Lookup

A small web app that indexes the TVS Motor "PARTS CATALOGUE" PDFs in
`testdata/` and lets you look up an exact part number by vehicle, variant,
and part name (with autocomplete).

## What it does

1. `extract_parts.py` scans every PDF in `testdata/` and parses each parts
   table (Ref No / Part No / Description / Remarks) into `parts_index.json`.
   For every part it records:
   - `vehicle` — derived from the PDF's filename (e.g. "Ntorq", "Rtr 160 2V")
   - `version` — the variant/version line printed on the catalogue's cover
     page (e.g. "BSIV / BSVI / OBDIIA / OBDIIB"). **Note:** these PDFs do not
     print an actual model *year* anywhere — "version" (emission stage /
     trim variant) is the closest real field in the source data, so that's
     what the app uses instead of a year.
   - `section` — the assembly/figure the part belongs to (e.g. "CYLINDER
     HEAD ASSEMBLY")
   - `part_number`, `part_name`, `remarks`, `qty`, `source_file`, `page`

2. `app.py` is a Flask app that serves the UI and a small JSON API:
   - `GET /api/vehicles` — list of vehicles
   - `GET /api/versions?vehicle=X` — variant tags available for that vehicle
   - `GET /api/suggest?vehicle=X&version=Y&q=partial` — part-name
     autocomplete suggestions
   - `GET /api/part?vehicle=X&version=Y&name=exact` — the part number(s)
     matching that name
   - `POST /api/refresh` — reload `parts_index.json` from disk

3. The UI (`templates/index.html`, `static/`) is a single page: pick a
   vehicle, optionally narrow by variant, then type a part name — matching
   names appear as you type, and selecting one shows its part number.

## Running it

```bash
pip install -r requirements.txt
python extract_parts.py      # (re)builds parts_index.json from testdata/
python app.py                 # starts the app on http://127.0.0.1:5000
```

If you add or replace PDFs in `testdata/`, re-run `extract_parts.py` (or
`POST /api/refresh` after updating `parts_index.json`) to refresh the index.

## Known limitations

- Extraction uses layout heuristics on `pypdf`'s text output, since these
  catalogues have no embedded structured data — a small fraction of rows
  (roughly parts with unusual formatting) may have a slightly off name or
  missing remarks. Numbers/part codes are matched precisely though.
- There's no true "model year" in the source PDFs — see the `version` note
  above.
