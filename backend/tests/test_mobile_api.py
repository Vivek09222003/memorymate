"""Routes the mobile app needs: alarms to set on the phone, and the chat history."""
from datetime import datetime, timedelta

from app.ai import AIResult
from app.timeutil import local_now
from tests.conftest import signup


def _daily_medicine(client, h, minutes_from_now=5):
    when = local_now() + timedelta(minutes=minutes_from_now)
    r = client.post("/reminders", headers=h, json={
        "title": "BP medicine", "kind": "MEDICINE", "date": when.date().isoformat(),
        "time": when.strftime("%H:%M"), "repeat": "DAILY"})
    assert r.status_code == 201, r.text
    return r.json()


def test_upcoming_lists_the_next_ring_and_later_daily_repeats(client):
    h = signup(client, "Vivek", "vivek@test.com")
    _daily_medicine(client, h)
    rings = client.get("/reminders/upcoming?hours=48", headers=h).json()
    main = [r for r in rings if r["title"] == "BP medicine" and r["is_main"]]
    assert len(main) == 2                      # today's ring (planned) + tomorrow's (worked out)
    assert main[0]["alert_id"] is not None and main[1]["alert_id"] is None
    t = lambda r: datetime.fromisoformat(r["ring_at"].replace("Z", "+00:00"))
    assert t(main[0]) < t(main[1])


def test_upcoming_respects_the_time_window(client):
    h = signup(client, "Vivek", "vivek@test.com")
    _daily_medicine(client, h)
    rings = client.get("/reminders/upcoming?hours=1", headers=h).json()
    assert len(rings) == 1


def test_upcoming_is_only_my_own(client):
    vivek = signup(client, "Vivek", "vivek@test.com")
    asha = signup(client, "Asha", "asha@test.com")
    _daily_medicine(client, vivek)
    assert client.get("/reminders/upcoming", headers=asha).json() == []


def test_chat_history_comes_back_oldest_first(client, fake_ai):
    h = signup(client, "Vivek", "vivek@test.com")
    fake_ai.result = AIResult(intent="SMALL_TALK", reply="Namaste Vivek!")
    client.post("/chat", headers=h, json={"message": "Hello"})
    hist = client.get("/chat/history", headers=h).json()
    assert [(m["role"], m["text"]) for m in hist] == [("user", "Hello"), ("assistant", "Namaste Vivek!")]
