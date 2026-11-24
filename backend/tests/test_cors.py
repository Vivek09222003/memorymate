"""The app's browser version (Expo web on port 8081) may call the API; other websites may not."""


def test_expo_web_on_this_laptop_is_allowed(client):
    r = client.options("/auth/login", headers={"Origin": "http://localhost:8081", "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:8081"


def test_expo_web_on_the_wifi_is_allowed(client):
    r = client.get("/health", headers={"Origin": "http://192.168.1.7:8081"})
    assert r.headers.get("access-control-allow-origin") == "http://192.168.1.7:8081"


def test_the_online_website_is_allowed(client):
    r = client.get("/health", headers={"Origin": "https://memorymate-web.onrender.com"})
    assert r.headers.get("access-control-allow-origin") == "https://memorymate-web.onrender.com"


def test_lookalike_onrender_sites_are_not_allowed(client):
    r = client.get("/health", headers={"Origin": "https://memorymate-web.onrender.com.evil.com"})
    assert "access-control-allow-origin" not in r.headers


def test_other_websites_are_not_allowed(client):
    r = client.get("/health", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in r.headers
