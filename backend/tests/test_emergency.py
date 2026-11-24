"""Emergency mode: help words, the SOS button, family alerts and resolving them."""
import pytest

from app.ai import AIResult
from app.emergency import is_emergency
from tests.conftest import linked_family, signup


@pytest.mark.parametrize("text", [
    "help", "Help!", "help me please", "madad karo", "Mujhe madad chahiye", "bachao", "Main gir gaya",
    "I fell in the bathroom", "chest pain ho raha hai", "seene mein dard hai", "emergency!", "call ambulance",
    "SOS", "बचाओ", "मदद करो", "मैं गिर गया", "This is an emergency"])
def test_help_words_are_emergencies(text):
    assert is_emergency(text)


@pytest.mark.parametrize("text", [
    "can you help me remember Rajesh's number?", "Add Rajesh as my emergency contact",
    "Rajesh is my emergency contact, number 98765", "help me set a reminder for 9 pm tomorrow please",
    "Who are my emergency contacts?", "I'm a bit tired today", "what is sos?", "How does emergency mode work?"])
def test_normal_sentences_are_not_emergencies(text):
    assert not is_emergency(text)


def test_help_in_chat_alerts_family_without_the_ai(client, fake_ai):
    elder = signup(client, "Vivek", "vivek@test.com", phone="98123 45678")
    priya = linked_family(client, elder)

    calls = fake_ai.calls
    out = client.post("/chat", headers=elder, json={"message": "bachao, main gir gaya"}).json()
    assert fake_ai.calls == calls        # works even when the AI is down
    assert out["intent"] == "EMERGENCY"
    assert out["emergency"]["notified"] == ["Priya"]
    assert "108" in out["reply"]

    alerts = client.get("/emergency/alerts", headers=priya).json()
    assert len(alerts) == 1
    assert alerts[0]["elder_name"] == "Vivek"
    assert alerts[0]["elder_phone"] == "98123 45678"
    assert alerts[0]["message"] == "bachao, main gir gaya"


def test_sos_button_then_im_safe(client):
    elder = signup(client, "Vivek", "vivek@test.com")
    priya = linked_family(client, elder)
    alert = client.post("/emergency/sos", headers=elder).json()
    assert alert["status"] == "ACTIVE" and alert["source"] == "button"

    again = client.post("/emergency/sos", headers=elder).json()
    assert again["id"] == alert["id"]     # pressing twice doesn't create a second alert

    client.post(f"/emergency/{alert['id']}/resolve", headers=elder)
    assert client.get("/emergency/alerts", headers=priya).json() == []
    assert client.get("/emergency/active", headers=elder).json() is None


def test_family_can_mark_it_handled(client):
    elder = signup(client, "Vivek", "vivek@test.com")
    priya = linked_family(client, elder)
    alert = client.post("/emergency/sos", headers=elder).json()
    done = client.post(f"/emergency/{alert['id']}/resolve", headers=priya).json()
    assert done["status"] == "RESOLVED" and done["resolved_by"] == "Priya"


def test_helper_without_emergency_permission_sees_nothing(client):
    elder = signup(client, "Vivek", "vivek@test.com")
    helper = linked_family(client, elder, can_see_emergency=False)
    client.post("/emergency/sos", headers=elder)
    assert client.get("/emergency/alerts", headers=helper).json() == []


def test_strangers_cannot_see_or_resolve_alerts(client):
    elder = signup(client, "Vivek", "vivek@test.com")
    alert = client.post("/emergency/sos", headers=elder).json()
    stranger = signup(client, "Someone", "someone@test.com", role="FAMILY")
    assert client.get("/emergency/alerts", headers=stranger).json() == []
    assert client.post(f"/emergency/{alert['id']}/resolve", headers=stranger).status_code == 404


def test_helper_is_not_offered_to_call_themselves(client, fake_ai, db):
    from app.models import Person, User
    elder = signup(client, "Vivek", "vivek@test.com")
    priya = linked_family(client, elder)
    vivek_id = db.query(User).filter_by(email="vivek@test.com").one().id
    db.add_all([Person(owner_id=vivek_id, name="Priya", relation_to_user="daughter", phone="90000 00001",
                       is_emergency_contact=True),
                Person(owner_id=vivek_id, name="Rajesh", relation_to_user="son", phone="98765 43210",
                       is_emergency_contact=True)])
    db.commit()
    client.post("/emergency/sos", headers=elder)
    names = [p["name"] for p in client.get("/emergency/alerts", headers=priya).json()[0]["contacts"]]
    assert names == ["Rajesh"]


def test_ai_noticing_illness_only_suggests_help(client, fake_ai):
    elder = signup(client, "Vivek", "vivek@test.com")
    priya = linked_family(client, elder)
    fake_ai.result = AIResult(intent="EMERGENCY", reply="You sound unwell. Press Help if you need someone.")
    out = client.post("/chat", headers=elder, json={"message": "I'm feeling very dizzy today"}).json()
    assert out["suggest_help"] is True
    assert out["emergency"] is None
    assert client.get("/emergency/alerts", headers=priya).json() == []   # nobody alerted without the elder
