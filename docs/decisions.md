# Architecture decision records

## ADR-001: Server-rendered pages instead of a JavaScript framework
- **Context:** a small form-and-report app; the main audience is a lab with mixed devices.
- **Decision:** FastAPI with Jinja2 templates; charts rendered as SVG on the server.
- **Consequences:** no build step, works without JavaScript, nothing loaded from third parties.
  Interactive charts would need a client library later.

## ADR-002: SQLite with the standard library
- **Context:** one course, a few hundred rows per semester.
- **Decision:** SQLite through `sqlite3`, no ORM.
- **Consequences:** zero setup and one file to back up. A move to PostgreSQL needs a small data layer change.

## ADR-003: Values are locked on submit
- **Context:** a group could otherwise adjust its values after seeing the class.
- **Decision:** no update path; the comparison is shown only after the values are stored with a timestamp.
- **Consequences:** a typo needs a new entry approved by the assistant (not built yet).

## ADR-004: Robust statistics for the class reference
- **Context:** a few wrong values would shift a mean and a standard deviation.
- **Decision:** median and median absolute deviation (scaled by 1.4826), with a minimum spread of
  0.003 in f so a very tight class does not flag every small difference.
- **Consequences:** stable reference with outliers present; needs at least 5 groups.

## ADR-005: Rule-based findings before AI
- **Context:** findings must be explainable to students and assistants, and the app must not grade.
- **Decision:** v0.1 uses deterministic rules only; each finding names its rule. A later AI layer may
  explain findings in plain language, grounded in the rule results and labelled as AI.
- **Consequences:** fully testable and reproducible; limited to the errors in the catalog.

## ADR-006: Pseudonymous group codes, no personal data
- **Context:** GDPR (DSGVO) and a public demo.
- **Decision:** groups are identified by codes like G31; the demo uses synthetic data only.
- **Consequences:** no consent or processing agreements needed for the demo. A real pilot would run on
  university infrastructure under its data protection rules.

## ADR-007: Experiments as data, formulas through a whitelist
- **Context:** lecturers should add experiments without writing code, and a formula typed into a web
  form must never be executed as code.
- **Decision:** an experiment is a data structure (quantities, constants, formula, rules, causes). The
  formula is parsed with Python's `ast` module and only numbers, known symbols, `+ - * / ^` and a few
  math functions are accepted; exponents must be constants between -10 and 10.
- **Consequences:** the same checks work for every experiment. Formulas cannot branch or use tables;
  methods that need that remain code.

## ADR-008: Built-in experiments live in code
- **Context:** corrections to a built-in experiment should reach every installation.
- **Decision:** built-ins are defined in `app/experiments.py`; only custom experiments are stored in
  SQLite. Built-ins cannot be deleted; "Copy and edit" creates a custom version.
- **Consequences:** a changed built-in applies at the next start. Results stored with an old version
  are recalculated with the new definition.

## ADR-009: Typo check limits scale with the method's noise
- **Context:** with a fixed 1 % trigger, noisy methods (gas volumes) produced typo suspicions from
  ordinary scatter.
- **Decision:** only the run furthest from the group median is tested; it must deviate by at least
  max(1 %, 2 × allowed RSD) and agree within max(0.3 %, allowed RSD / 2) after the swap.
- **Consequences:** no false typo findings in the default synthetic classes; a typo smaller than twice
  the allowed RSD is not detected.

## ADR-010: Courses with two shared passwords instead of user accounts
- **Context:** a practical has one teacher and many groups; individual accounts would mean registration,
  personal data and password resets.
- **Decision:** a course has a teacher password and a class password, stored as salted PBKDF2 hashes. A
  signed session cookie (HMAC, standard library) remembers which courses a browser may open and in which
  role. Groups pick their group code from the step's list.
- **Consequences:** no personal data and no registration. The class password does not prove which group
  someone belongs to: a student could enter values for another group. Each group can submit once, and the
  teacher can delete a wrong entry.

## ADR-011: Chained steps pass on the class median
- **Context:** in long experiments, later groups need a value that earlier groups measured, for example
  the NaOH factor for the vinegar titration.
- **Decision:** a step can link any of its quantities to an earlier step. At submission, the earlier
  step's class median is filled in and stored with each run.
- **Consequences:** one outlying group cannot spoil the chain, and results stay reproducible. A later
  correction in the earlier step does not change runs that were already submitted.
