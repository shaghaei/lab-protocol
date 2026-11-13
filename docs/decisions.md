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
