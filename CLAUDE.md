# CLAUDE.md – project guide for AI coding assistants

## Goal
Digitise the paper-based lab protocol of a basic chemistry practical (Grundpraktikum).
Students enter measurements in a validated digital form; the app calculates the result,
compares it with all groups and flags likely errors. Portfolio project with a focus on
digital transformation and documentation.

## Scope (v0.4)
- Five built-in experiments (app/experiments.py) plus a builder for custom experiments.
- Courses with teacher and class passwords; long experiments as chained steps (app/chain.py).
- Synthetic data only. No real student data, no names, no logins.
- Feedback only: the app never grades and never decides a Testat.
- No AI/LLM calls yet; likely causes come from a rule-based catalog.

## Stack
- Python 3.11+, FastAPI, Jinja2 templates, SQLite via the standard `sqlite3` module.
- Charts are server-rendered SVG. Fonts (IBM Plex, OFL) are self-hosted. No CDNs or trackers.
- Built-in experiments live in code; only custom experiments are stored in SQLite as JSON.
- Tests: pytest.

## Layout
- `app/experiments.py` – experiment model and the five built-ins (quantities, constants, formula, causes)
- `app/formula.py` – safe evaluation of result formulas (AST whitelist, no eval)
- `app/builder.py` – builder form <-> experiment definition
- `app/calc.py` – validation and calculation (pure functions, fully tested)
- `app/analysis.py` – class statistics, outlier flags, station analysis, cause catalog
- `app/charts.py` – SVG charts
- `app/db.py` – SQLite access
- `app/main.py` – routes
- `app/synthetic.py` – seeded synthetic classes with ground-truth labels
- `scripts/evaluate.py` – checks against the ground truth
- `docs/` – process analysis, experiment specification, decisions

## Conventions
- Units are part of every name: `mass_g`, `volume_ml`, `conc_mol_l`.
- Pure functions in `calc.py` and `analysis.py`; no I/O there.
- Every change to calculation or analysis comes with a test.
- Text in the app and docs is our own wording; sources are linked, never copied.
- Run `pytest` before every commit.
