# Lab Protocol

Lab protocols, checked at the bench. A web app that digitises the paper protocol of basic chemistry
practicals (Grundpraktikum): students enter their measurements in a validated form, the app calculates
the result, compares it with every group in the course and points to likely errors before the group
leaves the lab. Teachers create password-protected courses in which long experiments run as a chain
of steps, and they can add their own experiments in a builder, without writing code.

> Portfolio project · digital transformation and documentation · synthetic demo data only

https://github.com/user-attachments/assets/25a562ac-522f-40e9-90e7-fbf8cd8d7ce0

## The problem

On paper, errors in calculation or units surface only when the written report is corrected, about a
week after the measurement. The assistant's signature (Testat) confirms that a group measured, not
that the values are right, and the data of a whole course is lost at the end of the semester.
The as-is / to-be analysis is in [docs/process.md](docs/process.md).

## What the app does

| Step | Paper process | Digital process |
| --- | --- | --- |
| Entry | Handwritten table, later retyped | Validated form: ranges, unit mix-ups (mg vs g), swapped readings |
| Calculation | By hand, per group | Result per run, mean and RSD from the experiment's formula |
| Integrity | Values can be changed later | Values locked on submit, with timestamp |
| Comparison | None during the lab | Group result against all groups and against its station |
| Diagnosis | Found at report correction | Rule-based findings with likely causes, each naming its rule |
| Equipment | Faulty devices go unnoticed | Station view flags stations whose groups deviate together |
| New experiments | New paper form | Builder: quantities, units, formula, checks and causes |
| Long experiments | Results passed on by hand between groups | Chained steps: a step takes the class result of an earlier step |
| Archive | Lost after the semester | CSV export per experiment |

## Experiments

| Experiment | Category | Result | Runs |
| --- | --- | --- | --- |
| Titer of 0.1 mol/L sodium hydroxide | Titration | factor f | 3 |
| Acetic acid in vinegar | Titration | β in g/L | 3 |
| Calibration of a 10 mL volumetric pipette | Calibration | V in mL | 5 |
| Water of crystallization in copper sulfate | Gravimetry | x in mol/mol | 2 |
| Molar volume of hydrogen | Gas laws | Vm in L/mol | 3 |

Definitions, error catalogs and sources: [docs/experiments.md](docs/experiments.md).

### Create your own

The builder (Create experiment) starts from a template or from scratch. You define the measured
quantities with units, ranges and decimals, constants, the result formula, the expected result, rules
such as `V_end > V_start`, and the likely causes for results that are too low or too high. A test with
example values runs before saving. Formulas are parsed against a whitelist (numbers, symbols,
`+ - * / ^`, a few math functions), so they cannot run code.

## Courses and chained steps

A teacher creates a course with a number of groups and two passwords: a teacher password and a class
password. Students join with the course code and the class password; they see every group's results in
the course and enter the values of their own group. The teacher adds steps, each one experiment done by
some of the groups. A step can take a value from an earlier step: in the demo course, groups G01 to G06
determine the factor of the NaOH solution, and groups G07 to G12 titrate vinegar with that solution; the
class median of step 1 is filled in for them and stored with each run. The teacher can delete a wrong
entry so the group can enter it again.

Demo course: code `demo-acid-base`, class password `demo-class`, teacher password `demo-teacher`.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000. On first start the app loads a synthetic class of 30 groups at 6 stations for
each built-in experiment and the demo course. Delete `data/lab_v3.db` to start fresh. Python 3.11 or newer.

```bash
pytest                     # 56 tests: formulas, calculation, analysis, pages, builder, courses
python scripts/evaluate.py # checks against the ground truth of the synthetic classes
```

## Evaluation

Each synthetic class carries injected errors with a known direction (for example an overshot endpoint,
an undried standard, a gas leak), one swapped-digit typo where the method allows three runs, and one
station with faulty equipment.

| Synthetic classes | Injected errors detected | False alarms on clean groups | Right direction or cause |
| --- | --- | --- | --- |
| Seed 42 (default), 5 experiments | 52 / 52 | 0 / 98 | 52 / 52 |
| Six seeds together | 312 / 312 | 4 / 588 | 308 / 312 |

**Limitations:** the errors are injected by the same author who wrote the checks, and three limits
were tuned after a first evaluation on seed 42. The numbers show that the checks work as designed; they
do not show how they perform on real protocols. Next step: validation with anonymised real data.

## How it is built

- **Stack:** Python, FastAPI, Jinja2 templates, SQLite. Charts are server-rendered SVG.
- **Privacy by design:** group codes instead of names, no tracking; fonts (IBM Plex, OFL) are served by
  the app itself. The only cookie is a signed session cookie for course access.
- **Security:** passwords stored as salted PBKDF2 hashes; the session cookie is signed with HMAC; both
  use only the Python standard library.
- **Explainable checks:** median and MAD for the class reference, a station test, and a typo check that
  tests whether swapping two digits of one value makes a run agree with the others. No AI model yet.
- **Feedback, not grading:** the app never decides a Testat.

```
app/
  experiments.py   experiment model and the five built-ins
  formula.py       safe formula evaluation (AST whitelist)
  builder.py       builder form <-> experiment definition
  auth.py          password hashing and the signed session cookie
  chain.py         values passed from one course step to the next
  demo_course.py   the ready-made demo course
  calc.py          validation and calculation
  analysis.py      class statistics, findings, likely causes
  charts.py        SVG strip charts
  synthetic.py     seeded synthetic classes with ground-truth labels
  db.py            SQLite: custom experiments, courses, steps, submissions (locked on submit)
  main.py          routes
docs/              process analysis, experiments, decisions
scripts/           evaluation
tests/             pytest suite
```

Design decisions: [docs/decisions.md](docs/decisions.md).

## Roadmap

- [ ] Photo of the handwritten table, read by AI and confirmed by the student
- [ ] AI explanation of findings, grounded in the rule results and labelled as AI
- [ ] Teacher password before custom experiments can be created or deleted
- [ ] Limit password attempts per course
- [ ] Usability test (SUS) and a time comparison paper vs. digital

## Disclaimer

Software demo with synthetic data. Not an official lab instruction: experiments are carried out only
under supervision and according to the safety data sheets.

## License

Code: MIT. Typeface IBM Plex: SIL Open Font License (`app/static/fonts/OFL-LICENSE.txt`).
