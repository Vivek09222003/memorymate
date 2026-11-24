"""What the mobile app relies on: private chat history, phone alarms that follow changes,
and the family app's suggest / note / join actions reaching the elder."""
from datetime import datetime, timedelta

from app.ai import AIResult
from app.timeutil import local_now
from tests.conftest import linked_family, signup


def _reminder(client, h, minutes=5, **extra):
    when = local_now() + timedelta(minutes=minutes)
    body = {"title": "BP medicine", "kind": "MEDICINE", "date": when.date().isoformat(),
            "time": when.strftime("%H:%M"), **extra}
    r = client.post("/reminders", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


# ---------- chat history ----------
def test_chat_history_is_private(client, fake_ai):
    vivek = signup(client, "Vivek", "vivek@test.com")
    asha = signup(client, "Asha", "asha@test.com")
    fake_ai.result = AIResult(intent="SMALL_TALK", reply="Namaste!")
    client.post("/chat", headers=vivek, json={"message": "Hello"})
    assert client.get("/chat/history", headers=asha).json() == []


def test_chat_history_limit_keeps_the_newest(client, fake_ai):
    h = signup(client, "Vivek", "vivek@test.com")
    fake_ai.result = AIResult(intent="SMALL_TALK", reply="OK")
    for word in ["one", "two", "three"]:
        client.post("/chat", headers=h, json={"message": word})
    last = client.get("/chat/history?limit=2", headers=h).json()
    assert [m["text"] for m in last] == ["three", "OK"]


def test_chat_history_needs_login(client):
    assert client.get("/chat/history").status_code == 401


# ---------- phone alarms (/reminders/upcoming) ----------
def test_cancelled_reminder_leaves_the_phone_alarms(client):
    h = signup(client, "Vivek", "vivek@test.com")
    rem = _reminder(client, h, repeat="DAILY")
    assert client.get("/reminders/upcoming", headers=h).json() != []
    client.delete(f"/reminders/{rem['id']}", headers=h)
    assert client.get("/reminders/upcoming", headers=h).json() == []


def test_done_early_moves_the_alarm_to_the_next_day(client):
    h = signup(client, "Vivek", "vivek@test.com")
    _reminder(client, h, repeat="DAILY")
    first = client.get("/reminders/upcoming?hours=48", headers=h).json()[0]
    client.post(f"/reminders/alerts/{first['alert_id']}/done", headers=h)
    after = client.get("/reminders/upcoming?hours=48", headers=h).json()
    assert all(r["alert_id"] != first["alert_id"] for r in after)
    t = lambda r: datetime.fromisoformat(r["ring_at"].replace("Z", "+00:00"))
    assert after and t(after[0]) > t(first)


def test_appointment_has_an_evening_before_alarm(client):
    h = signup(client, "Vivek", "vivek@test.com")
    when = local_now() + timedelta(days=2)   # so "the evening before" (6 PM tomorrow) is still ahead
    client.post("/reminders", headers=h, json={
        "title": "Eye check-up", "kind": "APPOINTMENT", "date": when.date().isoformat(), "time": "11:00"})
    rings = client.get("/reminders/upcoming?hours=96", headers=h).json()
    assert {r["is_main"] for r in rings if r["title"] == "Eye check-up"} == {True, False}


def test_suggested_reminder_has_no_alarm_until_accepted(client):
    elder = signup(client, "Vivek", "vivek@test.com")
    priya = linked_family(client, elder)
    eid = client.get("/family/my-elders", headers=priya).json()[0]["elder_id"]
    when = local_now() + timedelta(minutes=10)
    client.post(f"/family/elders/{eid}/reminders", headers=priya, json={
        "title": "Drink water", "kind": "TASK", "date": when.date().isoformat(), "time": when.strftime("%H:%M")})
    assert client.get("/reminders/upcoming", headers=elder).json() == []
    sug = client.get("/reminders/suggestions", headers=elder).json()[0]
    client.post(f"/reminders/{sug['id']}/accept", headers=elder)
    assert [r["title"] for r in client.get("/reminders/upcoming", headers=elder).json()] == ["Drink water"]


# ---------- family app actions ----------
def test_family_note_reaches_the_elder_to_accept(client):
    elder = signup(client, "Vivek", "vivek@test.com")
    doctor = linked_family(client, elder, name="Dr Sharma", email="doc@test.com")
    eid = client.get("/family/my-elders", headers=doctor).json()[0]["elder_id"]
    r = client.post(f"/family/elders/{eid}/notes", headers=doctor, json={"text": "Walk 20 minutes every morning"})
    assert r.status_code == 201
    notes = client.get("/memories/from-others", headers=elder).json()
    assert [(n["text"], n["from_name"]) for n in notes] == [("Walk 20 minutes every morning", "Dr Sharma")]
    assert client.post(f"/memories/{notes[0]['id']}/approve", headers=elder).status_code == 200
    assert client.get("/memories/from-others", headers=elder).json() == []


def test_suggesting_needs_permission(client):
    elder = signup(client, "Vivek", "vivek@test.com")
    helper = linked_family(client, elder, can_suggest_reminders=False)
    eid = client.get("/family/my-elders", headers=helper).json()[0]["elder_id"]
    when = local_now() + timedelta(minutes=10)
    r = client.post(f"/family/elders/{eid}/reminders", headers=helper, json={
        "title": "Walk", "kind": "TASK", "date": when.date().isoformat(), "time": when.strftime("%H:%M")})
    assert r.status_code == 403


def test_existing_family_account_joins_with_a_code(client):
    elder = signup(client, "Vivek", "vivek@test.com")
    priya = signup(client, "Priya", "priya@test.com", role="FAMILY")      # signed up earlier, no code
    code = client.post("/family/invites", headers=elder, json={"name": "Priya"}).json()["invite_code"]
    r = client.post("/family/join", headers=priya, json={"code": code.lower()})   # typed in small letters
    assert r.status_code == 200 and r.json()["elder_name"] == "Vivek"
    assert client.post("/family/join", headers=priya, json={"code": code}).status_code == 404   # used up


def test_wrong_code_is_a_clear_error(client):
    priya = signup(client, "Priya", "priya@test.com", role="FAMILY")
    r = client.post("/family/join", headers=priya, json={"code": "ABCD1234"})
    assert r.status_code == 404 and "code" in r.json()["detail"].lower()
