import pytest
from fastapi.testclient import TestClient

from app.experiments import BUILTINS


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LAB_DB", str(tmp_path / "test.db"))
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_catalog_lists_five_experiments(client):
    r = client.get("/")
    assert r.status_code == 200
    for exp in BUILTINS:
        assert exp.title in r.text


@pytest.mark.parametrize("exp", BUILTINS, ids=lambda e: e.id)
def test_experiment_pages_render(client, exp):
    for path in ["", "/new", "/class", "/stations", "/export.csv"]:
        assert client.get(f"/e/{exp.id}{path}").status_code == 200, path


def test_other_pages_render(client):
    for path in ["/about", "/experiments/new", "/experiments/new?template=titration",
                 "/experiments/new?source=naoh-titer", "/s/1"]:
        assert client.get(path).status_code == 200, path


def test_submit_clean_entry_and_lock(client):
    form = {"group_code": "g31", "station": "2",
            "m_KHP_1": "0,4100", "V_start_1": "0.20", "V_end_1": "20.54",
            "m_KHP_2": "0.4200", "V_start_2": "0.40", "V_end_2": "21.24",
            "m_KHP_3": "0.4150", "V_start_3": "0.10", "V_end_3": "20.69"}
    r = client.post("/e/naoh-titer/new", data=form, follow_redirects=False)
    assert r.status_code == 303
    page = client.get(r.headers["location"])
    assert "G31" in page.text and "clean result" in page.text
    again = client.post("/e/naoh-titer/new", data=form)
    assert again.status_code == 400 and "locked" in again.text


def test_invalid_entry_shows_errors(client):
    form = {"group_code": "G32", "station": "1",
            "m_KHP_1": "410", "V_start_1": "0.2", "V_end_1": "20.5",
            "m_KHP_2": "0.42", "V_start_2": "21.0", "V_end_2": "0.4",
            "m_KHP_3": "", "V_start_3": "0.1", "V_end_3": "20.7"}
    r = client.post("/e/naoh-titer/new", data=form)
    assert r.status_code == 400
    assert "thousandth" in r.text and "swapped" in r.text and "enter a number" in r.text


def builder_form(**overrides):
    form = {"title": "Chloride by Mohr titration", "category": "Titration", "summary": "Test.",
            "runs": "3", "stations": "4", "formula": "c_Ag * (V_end - V_start) * M_Cl / V_sample * 1000",
            "result_label": "Chloride content", "result_symbol": "β", "result_unit": "mg/L",
            "result_decimals": "1", "expected": "35.45", "tolerance_percent": "10",
            "max_rsd_percent": "1", "min_spread": "", "constraints": "V_end > V_start",
            "causes_low": "Endpoint too early", "causes_high": "Endpoint overshot", "procedure": "",
            "q1_key": "V_sample", "q1_label": "Sample volume", "q1_unit": "mL", "q1_min": "1",
            "q1_max": "100", "q1_decimals": "2", "q1_example": "50.00",
            "q2_key": "V_start", "q2_label": "Start", "q2_unit": "mL", "q2_min": "0", "q2_max": "50",
            "q2_decimals": "2", "q2_example": "0.10",
            "q3_key": "V_end", "q3_label": "End", "q3_unit": "mL", "q3_min": "0", "q3_max": "50",
            "q3_decimals": "2", "q3_example": "5.10",
            "c1_key": "c_Ag", "c1_label": "AgNO3 concentration", "c1_value": "0.01", "c1_unit": "mol/L",
            "c2_key": "M_Cl", "c2_label": "Molar mass Cl", "c2_value": "35.45", "c2_unit": "g/mol"}
    form.update(overrides)
    return form


def test_builder_test_then_save(client):
    r = client.post("/experiments/new", data=builder_form(action="test"))
    assert r.status_code == 200 and "35.5" in r.text           # 0.01*5*35.45/50*1000
    r = client.post("/experiments/new", data=builder_form(action="save"), follow_redirects=False)
    assert r.status_code == 303
    eid = r.headers["location"].split("/")[2].split("?")[0]
    assert "Chloride by Mohr titration" in client.get("/").text
    assert client.get(f"/e/{eid}/new").status_code == 200
    assert client.post(f"/e/{eid}/delete", follow_redirects=False).status_code == 303
    assert client.get(f"/e/{eid}").status_code == 404


def test_builder_rejects_bad_formula(client):
    r = client.post("/experiments/new", data=builder_form(formula="__import__('os')", action="save"))
    assert r.status_code == 400 and "Formula:" in r.text


def test_builtin_cannot_be_deleted(client):
    assert client.post("/e/naoh-titer/delete").status_code == 400
