"""Overview screen: every elder or patient on one page, most urgent first, within each elder's permissions."""
from tests.conftest import linked_family, signup
from tests.test_reminders import _make_missed, _medicine_soon


def _also_link(client, elder_headers, helper_headers, name="Priya", **scopes):
    """A second elder gives the same helper access; the helper enters the new code."""
    code = client.post("/family/invites", headers=elder_headers, json={"name": name, **scopes}).json()["invite_code"]
    r = client.post("/family/join", headers=helper_headers, json={"code": code})
    assert r.status_code == 200, r.text


def test_overview_lists_everyone_most_urgent_first(client, db):
    vivek = signup(client, "Vivek", "vivek@test.com", phone="98123 45678")
    asha = signup(client, "Asha", "asha@test.com")
    mohan = signup(client, "Mohan", "mohan@test.com")
    priya = linked_family(client, vivek)
    _also_link(client, asha, priya)
    _also_link(client, mohan, priya)

    rem = _medicine_soon(client, asha)                 # Asha misses a medicine
    _make_missed(db, rem["id"])
    client.post("/reminders/check-now", headers=asha)
    client.post("/emergency/sos", headers=mohan)       # Mohan presses Help

    rows = client.get("/family/overview", headers=priya).json()
    assert [(r["elder_name"], r["status"]) for r in rows] == [
        ("Mohan", "emergency"), ("Asha", "attention"), ("Vivek", "ok")]
    asha_row = rows[1]
    assert (asha_row["medicines_total"], asha_row["medicines_taken"], asha_row["medicines_missed"]) == (1, 0, 1)
    assert rows[0]["emergency_since"] is not None
    assert rows[2]["elder_phone"] == "98123 45678"


def test_overview_follows_permissions(client, db):
    vivek = signup(client, "Vivek", "vivek@test.com", phone="98123 45678")
    helper = linked_family(client, vivek, can_see_medicines=False, can_see_emergency=False)
    rem = _medicine_soon(client, vivek)
    _make_missed(db, rem["id"])
    client.post("/reminders/check-now", headers=vivek)
    client.post("/emergency/sos", headers=vivek)

    row = client.get("/family/overview", headers=helper).json()[0]
    assert row["status"] == "ok"                       # can't see medicines or emergencies, so no warning either
    assert row["medicines_total"] is None and row["medicines_missed"] is None
    assert row["elder_phone"] is None and row["emergency_since"] is None


def test_overview_counts_my_waiting_suggestions(client):
    from datetime import timedelta
    from app.timeutil import local_now
    vivek = signup(client, "Vivek", "vivek@test.com")
    doctor = linked_family(client, vivek, name="Dr Sharma", email="doc@test.com")
    eid = client.get("/family/my-elders", headers=doctor).json()[0]["elder_id"]
    when = local_now() + timedelta(minutes=5)
    client.post(f"/family/elders/{eid}/reminders", headers=doctor, json={
        "title": "Metformin", "kind": "MEDICINE", "date": when.date().isoformat(), "time": when.strftime("%H:%M")})
    assert client.get("/family/overview", headers=doctor).json()[0]["my_suggestions_waiting"] == 1


def test_overview_is_logged_once_not_every_refresh(client):
    vivek = signup(client, "Vivek", "vivek@test.com")
    priya = linked_family(client, vivek)
    for _ in range(3):                                 # the page refreshes every minute
        client.get("/family/overview", headers=priya)
    log = client.get("/family/access-log", headers=vivek).json()
    assert sum(1 for row in log if row["section"] == "overview") == 1


def test_elders_cannot_open_the_overview(client):
    vivek = signup(client, "Vivek", "vivek@test.com")
    assert client.get("/family/overview", headers=vivek).status_code == 403
