import pytest
from fastapi.testclient import TestClient

from app import auth


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LAB_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("LAB_SECRET", "test-secret")
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_password_hash_roundtrip():
    h = auth.hash_password("geheim123")
    assert auth.verify_password("geheim123", h) and not auth.verify_password("falsch", h)
    assert "geheim123" not in h


def test_cookie_cannot_be_forged(monkeypatch):
    monkeypatch.setenv("LAB_SECRET", "s")
    token = auth.sign({"c1": "class"})
    payload, mac = token.rsplit(".", 1)
    forged = auth.sign({"c1": "teacher"}).rsplit(".", 1)[0] + "." + mac
    assert auth.unsign(token) == {"c1": "class"}
    assert auth.unsign(forged) == {}


def create_course(client):
    r = client.post("/courses/new", data={"name": "Test lab", "n_groups": "6", "stations": "3",
                                         "teacher_password": "teach123", "class_password": "class123"},
                    follow_redirects=False)
    assert r.status_code == 303
    return r.headers["location"].split("/")[2].split("?")[0]


def run_values(prefix, runs):
    return {f"{k}_{i}": v for i, run in enumerate(runs, start=1) for k, v in run.items()}


NAOH = [{"m_KHP": "0.4100", "V_start": "0.20", "V_end": "20.54"},
        {"m_KHP": "0.4200", "V_start": "0.40", "V_end": "21.24"},
        {"m_KHP": "0.4150", "V_start": "0.10", "V_end": "20.69"}]


def test_course_chain_flow(client):
    code = create_course(client)
    home = client.get(f"/c/{code}")
    assert "Share with your students" in home.text

    # step 1: NaOH titer for G01-G03, step 2: vinegar for G04-G06 using f from step 1
    client.post(f"/c/{code}/steps/new", data={"experiment": "naoh-titer", "groups": ["G01", "G02", "G03"]})
    steps_page = client.get(f"/c/{code}/steps/new?experiment=vinegar-acetic-acid")
    import re
    step1 = int(re.search(r'name="link_f_NaOH">\s*<option value="">Groups measure it</option>\s*<option value="(\d+)"',
                          steps_page.text).group(1))
    client.post(f"/c/{code}/steps/new", data={"experiment": "vinegar-acetic-acid",
                                             "groups": ["G04", "G05", "G06"], "link_f_NaOH": str(step1)})
    step2 = step1 + 1

    # step 2 cannot start before step 1 has a result
    vin = {"V_sample": "20.00", "V_start": "0.30", "V_end": "17.17"}
    r = client.post(f"/c/{code}/s/{step2}/new", data={"group_code": "G04", "station": "1",
                                                     **run_values("", [vin] * 3)})
    assert r.status_code == 400 and "no results yet" in r.text

    r = client.post(f"/c/{code}/s/{step1}/new", data={"group_code": "G01", "station": "1",
                                                     **run_values("", NAOH)}, follow_redirects=False)
    assert r.status_code == 303

    # a group not in the step is refused
    r = client.post(f"/c/{code}/s/{step1}/new", data={"group_code": "G05", "station": "1",
                                                     **run_values("", NAOH)})
    assert r.status_code == 400

    form = client.get(f"/c/{code}/s/{step2}/new")
    assert "class median of step 1" in form.text
    r = client.post(f"/c/{code}/s/{step2}/new", data={"group_code": "G04", "station": "1",
                                                     **run_values("", [vin] * 3)}, follow_redirects=False)
    assert r.status_code == 303
    result = client.get(r.headers["location"])
    assert "0.9869" in result.text                     # f from step 1 (mean of G01) used in every run


def test_class_password_cannot_manage(client):
    code = create_course(client)
    client.post(f"/c/{code}/logout")
    other = TestClient(client.app)
    assert "protected" in other.get(f"/c/{code}").text
    other.post(f"/c/{code}/login", data={"password": "class123"})
    assert "Signed in as" in other.get(f"/c/{code}").text
    r = other.get(f"/c/{code}/steps/new", follow_redirects=False)
    assert r.status_code == 303                         # back to the course page


def test_wrong_password_and_no_access(client):
    code = create_course(client)
    stranger = TestClient(client.app)
    r = stranger.post(f"/c/{code}/login", data={"password": "nope"}, follow_redirects=False)
    assert "error=1" in r.headers["location"]
    r = stranger.get(f"/c/{code}/s/1/class", follow_redirects=False)
    assert r.status_code == 303


def test_demo_course_is_seeded(client):
    r = client.post("/courses/join", data={"code": "demo-acid-base", "password": "demo-class"})
    assert "Step 2" in r.text and "comes from the result of step 1" in r.text


def test_teacher_can_delete_entry(client):
    client.post("/courses/join", data={"code": "demo-acid-base", "password": "demo-teacher"})
    page = client.get("/c/demo-acid-base")
    import re
    step = re.search(r'/c/demo-acid-base/s/(\d+)/class', page.text).group(1)
    cls = client.get(f"/c/demo-acid-base/s/{step}/class")
    sid = re.search(r'/c/demo-acid-base/submissions/(\d+)/delete', cls.text).group(1)
    r = client.post(f"/c/demo-acid-base/submissions/{sid}/delete", follow_redirects=False)
    assert r.status_code == 303
    assert client.get(f"/s/{sid}").status_code == 404
