"""FastAPI app: digital lab protocols for basic chemistry experiments.

Two areas share the same pages:
- the open catalog (/e/...): every experiment with a synthetic demo class;
- courses (/c/...): a teacher creates a course, groups join with a shared class
  password, and a long experiment runs as a chain of steps.
"""
import csv
import io
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import auth, builder, chain, db
from .analysis import Z_LIMIT, assess_group, class_stats, fmt, robust_z, station_deviations
from .calc import evaluate_group, validate_run
from .charts import strip_chart
from .experiments import CATEGORIES, TEMPLATES, UNITS

BASE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE / "templates")

KIND_LABELS = {
    "digit_swap": ("Possible typo", "warn"),
    "spread": ("Runs disagree", "warn"),
    "outlier_low": ("Lower than the class", "crit"),
    "outlier_high": ("Higher than the class", "crit"),
    "station": ("Station effect", "warn"),
    "outside_expected": ("Outside the usual range", "info"),
}
GROUP_CODE = re.compile(r"^[A-Za-z0-9-]{2,12}$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.conn = db.connect()
    db.seed(app.state.conn)
    yield
    app.state.conn.close()


app = FastAPI(title="Lab Protocol", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates.env.globals.update(KIND_LABELS=KIND_LABELS, CATEGORIES=CATEGORIES, UNITS=UNITS)
templates.env.filters["fmt"] = lambda v, d: f"{v:.{d}f}"


def conn_of(request: Request):
    return request.app.state.conn


def experiment_or_404(request: Request, eid: str):
    exp = db.get_experiment(conn_of(request), eid)
    if exp is None:
        raise HTTPException(404, "This experiment does not exist.")
    return exp


def page(request, name, **ctx):
    exp = ctx.get("exp")
    if exp is not None and "number" not in ctx:
        ids = [e.id for e in db.list_experiments(conn_of(request))]
        ctx["number"] = ids.index(exp.id) + 1 if exp.id in ids else None
    ctx.setdefault("scope", None)
    return templates.TemplateResponse(request, name, ctx, status_code=ctx.pop("status", 200))


# shared experiment pages -------------------------------------------------------

@dataclass
class Scope:
    """Where an experiment page lives: the open catalog or one step of a course."""
    exp: object
    base: str
    step_id: int = 0
    course: dict | None = None
    step: dict | None = None
    role: str | None = None

    @property
    def teacher(self) -> bool:
        return self.role == "teacher"


def class_view(conn, exp, step_id: int = 0) -> dict:
    """Evaluate every submission of one experiment (in one scope) against the whole class."""
    subs = db.list_submissions(conn, exp.id, step_id)
    for s in subs:
        s["result"] = evaluate_group(s["runs"], exp)
    stats = class_stats([s["result"].mean for s in subs], exp)
    by_station = {}
    for s in subs:
        by_station.setdefault(s["station"], []).append(s["result"].mean)
    stations = station_deviations(by_station, stats) if stats else {}
    for s in subs:
        s["findings"] = assess_group(s["result"], s["station"], stats, stations, exp)
        s["z"] = robust_z(s["result"].mean, stats) if stats else None
    return {"subs": subs, "stats": stats, "stations": stations, "by_station": by_station}


def chart(exp, stats, rows, caption):
    band = (stats.median - Z_LIMIT * stats.spread, stats.median + Z_LIMIT * stats.spread)
    unit = f" [{exp.result_unit}]" if exp.result_unit else ""
    return strip_chart(rows, stats.median, band, stats.spread, caption, exp.result_decimals,
                       f"{exp.result_label}, {exp.result_symbol}{unit}")


def entry_context(conn, sc: Scope) -> dict:
    ctx = {"linked": {}, "open_groups": None}
    if sc.step:
        ctx["linked"] = chain.linked_values(conn, sc.step)
        done = {s["group_code"] for s in db.list_submissions(conn, sc.exp.id, sc.step_id)}
        ctx["open_groups"] = [g for g in sc.step["groups"] if g not in done]
    return ctx


def render_entry(request, sc: Scope, values=None, errors=None, status=200):
    return page(request, "entry.html", exp=sc.exp, scope=sc, tab="new", values=values or {},
                errors=errors or [], status=status, **entry_context(conn_of(request), sc))


async def handle_entry(request: Request, sc: Scope):
    exp, conn = sc.exp, conn_of(request)
    values = dict(await request.form())
    errors = []
    ctx = entry_context(conn, sc)
    code = values.get("group_code", "").strip().upper()
    if sc.step:
        if code not in sc.step["groups"]:
            errors.append("Choose your group from the list.")
        elif code not in ctx["open_groups"]:
            errors.append(f"Group {code} has already submitted for this step. Submitted values are "
                          "locked; ask the teacher if a value must be corrected.")
    elif not GROUP_CODE.match(code):
        errors.append("Group code: use 2 to 12 letters, digits or hyphens, for example G31. No names.")
    elif db.group_exists(conn, exp.id, code):
        errors.append(f"Group {code} has already submitted for this experiment. Submitted values "
                      "are locked; ask the assistant if a value must be corrected.")
    st = builder.num(values.get("station"))
    if st is None or int(st) not in exp.station_numbers:
        errors.append("Choose your lab station.")

    for key, link in ctx["linked"].items():
        if link["value"] is None:
            errors.append(f"{exp.quantity(key).label} comes from step {link['source']['position']}, "
                          "which has no results yet. Wait until a group of that step has submitted.")
    runs = []
    for i in range(1, exp.runs + 1):
        run = {q.key: builder.num(values.get(f"{q.key}_{i}")) for q in exp.quantities}
        for key, link in ctx["linked"].items():
            if link["value"] is not None:
                run[key] = round(link["value"], exp.quantity(key).decimals)
        if not any("comes from step" in e for e in errors):
            errors.extend(validate_run(run, exp, i)[0])
        runs.append(run)
    if errors:
        return render_entry(request, sc, values, errors, 400)
    sid = db.insert_submission(conn, exp.id, code, int(st), runs, step_id=sc.step_id)
    return RedirectResponse(f"/s/{sid}", status_code=303)


def render_class(request, sc: Scope):
    cv = class_view(conn_of(request), sc.exp, sc.step_id)
    svg = None
    if cv["stats"]:
        pts = [(s["group_code"], s["result"].mean, False, bool(s["findings"])) for s in cv["subs"]]
        svg = chart(sc.exp, cv["stats"], [("All groups", pts, False)], "Result of every group")
    subs = sorted(cv["subs"], key=lambda s: (not s["findings"], s["group_code"]))
    return page(request, "class.html", exp=sc.exp, scope=sc, tab="class", subs=subs,
                stats=cv["stats"], chart=svg, fmt=fmt)


def render_stations(request, sc: Scope):
    cv = class_view(conn_of(request), sc.exp, sc.step_id)
    svg, rows = None, []
    if cv["stats"]:
        chart_rows = []
        for station in sorted(cv["by_station"]):
            pts = [(s["group_code"], s["result"].mean, False, bool(s["findings"]))
                   for s in cv["subs"] if s["station"] == station]
            info = cv["stations"].get(station)
            chart_rows.append((f"Station {station}", pts, bool(info and info[2])))
            rows.append({"station": station, "n": len(pts), "info": info})
        svg = chart(sc.exp, cv["stats"], chart_rows, "Results by lab station")
    return page(request, "stations.html", exp=sc.exp, scope=sc, tab="stations", rows=rows,
                stats=cv["stats"], chart=svg, fmt=fmt)


def render_export(request, sc: Scope):
    exp = sc.exp
    cv = class_view(conn_of(request), exp, sc.step_id)
    buf = io.StringIO()
    w = csv.writer(buf)
    keys = [q.key for q in exp.quantities]
    w.writerow(["group", "station", "submitted_at", "source", "run", *keys, exp.result_symbol,
                "group_mean", "group_rsd_percent", "findings"])
    for s in cv["subs"]:
        flags = ";".join(f.kind for f in s["findings"])
        rsd = s["result"].rsd_percent
        for r in s["result"].runs:
            w.writerow([s["group_code"], s["station"], s["submitted_at"], s["source"], r.index,
                        *[r.values[k] for k in keys], f"{r.result:.6g}", f"{s['result'].mean:.6g}",
                        "" if rsd is None else f"{rsd:.3f}", flags])
    name = f"{sc.course['code']}-step{sc.step['position']}" if sc.step else exp.id
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})


# open catalog ------------------------------------------------------------------

def catalog_scope(request, eid: str) -> Scope:
    return Scope(exp=experiment_or_404(request, eid), base=f"/e/{eid}")


@app.get("/", response_class=HTMLResponse)
def catalog(request: Request, category: str = ""):
    conn = conn_of(request)
    counts = db.count_submissions(conn)
    exps = db.list_experiments(conn)
    used = [c for c in CATEGORIES if any(e.category == c for e in exps)]
    shown = [e for e in exps if not category or e.category == category]
    numbers = {e.id: i for i, e in enumerate(exps, start=1)}
    return page(request, "catalog.html", experiments=shown, counts=counts, categories=used,
                active=category, total=len(exps), groups=sum(counts.values()), numbers=numbers,
                nav="catalog")


@app.get("/e/{eid}", response_class=HTMLResponse)
def overview(request: Request, eid: str):
    sc = catalog_scope(request, eid)
    cv = class_view(conn_of(request), sc.exp)
    flagged = sum(1 for s in cv["subs"] if s["findings"])
    return page(request, "overview.html", exp=sc.exp, scope=sc, tab="overview", n=len(cv["subs"]),
                flagged=flagged, stats=cv["stats"], fmt=fmt)


@app.get("/e/{eid}/new", response_class=HTMLResponse)
def entry_form(request: Request, eid: str):
    return render_entry(request, catalog_scope(request, eid))


@app.post("/e/{eid}/new", response_class=HTMLResponse)
async def entry_submit(request: Request, eid: str):
    return await handle_entry(request, catalog_scope(request, eid))


@app.get("/e/{eid}/class", response_class=HTMLResponse)
def class_page(request: Request, eid: str):
    return render_class(request, catalog_scope(request, eid))


@app.get("/e/{eid}/stations", response_class=HTMLResponse)
def stations_page(request: Request, eid: str):
    return render_stations(request, catalog_scope(request, eid))


@app.get("/e/{eid}/export.csv")
def export_csv(request: Request, eid: str):
    return render_export(request, catalog_scope(request, eid))


@app.get("/s/{sid}", response_class=HTMLResponse)
def result(request: Request, sid: int):
    conn = conn_of(request)
    sub = db.get_submission(conn, sid)
    if sub is None:
        raise HTTPException(404, "This submission does not exist.")
    if sub["step_id"]:
        step = db.get_step(conn, sub["step_id"])
        sc = course_scope(request, step["course_code"], step["id"])
        if not isinstance(sc, Scope):
            return sc
    else:
        sc = catalog_scope(request, sub["experiment_id"])
    exp = sc.exp
    cv = class_view(conn, exp, sc.step_id)
    me = next(s for s in cv["subs"] if s["id"] == sid)
    warnings = [w for i, r in enumerate(me["runs"], start=1) for w in validate_run(r, exp, i)[1]]
    svg = standing = None
    if cv["stats"]:
        pts = [(s["group_code"], s["result"].mean, s["id"] == sid, bool(s["findings"])) for s in cv["subs"]]
        st_pts = [p for p, s in zip(pts, cv["subs"]) if s["station"] == me["station"]]
        st_flag = cv["stations"].get(me["station"], (0, 0, False))[2]
        svg = chart(exp, cv["stats"], [("All groups", pts, False),
                                       (f"Station {me['station']}", st_pts, st_flag)],
                    f"Result of group {me['group_code']} against the class")
        med = cv["stats"].median
        mine = abs(me["result"].mean - med)
        others = [s for s in cv["subs"] if s["id"] != sid]
        standing = {
            "closer_than": round(100 * sum(abs(s["result"].mean - med) > mine for s in others) / len(others)),
            "in_zone": sum(1 for s in cv["subs"] if abs(s["z"]) <= Z_LIMIT),
            "n": len(cv["subs"]),
            "dots": [("me" if s["id"] == sid else "on" if abs(s["z"]) <= Z_LIMIT else "")
                     for s in sorted(cv["subs"], key=lambda s: abs(s["z"]))],
        }
    return page(request, "result.html", exp=exp, scope=sc, tab="class", me=me, stats=cv["stats"],
                chart=svg, warnings=warnings, fmt=fmt, standing=standing)


# builder -----------------------------------------------------------------------

@app.get("/experiments/new", response_class=HTMLResponse)
def builder_form(request: Request, template: str = "", source: str = ""):
    base, prefix = None, ""
    if template in TEMPLATES:
        base = TEMPLATES[template][1]
    elif source:
        base, prefix = db.get_experiment(conn_of(request), source), "Copy of "
    form = builder.to_form(base, prefix)
    if template in TEMPLATES:
        form["title"] = ""
    return page(request, "builder.html", form=form, templates=TEMPLATES, chosen=template or source,
                problems=[], test=None, started=bool(base) or template == "blank", nav="builder")


@app.post("/experiments/new", response_class=HTMLResponse)
async def builder_submit(request: Request):
    raw = await request.form()
    form = builder.read_form(raw)
    conn = conn_of(request)
    exp, problems = builder.build(form, db.unique_id(conn, form["title"]))
    test = builder.test_run(exp) if exp else None
    if exp and raw.get("action") == "save" and not test["errors"]:
        db.save_experiment(conn, exp)
        return RedirectResponse(f"/e/{exp.id}?created=1", status_code=303)
    return page(request, "builder.html", form=form, templates=TEMPLATES, chosen="", problems=problems,
                test=test, started=True, built=exp, status=400 if problems else 200, nav="builder")


@app.post("/e/{eid}/delete")
def delete(request: Request, eid: str):
    exp = experiment_or_404(request, eid)
    conn = conn_of(request)
    if exp.builtin:
        raise HTTPException(400, "Built-in experiments cannot be deleted.")
    if conn.execute("SELECT 1 FROM steps WHERE experiment_id=?", (eid,)).fetchone():
        raise HTTPException(400, "This experiment is used in a course step. Remove the step first.")
    db.delete_experiment(conn, eid)
    return RedirectResponse("/", status_code=303)


@app.get("/about", response_class=HTMLResponse)
def about(request: Request):
    return page(request, "about.html", nav="about")


# courses -----------------------------------------------------------------------

def course_or_404(request, code: str) -> dict:
    course = db.get_course(conn_of(request), code)
    if course is None:
        raise HTTPException(404, "No course with this code.")
    return course


def course_scope(request, code: str, step_id: int, need: str = "class"):
    """Scope for a course step, or a redirect to the course's password page."""
    course = course_or_404(request, code)
    role = auth.role_in(request, code)
    if role is None or (need == "teacher" and role != "teacher"):
        return RedirectResponse(f"/c/{code}", status_code=303)
    step = db.get_step(conn_of(request), step_id)
    if step is None or step["course_code"] != code:
        raise HTTPException(404, "This step does not exist in the course.")
    exp = experiment_or_404(request, step["experiment_id"])
    return Scope(exp=exp, base=f"/c/{code}/s/{step_id}", step_id=step_id, course=course, step=step,
                 role=role)


@app.get("/courses", response_class=HTMLResponse)
def courses(request: Request, error: str = ""):
    from .demo_course import CLASS_PASSWORD, CODE, TEACHER_PASSWORD
    return page(request, "courses.html", nav="courses", error=error,
                demo={"code": CODE, "class": CLASS_PASSWORD, "teacher": TEACHER_PASSWORD})


@app.post("/courses/join")
def join(request: Request, code: str = Form(""), password: str = Form("")):
    code = code.strip().lower()
    course = db.get_course(conn_of(request), code)
    role = None
    if course and auth.verify_password(password, course["teacher_hash"]):
        role = "teacher"
    elif course and auth.verify_password(password, course["class_hash"]):
        role = "class"
    if role is None:
        return RedirectResponse("/courses?error=1", status_code=303)
    resp = RedirectResponse(f"/c/{code}", status_code=303)
    auth.grant(resp, request, code, role)
    return resp


@app.get("/courses/new", response_class=HTMLResponse)
def course_form(request: Request):
    return page(request, "course_new.html", nav="courses", form={"n_groups": "8", "stations": "6"},
                problems=[])


@app.post("/courses/new", response_class=HTMLResponse)
def course_create(request: Request, name: str = Form(""), n_groups: str = Form(""),
                  stations: str = Form(""), teacher_password: str = Form(""),
                  class_password: str = Form("")):
    form = {"name": name, "n_groups": n_groups, "stations": stations}
    problems = []
    groups, st = builder.num(n_groups), builder.num(stations)
    if not name.strip():
        problems.append("Give the course a name.")
    if groups is None or not 2 <= groups <= 40:
        problems.append("Number of groups: between 2 and 40.")
    if st is None or not 1 <= st <= 20:
        problems.append("Number of lab stations: between 1 and 20.")
    if len(teacher_password) < auth.MIN_PASSWORD or len(class_password) < auth.MIN_PASSWORD:
        problems.append(f"Both passwords need at least {auth.MIN_PASSWORD} characters.")
    elif teacher_password == class_password:
        problems.append("The teacher password must differ from the class password.")
    if problems:
        return page(request, "course_new.html", nav="courses", form=form, problems=problems, status=400)
    conn = conn_of(request)
    code = db.new_course_code(conn, name)
    db.create_course(conn, code, name.strip(), int(groups), int(st),
                     auth.hash_password(teacher_password), auth.hash_password(class_password))
    resp = RedirectResponse(f"/c/{code}?created=1", status_code=303)
    auth.grant(resp, request, code, "teacher")
    return resp


@app.get("/c/{code}", response_class=HTMLResponse)
def course_home(request: Request, code: str, error: str = ""):
    course = course_or_404(request, code)
    role = auth.role_in(request, code)
    if role is None:
        return page(request, "course_login.html", nav="courses", course=course, error=error)
    conn = conn_of(request)
    steps = []
    for st in db.list_steps(conn, code):
        exp = db.get_experiment(conn, st["experiment_id"])
        value, n = chain.step_result(conn, st)
        links = []
        for key, src in st["links"].items():
            source = db.get_step(conn, src)
            if source:
                links.append({"label": exp.quantity(key).label, "key": key, "position": source["position"]})
        done = {s["group_code"] for s in db.list_submissions(conn, st["experiment_id"], st["id"])}
        steps.append({**st, "exp": exp, "value": value, "n": n, "links": links, "done": done,
                      "category_class": exp.category.lower().replace(" ", "-")})
    return page(request, "course_home.html", nav="courses", course=course, role=role, steps=steps,
                fmt=fmt)


@app.post("/c/{code}/login")
def course_login(request: Request, code: str, password: str = Form("")):
    course = course_or_404(request, code)
    if auth.verify_password(password, course["teacher_hash"]):
        role = "teacher"
    elif auth.verify_password(password, course["class_hash"]):
        role = "class"
    else:
        return RedirectResponse(f"/c/{code}?error=1", status_code=303)
    resp = RedirectResponse(f"/c/{code}", status_code=303)
    auth.grant(resp, request, code, role)
    return resp


@app.post("/c/{code}/logout")
def course_logout(request: Request, code: str):
    resp = RedirectResponse("/courses", status_code=303)
    auth.revoke(resp, request, code)
    return resp


@app.get("/c/{code}/steps/new", response_class=HTMLResponse)
def step_form(request: Request, code: str, experiment: str = ""):
    course = course_or_404(request, code)
    if auth.role_in(request, code) != "teacher":
        return RedirectResponse(f"/c/{code}", status_code=303)
    conn = conn_of(request)
    exp = db.get_experiment(conn, experiment) if experiment else None
    steps = db.list_steps(conn, code)
    taken = {g for st in steps for g in st["groups"]}
    return page(request, "step_new.html", nav="courses", course=course, chosen=exp,
                experiments=db.list_experiments(conn), steps=steps,
                step_titles={st["id"]: db.get_experiment(conn, st["experiment_id"]) for st in steps},
                free_groups=[g for g in course["groups"] if g not in taken], problems=[])


@app.post("/c/{code}/steps/new", response_class=HTMLResponse)
async def step_create(request: Request, code: str):
    course = course_or_404(request, code)
    if auth.role_in(request, code) != "teacher":
        return RedirectResponse(f"/c/{code}", status_code=303)
    conn = conn_of(request)
    form = await request.form()
    exp = experiment_or_404(request, form.get("experiment", ""))
    groups = [g for g in form.getlist("groups") if g in course["groups"]]
    steps = {st["id"]: st for st in db.list_steps(conn, code)}
    links = {}
    for q in exp.quantities:
        src = form.get(f"link_{q.key}", "")
        if src and src.isdigit() and int(src) in steps:
            links[q.key] = int(src)
    problems = [] if groups else ["Choose at least one group for this step."]
    if problems:
        return page(request, "step_new.html", nav="courses", course=course, chosen=exp,
                    experiments=db.list_experiments(conn), steps=list(steps.values()),
                    step_titles={i: db.get_experiment(conn, st["experiment_id"]) for i, st in steps.items()},
                    free_groups=course["groups"], problems=problems, status=400)
    title = form.get("title", "").strip() or exp.title
    db.add_step(conn, code, exp.id, title, groups, links)
    return RedirectResponse(f"/c/{code}", status_code=303)


@app.post("/c/{code}/s/{step_id}/delete")
def step_delete(request: Request, code: str, step_id: int):
    sc = course_scope(request, code, step_id, need="teacher")
    if not isinstance(sc, Scope):
        return sc
    conn = conn_of(request)
    if any(step_id in st["links"].values() for st in db.list_steps(conn, code)):
        raise HTTPException(400, "A later step takes a value from this step. Remove that step first.")
    db.delete_step(conn, step_id)
    return RedirectResponse(f"/c/{code}", status_code=303)


@app.get("/c/{code}/s/{step_id}/new", response_class=HTMLResponse)
def course_entry_form(request: Request, code: str, step_id: int):
    sc = course_scope(request, code, step_id)
    return render_entry(request, sc) if isinstance(sc, Scope) else sc


@app.post("/c/{code}/s/{step_id}/new", response_class=HTMLResponse)
async def course_entry_submit(request: Request, code: str, step_id: int):
    sc = course_scope(request, code, step_id)
    return await handle_entry(request, sc) if isinstance(sc, Scope) else sc


@app.get("/c/{code}/s/{step_id}/class", response_class=HTMLResponse)
def course_class(request: Request, code: str, step_id: int):
    sc = course_scope(request, code, step_id)
    return render_class(request, sc) if isinstance(sc, Scope) else sc


@app.get("/c/{code}/s/{step_id}/stations", response_class=HTMLResponse)
def course_stations(request: Request, code: str, step_id: int):
    sc = course_scope(request, code, step_id)
    return render_stations(request, sc) if isinstance(sc, Scope) else sc


@app.get("/c/{code}/s/{step_id}/export.csv")
def course_export(request: Request, code: str, step_id: int):
    sc = course_scope(request, code, step_id)
    return render_export(request, sc) if isinstance(sc, Scope) else sc


@app.post("/c/{code}/submissions/{sid}/delete")
def submission_delete(request: Request, code: str, sid: int):
    conn = conn_of(request)
    sub = db.get_submission(conn, sid)
    if sub is None or not sub["step_id"]:
        raise HTTPException(404, "This submission does not exist in a course.")
    sc = course_scope(request, code, sub["step_id"], need="teacher")
    if not isinstance(sc, Scope):
        return sc
    db.delete_submission(conn, sid)
    return RedirectResponse(f"{sc.base}/class", status_code=303)
