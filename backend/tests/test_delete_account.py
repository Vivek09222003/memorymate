"""Delete my account: everything of yours goes, nothing of anyone else's."""
from datetime import timedelta

from sqlalchemy import func, select

from app.ai import AIResult, MemoryCandidate
from app.models import FamilyLink, Memory, Message, Reminder, User
from app.timeutil import local_now
from tests.conftest import linked_family, signup


def _fill(client, h, fake_ai):
    """Give an elder a memory, a chat and a reminder."""
    fake_ai.result = AIResult(intent="SHARE_INFORMATION", reply="Shall I remember that?", memories=[
        MemoryCandidate(memory_type="PERSONAL_FACT", normalized_fact="Rajesh lives in Bangalore.", visibility="PRIVATE")])
    client.post("/chat", headers=h, json={"message": "Rajesh lives in Bangalore"})
    client.post("/chat", headers=h, json={"message": "yes"})
    when = local_now() + timedelta(minutes=5)
    client.post("/reminders", headers=h, json={"title": "BP medicine", "kind": "MEDICINE",
                                               "date": when.date().isoformat(), "time": when.strftime("%H:%M")})


def _count(db, model, **where):
    q = select(func.count()).select_from(model)
    for k, v in where.items():
        q = q.where(getattr(model, k) == v)
    return db.scalar(q)


def test_delete_removes_the_account_and_all_its_data(client, db, fake_ai):
    h = signup(client, "Vivek", "vivek@test.com")
    _fill(client, h, fake_ai)
    uid = client.get("/auth/me", headers=h).json()["id"]
    assert _count(db, Memory, owner_id=uid) > 0 and _count(db, Message, owner_id=uid) > 0

    r = client.post("/auth/delete-account", headers=h, json={"password": "test1234"})
    assert r.status_code == 204
    db.expire_all()
    assert db.get(User, uid) is None
    for model in (Memory, Message, Reminder):
        assert _count(db, model, owner_id=uid) == 0
    # the old login no longer works
    assert client.get("/auth/me", headers=h).status_code == 401
    assert client.post("/auth/login", data={"username": "vivek@test.com", "password": "test1234"}).status_code == 401


def test_wrong_password_deletes_nothing(client, db):
    h = signup(client, "Vivek", "vivek@test.com")
    r = client.post("/auth/delete-account", headers=h, json={"password": "wrong-one"})
    assert r.status_code == 403
    assert client.get("/auth/me", headers=h).status_code == 200


def test_other_peoples_data_stays(client, db, fake_ai):
    vivek = signup(client, "Vivek", "vivek@test.com")
    asha = signup(client, "Asha", "asha@test.com")
    _fill(client, asha, fake_ai)
    asha_id = client.get("/auth/me", headers=asha).json()["id"]
    client.post("/auth/delete-account", headers=vivek, json={"password": "test1234"})
    db.expire_all()
    assert _count(db, Memory, owner_id=asha_id) > 0
    assert client.get("/auth/me", headers=asha).status_code == 200


def test_family_member_leaving_keeps_the_elders_data(client, db, fake_ai):
    elder = signup(client, "Vivek", "vivek@test.com")
    _fill(client, elder, fake_ai)
    priya = linked_family(client, elder)
    elder_id = client.get("/auth/me", headers=elder).json()["id"]
    client.post("/auth/delete-account", headers=priya, json={"password": "test1234"})
    db.expire_all()
    assert _count(db, Memory, owner_id=elder_id) > 0                 # Vivek keeps everything
    assert _count(db, FamilyLink, elder_id=elder_id) == 0             # Priya's access is gone
    assert client.get("/family/links", headers=elder).json() == []


def test_needs_login(client):
    assert client.post("/auth/delete-account", json={"password": "x"}).status_code == 401
