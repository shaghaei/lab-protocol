# Digital Lab Protocol

Lab protocols, checked at the bench. A web app that digitises the paper-based protocol of a basic
chemistry practical (Grundpraktikum): students enter their measurements in a validated form, the app
calculates the result, compares it with every group in the course and points to likely errors before
the group leaves the lab.

> Portfolio project · digital transformation and documentation · synthetic demo data only
>
> 
https://github.com/user-attachments/assets/25a562ac-522f-40e9-90e7-fbf8cd8d7ce0



## The problem

On paper, errors in calculation or units surface only when the written report is corrected, about a
week after the measurement. The assistant's signature (Testat) confirms that a group measured, not
that the values are right, and the data of a whole course is lost at the end of the semester.
The full as-is / to-be analysis is in [docs/process.md](docs/process.md).

## What the app does

| Step | Paper process | Digital process |
| --- | --- | --- |
| Entry | Handwritten table, later retyped | Validated form: units, ranges, swapped readings, mg vs g |
| Calculation | By hand, per group | c(NaOH), factor f, mean and RSD computed automatically |
| Integrity | Values can be changed later | Values locked on submit, with timestamp |
| Comparison | None during the lab | Group result against all groups and against its station |
| Diagnosis | Found at report correction | Rule-based findings with likely causes, each naming its rule |
| Equipment | Faulty devices go unnoticed | Station view flags stations whose groups deviate together |
| Archive | Lost after the semester | CSV export of all data |

## First experiment

Titer determination of 0.1 mol/L NaOH against potassium hydrogen phthalate (KHP), three titrations per
group. Specification and error catalog: [docs/experiment-naoh.md](docs/experiment-naoh.md).

## Run it

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000. On first start the app loads a synthetic class of 30 groups at 6 stations.
Delete `data/lab.db` to start fresh.

```bash
pytest                              # 19 tests: calculation, analysis, web pages
python scripts/evaluate.py          # checks against the ground truth of the synthetic class
python scripts/generate_synthetic.py  # writes the synthetic class to data/*.csv
```

## Evaluation (synthetic class, seed 42)

| Metric | Result |
| --- | --- |
| Groups with an injected error detected | 12 / 12 |
| False alarms on clean groups | 0 / 18 |
| Right cause named first | 12 / 12 |

Injected errors: endpoint overshoot (3 groups), burette not rinsed (1), undried standard (2), a
swapped-digit typo (1), and a balance at station 4 that reads 5 mg too high (5 groups). The same result
holds for seeds 1, 2, 3, 7 and 99.

**Limitation:** the errors are injected by the same author who wrote the checks, so these numbers show
that the checks work as designed, not how they perform on real data. Next steps: subtler errors (for
example a 0.1 mL overshoot) and a validation with anonymised real protocols.

## How it is built

- **Stack:** Python, FastAPI, Jinja2 templates, SQLite. Charts are server-rendered SVG.
- **Privacy by design:** no names (group codes only), no cookies, no tracking, no external fonts or
  scripts.
- **Explainable checks:** robust statistics (median and MAD), a station test, and a typo check that
  tests whether swapping two digits makes a titration agree with the others. No AI model in v0.1.
- **Feedback, not grading:** the app never decides a Testat.

```
app/
  experiments.py   experiment definitions (quantities, units, ranges, constants)
  calc.py          validation and calculation (pure functions)
  analysis.py      class statistics, findings, likely causes
  charts.py        SVG strip charts
  db.py            SQLite storage, locked on submit
  synthetic.py     seeded synthetic class with ground-truth labels
  main.py          routes
docs/              process analysis, experiment specification, decisions
scripts/           data generation and evaluation
tests/             pytest suite
```

Design decisions are recorded in [docs/decisions.md](docs/decisions.md).

## Roadmap

- [ ] Photo of the handwritten table, read by AI and confirmed by the student
- [ ] AI explanation of findings, grounded in the rule results and labelled as AI
- [ ] Second experiment: acetic acid in vinegar, using the factor from this one
- [ ] Usability test (SUS) and a time comparison paper vs. digital

## Disclaimer

Software demo with synthetic data. Not an official lab instruction: experiments are carried out only
under supervision and according to the safety data sheets.

## License

MIT
