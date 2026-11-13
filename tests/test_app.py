import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LAB_DB", str(tmp_path / "test.db"))
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_pages_render(client):
    for path in ["/", "/e/naoh-titer/new", "/e/naoh-titer/class", "/e/naoh-titer/stations", "/about"]:
        r = client.get(path)
        assert r.status_code == 200, path


def test_submit_clean_entry_and_lock(client):
    form = {"group_code": "g31", "station": "2",
            "mass_g_1": "0,4100", "start_ml_1": "0.20", "end_ml_1": "20.54",
            "mass_g_2": "0.4200", "start_ml_2": "0.40", "end_ml_2": "21.24",
            "mass_g_3": "0.4150", "start_ml_3": "0.10", "end_ml_3": "20.69"}
    r = client.post("/e/naoh-titer/new", data=form, follow_redirects=False)
    assert r.status_code == 303
    page = client.get(r.headers["location"])
    assert "G31" in page.text and "No findings" in page.text
    again = client.post("/e/naoh-titer/new", data=form)
    assert again.status_code == 400 and "locked" in again.text


def test_invalid_entry_shows_errors(client):
    form = {"group_code": "G32", "station": "1",
            "mass_g_1": "410", "start_ml_1": "0.2", "end_ml_1": "20.5",
            "mass_g_2": "0.42", "start_ml_2": "21.0", "end_ml_2": "0.4",
            "mass_g_3": "", "start_ml_3": "0.1", "end_ml_3": "20.7"}
    r = client.post("/e/naoh-titer/new", data=form)
    assert r.status_code == 400
    assert "milligrams" in r.text and "swapped" in r.text and "fill in all three" in r.text


def test_export_csv(client):
    r = client.get("/e/naoh-titer/export.csv")
    assert r.status_code == 200
    assert r.text.count("\n") == 1 + 30 * 3
