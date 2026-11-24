"""Sign-up, login and profile."""
from tests.conftest import signup


def test_signup_login_and_me(client):
    h = signup(client, "Vivek", "vivek@test.com", phone="98123 45678")
    me = client.get("/auth/me", headers=h).json()
    assert me["name"] == "Vivek"
    assert me["role"] == "ELDER"
    assert me["phone"] == "98123 45678"
    assert "password" not in str(me).lower()  # the password (or its hash) is never sent back


def test_wrong_password_is_refused(client):
    signup(client, "Vivek", "vivek@test.com")
    r = client.post("/auth/login", data={"username": "vivek@test.com", "password": "wrong-pass"})
    assert r.status_code == 401


def test_same_email_twice_is_refused(client):
    signup(client, "Vivek", "vivek@test.com")
    r = client.post("/auth/register", json={"name": "Other", "email": "VIVEK@test.com", "password": "test1234"})
    assert r.status_code == 409


def test_private_pages_need_a_login(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/memories").status_code == 401


def test_update_language_and_phone(client):
    h = signup(client, "Vivek", "vivek@test.com")
    r = client.patch("/auth/me", headers=h, json={"preferred_language": "hinglish", "phone": "+91 98123 45678"})
    assert r.status_code == 200
    assert r.json()["preferred_language"] == "hinglish"
    assert r.json()["phone"] == "+91 98123 45678"


def test_bad_phone_is_refused(client):
    h = signup(client, "Vivek", "vivek@test.com")
    assert client.patch("/auth/me", headers=h, json={"phone": "call me"}).status_code == 422
