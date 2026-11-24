"""Family and doctor access: invite codes, permissions and privacy."""
from app.ai import AIResult, MemoryCandidate
from tests.conftest import linked_family, signup


def _remember(client, h, fake_ai, fact, visibility="PRIVATE", reply="Shall I remember that?"):
    # A memory is only shared when the AI's question to the user mentions sharing (safety net in chat.py).
    fake_ai.result = AIResult(intent="SHARE_INFORMATION", reply=reply, memories=[
        MemoryCandidate(memory_type="PERSONAL_FACT", normalized_fact=fact, visibility=visibility)])
    client.post("/chat", headers=h, json={"message": fact})
    client.post("/chat", headers=h, json={"message": "yes"})


def test_invite_code_links_the_family_member(client):
    elder = signup(client, "Vivek", "vivek@test.com")
    priya = linked_family(client, elder)
    elders = client.get("/family/my-elders", headers=priya).json()
    assert [e["elder_name"] for e in elders] == ["Vivek"]


def test_wrong_code_cancels_sign_up(client):
    r = client.post("/auth/register", json={"name": "X", "email": "x@test.com", "password": "test1234",
                                            "role": "FAMILY", "invite_code": "WRONG123"})
    assert r.status_code in (400, 404)
    assert client.post("/auth/login", data={"username": "x@test.com", "password": "test1234"}).status_code == 401


def test_private_memories_never_reach_family(client, fake_ai):
    elder = signup(client, "Vivek", "vivek@test.com")
    _remember(client, elder, fake_ai, "I feel lonely in the evenings.")
    _remember(client, elder, fake_ai, "Ananya got a scholarship.", "SHARED_FAMILY",
              reply="Shall I remember that and share it with your family?")
    priya = linked_family(client, elder, can_see_shared_memories=True)
    eid = client.get("/family/my-elders", headers=priya).json()[0]["elder_id"]
    d = client.get(f"/family/elders/{eid}/dashboard", headers=priya).json()
    facts = [m["fact"] for m in d["shared_memories"]]
    assert "Ananya got a scholarship." in facts
    assert "I feel lonely in the evenings." not in facts


def test_hidden_sections_follow_permissions(client):
    elder = signup(client, "Vivek", "vivek@test.com", phone="98123 45678")
    helper = linked_family(client, elder, can_see_medicines=False, can_see_emergency=False)
    eid = client.get("/family/my-elders", headers=helper).json()[0]["elder_id"]
    d = client.get(f"/family/elders/{eid}/dashboard", headers=helper).json()
    assert d["medicines_today"] is None
    assert "medicines" in d["hidden_sections"] and "emergency" in d["hidden_sections"]
    assert d["elder_phone"] is None   # phone only for helpers who may see emergency information


def test_views_are_logged_for_the_elder(client):
    elder = signup(client, "Vivek", "vivek@test.com")
    priya = linked_family(client, elder)
    eid = client.get("/family/my-elders", headers=priya).json()[0]["elder_id"]
    client.get(f"/family/elders/{eid}/dashboard", headers=priya)
    log = client.get("/family/access-log", headers=elder).json()
    assert any(row["viewer_name"] == "Priya" for row in log)


def test_not_linked_means_no_dashboard(client):
    elder = signup(client, "Vivek", "vivek@test.com")
    eid = client.get("/auth/me", headers=elder).json()["id"]
    stranger = signup(client, "Someone", "someone@test.com", role="FAMILY")
    assert client.get(f"/family/elders/{eid}/dashboard", headers=stranger).status_code == 404
