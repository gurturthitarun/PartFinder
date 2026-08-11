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

## Running it locally

```bash
pip install -r requirements.txt
python app.py                 # starts the app on http://127.0.0.1:5000
```

`parts_index.json` ships pre-built, so you don't need `testdata/` or
`pypdf` just to run the app. Only install `requirements-dev.txt` and keep
`testdata/` around if you want to regenerate the index:

```bash
pip install -r requirements-dev.txt
python extract_parts.py       # rebuilds parts_index.json from testdata/
```

## Deploying to Vercel

This project is already structured the way Vercel expects for Flask:

- `app.py` at the repo root exports a Flask instance named `app` — Vercel
  auto-detects this as the entrypoint.
- Static assets (`style.css`, `app.js`) live in `public/`, not `static/`.
  Flask's own `static/` folder isn't served on Vercel, so `app.py` points
  `static_folder` at `public/` with an empty URL prefix — that's what makes
  `/style.css` and `/app.js` resolve correctly both locally and on Vercel.
- `vercel.json` sets a `maxDuration` for the function.
- `requirements.txt` only lists what's needed at runtime (`Flask`) — kept
  minimal since `pypdf` is only needed offline, to rebuild the index.

Steps:

1. **Push this folder to GitHub** as its own repo (or the root of a repo).
   Do **not** commit `testdata/` — the PDFs aren't needed at runtime and
   would bloat the deployment; `parts_index.json` already has everything
   the app needs. `.gitignore` is included for the usual Python cruft.
2. **Import the repo in Vercel** (New Project → import from GitHub).
3. Vercel should auto-detect it as a Python/Flask project from `app.py`
   and `requirements.txt`. You shouldn't need to change any build/output
   settings — leave the framework preset on its default/auto-detected
   value.
4. Deploy. Once it's live, check:
   - `/` loads the UI
   - `/style.css` and `/app.js` return 200 (open them directly in the
     browser) — if either 404s, double check they exist under `public/`
     in the repo you pushed
   - `/api/vehicles` returns the JSON list of vehicles

### If you still get a 404 after this

- Make sure `app.py`, `requirements.txt`, `vercel.json`, `public/`, and
  `templates/` are all at the **root** of the GitHub repo Vercel imported
  (not nested inside an extra subfolder like `pdf_part_lookup/`). If your
  repo has everything inside a subfolder, set that subfolder as the
  **Root Directory** in the Vercel project's Settings → General.
- In the Vercel dashboard, check the deployment's **Build Logs** and
  **Function Logs** — a Python import error there (e.g. a missing
  dependency) will also surface as a 404/500 on every route.
- Confirm `requirements.txt` is present and lists `Flask` — without it,
  Vercel won't recognize the project as a Python app at all.

## Known limitations

- Extraction uses layout heuristics on `pypdf`'s text output, since these
  catalogues have no embedded structured data — a small fraction of rows
  (roughly parts with unusual formatting) may have a slightly off name or
  missing remarks. Numbers/part codes are matched precisely though.
- There's no true "model year" in the source PDFs — see the `version` note
  above.
