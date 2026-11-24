"""The main chat flow, with a fake AI: ask before saving, yes/no, duplicates, corrections."""
from app.ai import AIResult, MemoryCandidate
from tests.conftest import signup

RAJESH_BANGALORE = MemoryCandidate(memory_type="PERSONAL_FACT", person_name="Rajesh", relationship="son",
                                   attribute="city", value="Bangalore",
                                   normalized_fact="Rajesh (son) lives in Bangalore.")


def _say(client, h, text):
    r = client.post("/chat", headers=h, json={"message": text})
    assert r.status_code == 200, r.text
    return r.json()


def test_nothing_is_saved_until_yes(client, fake_ai):
    h = signup(client, "Vivek", "vivek@test.com")
    fake_ai.result = AIResult(intent="SHARE_INFORMATION", reply="Shall I remember that?", memories=[RAJESH_BANGALORE])

    out = _say(client, h, "Mera beta Rajesh Bangalore mein rehta hai")
    assert out["waiting_for_yes_or_no"] is True
    assert client.get("/memories", headers=h).json() == []                       # not active yet
    assert len(client.get("/memories?status=PENDING", headers=h).json()) == 1   # only pending

    calls = fake_ai.calls
    out = _say(client, h, "haan")
    assert out["intent"] == "CONFIRMATION"
    assert fake_ai.calls == calls   # a plain "haan" is understood without calling the AI
    active = client.get("/memories", headers=h).json()
    assert [m["normalized_fact"] for m in active] == ["Rajesh (son) lives in Bangalore."]


def test_no_means_nothing_is_saved(client, fake_ai):
    h = signup(client, "Vivek", "vivek@test.com")
    fake_ai.result = AIResult(intent="SHARE_INFORMATION", reply="Shall I remember that?", memories=[RAJESH_BANGALORE])
    _say(client, h, "Rajesh lives in Bangalore")
    _say(client, h, "nahi")
    assert client.get("/memories", headers=h).json() == []
    assert client.get("/memories?status=PENDING", headers=h).json() == []


def test_question_with_yes_word_is_not_a_confirmation(client, fake_ai):
    h = signup(client, "Vivek", "vivek@test.com")
    fake_ai.result = AIResult(intent="SHARE_INFORMATION", reply="Shall I remember that?", memories=[RAJESH_BANGALORE])
    _say(client, h, "Rajesh lives in Bangalore")
    fake_ai.result = AIResult(intent="QUESTION", reply="He lives in Bangalore.")
    out = _say(client, h, "Acha, aur Rajesh kahan rehta hai?")
    assert out["intent"] == "QUESTION"   # went to the AI, not treated as "yes"


def test_same_fact_twice_is_not_asked_again(client, fake_ai):
    h = signup(client, "Vivek", "vivek@test.com")
    fake_ai.result = AIResult(intent="SHARE_INFORMATION", reply="Shall I remember that?", memories=[RAJESH_BANGALORE])
    _say(client, h, "Rajesh lives in Bangalore")
    _say(client, h, "yes")
    out = _say(client, h, "Rajesh lives in Bangalore")
    assert out["pending_memories"] == []
    assert out["waiting_for_yes_or_no"] is False


def test_correction_keeps_the_old_fact_as_history(client, fake_ai):
    h = signup(client, "Vivek", "vivek@test.com")
    fake_ai.result = AIResult(intent="SHARE_INFORMATION", reply="Remember?", memories=[RAJESH_BANGALORE])
    _say(client, h, "Rajesh lives in Bangalore")
    _say(client, h, "yes")
    old_id = client.get("/memories", headers=h).json()[0]["id"]

    pune = RAJESH_BANGALORE.model_copy(update={"value": "Pune", "normalized_fact": "Rajesh (son) lives in Pune.",
                                               "replaces_memory_id": old_id})
    fake_ai.result = AIResult(intent="SHARE_INFORMATION", reply="Update to Pune?", memories=[pune])
    _say(client, h, "Rajesh lives in Pune now, not Bangalore")
    _say(client, h, "yes")

    assert [m["normalized_fact"] for m in client.get("/memories", headers=h).json()] == ["Rajesh (son) lives in Pune."]
    history = client.get("/memories?status=HISTORICAL", headers=h).json()
    assert [m["id"] for m in history] == [old_id]   # kept, not deleted


def test_new_memories_are_private_unless_sharing_is_mentioned(client, fake_ai):
    h = signup(client, "Vivek", "vivek@test.com")
    shared_by_ai = RAJESH_BANGALORE.model_copy(update={"visibility": "SHARED_FAMILY"})
    fake_ai.result = AIResult(intent="SHARE_INFORMATION", reply="Shall I remember that?", memories=[shared_by_ai])
    out = _say(client, h, "Rajesh lives in Bangalore")
    assert out["pending_memories"][0]["visibility"] == "PRIVATE"


def test_ai_busy_gives_a_friendly_error(client, fake_ai, monkeypatch):
    from app.ai import AIError

    def busy(*a, **k):
        raise AIError("503 UNAVAILABLE", temporary=True)
    monkeypatch.setattr("app.routers.chat.understand", busy)
    h = signup(client, "Vivek", "vivek@test.com")
    r = client.post("/chat", headers=h, json={"message": "Who is Rajesh?"})
    assert r.status_code == 503
    assert "busy" in r.json()["detail"].lower()
