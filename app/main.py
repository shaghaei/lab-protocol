"""FastAPI app: digital lab protocol for the NaOH titer experiment."""
import csv
import io
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import db
from .analysis import Z_LIMIT, assess_group, class_stats, robust_z, station_deviations
from .calc import Titration, evaluate_group, validate_titration
from .charts import strip_chart
from .experiments import EXPERIMENTS

BASE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE / "templates")

KIND_LABELS = {
    "digit_swap": ("Possible typo", "warn"),
    "spread": ("Titrations disagree", "warn"),
    "outlier_low": ("Lower than the class", "crit"),
    "outlier_high": ("Higher than the class", "crit"),
    "station": ("Station effect", "warn"),
    "outside_expected": ("Outside usual range", "info"),
}
GROUP_CODE = re.compile(r"^[A-Za-z0-9-]{2,12}$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.conn = db.connect()
    for eid in EXPERIMENTS:
        db.seed_if_empty(app.state.conn, eid)
    yield
    app.state.conn.close()


app = FastAPI(title="Digital Lab Protocol", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates.env.globals["KIND_LABELS"] = KIND_LABELS


def get_experiment(eid: str):
    exp = EXPERIMENTS.get(eid)
    if exp is None:
        raise HTTPException(404, "Unknown experiment")
    return exp


def class_view(conn, exp) -> dict:
    """Evaluate every submission of an experiment against the whole class."""
    subs = db.list_submissions(conn, exp.id)
    for s in subs:
        s["result"] = evaluate_group(s["titrations"], exp)
    stats = class_stats([s["result"].mean_factor for s in subs], exp)
    by_station = {}
    for s in subs:
        by_station.setdefault(s["station"], []).append(s["result"].mean_factor)
    stations = station_deviations(by_station, stats) if stats else {}
    for s in subs:
        s["findings"] = assess_group(s["result"], s["titrations"], s["station"], stats, stations, exp)
        s["z"] = robust_z(s["result"].mean_factor, stats) if stats else None
    return {"subs": subs, "stats": stats, "stations": stations, "by_station": by_station}


def band(stats) -> tuple:
    return (stats.median_f - Z_LIMIT * stats.spread_f, stats.median_f + Z_LIMIT * stats.spread_f)


def parse_number(raw: str) -> float | None:
    raw = (raw or "").strip().replace(",", ".")  # accept German decimal commas
    try:
        return float(raw)
    except ValueError:
        return None


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    conn = request.app.state.conn
    cards = []
    for exp in EXPERIMENTS.values():
        cv = class_view(conn, exp)
        flagged = sum(1 for s in cv["subs"] if s["findings"])
        cards.append({"exp": exp, "n": len(cv["subs"]), "flagged": flagged, "stats": cv["stats"]})
    return templates.TemplateResponse(request, "index.html", {"cards": cards})


@app.get("/e/{eid}/new", response_class=HTMLResponse)
def new_entry(request: Request, eid: str):
    exp = get_experiment(eid)
    return templates.TemplateResponse(request, "entry.html", {"exp": exp, "values": {}, "errors": []})


@app.post("/e/{eid}/new", response_class=HTMLResponse)
async def submit_entry(request: Request, eid: str, group_code: str = Form(""), station: str = Form("")):
    exp = get_experiment(eid)
    conn = request.app.state.conn
    form = await request.form()
    values = dict(form)
    errors = []

    code = group_code.strip().upper()
    if not GROUP_CODE.match(code):
        errors.append("Group code: use 2–12 letters, digits or hyphens, e.g. G31. No names.")
    elif db.group_exists(conn, exp.id, code):
        errors.append(f"Group {code} has already submitted. Submitted values are locked.")
    st = parse_number(station)
    if st is None or int(st) not in exp.stations:
        errors.append("Please choose your lab station.")

    titrations = []
    for i in range(1, exp.n_titrations + 1):
        nums = [parse_number(values.get(f"{q.key}_{i}", "")) for q in exp.quantities]
        if any(n is None for n in nums):
            errors.append(f"Titration {i}: please fill in all three values as numbers.")
            continue
        t = Titration(*nums)
        t_errors, _ = validate_titration(t, exp, i)
        errors.extend(t_errors)
        titrations.append(t)

    if errors:
        return templates.TemplateResponse(request, "entry.html",
                                          {"exp": exp, "values": values, "errors": errors},
                                          status_code=400)
    sid = db.insert_submission(conn, exp.id, code, int(st), titrations)
    return RedirectResponse(f"/s/{sid}", status_code=303)


@app.get("/s/{sid}", response_class=HTMLResponse)
def result(request: Request, sid: int):
    conn = request.app.state.conn
    sub = db.get_submission(conn, sid)
    if sub is None:
        raise HTTPException(404, "Submission not found")
    exp = get_experiment(sub["experiment_id"])
    cv = class_view(conn, exp)
    me = next(s for s in cv["subs"] if s["id"] == sid)
    warnings = []
    for i, t in enumerate(me["titrations"], start=1):
        warnings.extend(validate_titration(t, exp, i)[1])

    chart = None
    if cv["stats"]:
        all_pts = [(s["group_code"], s["result"].mean_factor, s["id"] == sid, bool(s["findings"]))
                   for s in cv["subs"]]
        st_pts = [p for p, s in zip(all_pts, cv["subs"]) if s["station"] == me["station"]]
        st_flag = cv["stations"].get(me["station"], (0, 0, False))[2]
        chart = strip_chart([("All groups", all_pts, False), (f"Station {me['station']}", st_pts, st_flag)],
                            cv["stats"].median_f, band(cv["stats"]),
                            f"Factor of group {me['group_code']} against the class")
    return templates.TemplateResponse(request, "result.html", {
        "exp": exp, "me": me, "stats": cv["stats"], "chart": chart, "warnings": warnings})


@app.get("/e/{eid}/class", response_class=HTMLResponse)
def class_page(request: Request, eid: str):
    exp = get_experiment(eid)
    cv = class_view(request.app.state.conn, exp)
    chart = None
    if cv["stats"]:
        pts = [(s["group_code"], s["result"].mean_factor, False, bool(s["findings"])) for s in cv["subs"]]
        chart = strip_chart([("All groups", pts, False)], cv["stats"].median_f, band(cv["stats"]),
                            "Factor of every group")
    subs = sorted(cv["subs"], key=lambda s: (not s["findings"], s["group_code"]))
    return templates.TemplateResponse(request, "class.html", {
        "exp": exp, "subs": subs, "stats": cv["stats"], "chart": chart})


@app.get("/e/{eid}/stations", response_class=HTMLResponse)
def stations_page(request: Request, eid: str):
    exp = get_experiment(eid)
    cv = class_view(request.app.state.conn, exp)
    chart, rows = None, []
    if cv["stats"]:
        chart_rows = []
        for station in sorted(cv["by_station"]):
            pts = [(s["group_code"], s["result"].mean_factor, False, bool(s["findings"]))
                   for s in cv["subs"] if s["station"] == station]
            info = cv["stations"].get(station)
            chart_rows.append((f"Station {station}", pts, bool(info and info[2])))
            rows.append({"station": station, "n": len(pts), "info": info})
        chart = strip_chart(chart_rows, cv["stats"].median_f, band(cv["stats"]), "Factor by lab station")
    return templates.TemplateResponse(request, "stations.html", {
        "exp": exp, "rows": rows, "stats": cv["stats"], "chart": chart})


@app.get("/e/{eid}/export.csv")
def export_csv(request: Request, eid: str):
    exp = get_experiment(eid)
    cv = class_view(request.app.state.conn, exp)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["group", "station", "submitted_at", "source", "titration", "mass_g", "start_ml",
                "end_ml", "volume_ml", "factor", "group_mean_factor", "group_rsd_percent", "flags"])
    for s in cv["subs"]:
        flags = ";".join(f.kind for f in s["findings"])
        for tr in s["result"].titrations:
            w.writerow([s["group_code"], s["station"], s["submitted_at"], s["source"], tr.index,
                        f"{tr.titration.mass_g:.4f}", f"{tr.titration.start_ml:.2f}",
                        f"{tr.titration.end_ml:.2f}", f"{tr.volume_ml:.2f}", f"{tr.factor:.5f}",
                        f"{s['result'].mean_factor:.5f}", f"{s['result'].rsd_percent:.3f}", flags])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{exp.id}.csv"'})


@app.get("/about", response_class=HTMLResponse)
def about(request: Request):
    return templates.TemplateResponse(request, "about.html", {})
