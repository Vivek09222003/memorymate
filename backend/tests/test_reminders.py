"""Reminders: ringing on time, done, missed, and missed-medicine alerts for family."""
from datetime import datetime, timedelta, timezone

from app.models import OccurrenceStatus, ReminderOccurrence
from app.timeutil import local_now
from tests.conftest import linked_family, signup


def _medicine_soon(client, h, title="BP medicine"):
    """A medicine 2 minutes from now (the app refuses one-time reminders in the past)."""
    when = local_now() + timedelta(minutes=2)
    r = client.post("/reminders", headers=h, json={
        "title": title, "kind": "MEDICINE", "date": when.date().isoformat(),
        "time": when.strftime("%H:%M"), "notes": "after dinner"})
    assert r.status_code == 201, r.text
    return r.json()


def _ring_now(db, reminder_id):
    """Move the alert's ring time into the past, as if 2 minutes had gone by."""
    occ = db.query(ReminderOccurrence).filter_by(reminder_id=reminder_id, is_main=True).first()
    occ.fire_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    db.commit()


def _make_missed(db, reminder_id):
    """Pretend the alert rang long ago and nobody answered."""
    occ = db.query(ReminderOccurrence).filter_by(reminder_id=reminder_id, is_main=True).first()
    occ.status = OccurrenceStatus.DUE
    occ.fired_at = datetime.now(timezone.utc) - timedelta(minutes=61)
    db.commit()
    return occ.id


def test_reminder_rings_when_its_time_comes(client, db):
    h = signup(client, "Vivek", "vivek@test.com")
    rem = _medicine_soon(client, h)
    client.post("/reminders/check-now", headers=h)
    assert client.get("/reminders/due", headers=h).json() == []   # not yet
    _ring_now(db, rem["id"])
    client.post("/reminders/check-now", headers=h)
    due = client.get("/reminders/due", headers=h).json()
    assert [a["title"] for a in due] == ["BP medicine"]


def test_done_stops_the_ringing(client, db):
    h = signup(client, "Vivek", "vivek@test.com")
    rem = _medicine_soon(client, h)
    _ring_now(db, rem["id"])
    client.post("/reminders/check-now", headers=h)
    alert = client.get("/reminders/due", headers=h).json()[0]
    assert client.post(f"/reminders/alerts/{alert['id']}/done", headers=h).json()["status"] == "DONE"
    assert client.get("/reminders/due", headers=h).json() == []


def test_unanswered_reminder_becomes_missed(client, db):
    h = signup(client, "Vivek", "vivek@test.com")
    rem = _medicine_soon(client, h)
    occ_id = _make_missed(db, rem["id"])
    client.post("/reminders/check-now", headers=h)
    db.expire_all()
    assert db.get(ReminderOccurrence, occ_id).status == OccurrenceStatus.MISSED


def test_family_sees_missed_medicine_and_it_clears_when_taken(client, db):
    elder = signup(client, "Vivek", "vivek@test.com")
    priya = linked_family(client, elder)
    rem = _medicine_soon(client, elder)
    occ_id = _make_missed(db, rem["id"])
    client.post("/reminders/check-now", headers=elder)

    missed = client.get("/family/missed-medicines", headers=priya).json()
    assert [(m["elder_name"], m["title"]) for m in missed] == [("Vivek", "BP medicine")]

    client.post(f"/reminders/alerts/{occ_id}/done", headers=elder)   # taken late
    assert client.get("/family/missed-medicines", headers=priya).json() == []


def test_missed_medicines_need_medicine_permission(client, db):
    elder = signup(client, "Vivek", "vivek@test.com")
    helper = linked_family(client, elder, can_see_medicines=False)
    rem = _medicine_soon(client, elder)
    _make_missed(db, rem["id"])
    client.post("/reminders/check-now", headers=elder)
    assert client.get("/family/missed-medicines", headers=helper).json() == []


def test_family_suggestion_rings_only_after_accepting(client, db):
    from app.models import Reminder
    elder = signup(client, "Vivek", "vivek@test.com")
    doctor = linked_family(client, elder, name="Dr Sharma", email="doc@test.com")
    eid = client.get("/family/my-elders", headers=doctor).json()[0]["elder_id"]
    when = local_now() + timedelta(minutes=2)
    r = client.post(f"/family/elders/{eid}/reminders", headers=doctor, json={
        "title": "Metformin", "kind": "MEDICINE", "date": when.date().isoformat(), "time": when.strftime("%H:%M")})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    assert db.get(Reminder, rid).status.value == "SUGGESTED"          # waits for the elder
    assert db.query(ReminderOccurrence).filter_by(reminder_id=rid).count() == 0   # nothing will ring

    sug = client.get("/reminders/suggestions", headers=elder).json()
    assert [x["title"] for x in sug] == ["Metformin"]
    client.post(f"/reminders/{rid}/accept", headers=elder)
    _ring_now(db, rid)
    client.post("/reminders/check-now", headers=elder)
    assert [a["title"] for a in client.get("/reminders/due", headers=elder).json()] == ["Metformin"]
