"""Memory search: people first, then by meaning, and nothing unrelated when nothing matches."""
from app.ai import AIResult, MemoryCandidate
from app.retrieval import people_mentioned
from app.models import Person
from tests.conftest import signup


def _remember(client, h, fake_ai, fact, person=None, relation=None):
    fake_ai.result = AIResult(intent="SHARE_INFORMATION", reply="Remember?", memories=[
        MemoryCandidate(memory_type="PERSONAL_FACT", normalized_fact=fact, person_name=person, relationship=relation)])
    client.post("/chat", headers=h, json={"message": fact})
    client.post("/chat", headers=h, json={"message": "yes"})


def test_people_are_found_by_name_or_relation():
    ananya = Person(id=1, name="Ananya", relation_to_user="granddaughter")
    doc = Person(id=2, name="Dr. Sharma", relation_to_user="family doctor")
    assert people_mentioned("What is my granddaughter studying?", [ananya, doc]) == [ananya]
    assert people_mentioned("When do I see my doctor?", [ananya, doc]) == [doc]
    assert people_mentioned("Call Sharma", [ananya, doc]) == [doc]


def test_search_finds_memories_by_meaning(client, fake_ai):
    h = signup(client, "Vivek", "vivek@test.com")
    _remember(client, h, fake_ai, "Ananya studies computer engineering at NIT Kurukshetra.")
    _remember(client, h, fake_ai, "I take BP medicine every night.")
    hits = client.get("/memories/search", headers=h, params={"q": "what Ananya studies at NIT"}).json()
    assert hits and hits[0]["memory"]["normalized_fact"].startswith("Ananya studies")


def test_unrelated_question_finds_nothing(client, fake_ai):
    h = signup(client, "Vivek", "vivek@test.com")
    _remember(client, h, fake_ai, "Ananya studies computer engineering at NIT Kurukshetra.")
    hits = client.get("/memories/search", headers=h, params={"q": "where does my sister live"}).json()
    assert hits == []   # the distance limit keeps far-away memories out


def test_show_all_lists_distances_for_tuning(client, fake_ai):
    h = signup(client, "Vivek", "vivek@test.com")
    _remember(client, h, fake_ai, "Ananya studies computer engineering at NIT Kurukshetra.")
    hits = client.get("/memories/search", headers=h, params={"q": "where does my sister live", "show_all": True}).json()
    assert hits and hits[0]["distance"] is not None
