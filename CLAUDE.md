# CLAUDE.md – project guide for AI coding assistants

## Goal
Digitise the paper-based lab protocol of a basic chemistry practical (Grundpraktikum).
Students enter measurements in a validated digital form; the app calculates the result,
compares it with all groups and flags likely errors. Portfolio project with a focus on
digital transformation and documentation.

## Scope (v0.1)
- One experiment: titer (factor) determination of ~0.1 mol/L NaOH against KHP.
- Synthetic data only. No real student data, no names, no logins.
- Feedback only: the app never grades and never decides a Testat.
- No AI/LLM calls yet; likely causes come from a rule-based catalog.

## Stack
- Python 3.11+, FastAPI, Jinja2 templates, SQLite via the standard `sqlite3` module.
- Charts are server-rendered SVG. No external CDNs, fonts or trackers (privacy by design).
- Tests: pytest.

## Layout
- `app/experiments.py` – experiment definitions (quantities, units, plausible ranges, constants)
- `app/calc.py` – validation and calculation (pure functions, fully tested)
- `app/analysis.py` – class statistics, outlier flags, station analysis, cause catalog
- `app/charts.py` – SVG charts
- `app/db.py` – SQLite access
- `app/main.py` – routes
- `scripts/generate_synthetic.py` – seeded synthetic data with ground-truth labels
- `docs/` – process analysis, experiment specification, decisions

## Conventions
- Units are part of every name: `mass_g`, `volume_ml`, `conc_mol_l`.
- Pure functions in `calc.py` and `analysis.py`; no I/O there.
- Every change to calculation or analysis comes with a test.
- Text in the app and docs is our own wording; sources are linked, never copied.
- Run `pytest` before every commit.
