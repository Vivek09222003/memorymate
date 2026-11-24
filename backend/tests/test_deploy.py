"""Settings for running online (Neon database + Render server)."""
import pytest

from app import main
from app.config import Settings, settings


@pytest.mark.parametrize("given", [
    "postgresql://u:p@ep-cool-1.ap-southeast-1.aws.neon.tech/neondb?sslmode=require",
    "postgres://u:p@ep-cool-1.ap-southeast-1.aws.neon.tech/neondb?sslmode=require",
])
def test_online_database_addresses_use_psycopg(given):
    url = Settings(database_url=given).database_url
    assert url.startswith("postgresql+psycopg://u:p@ep-cool-1")
    assert url.endswith("?sslmode=require")


def test_local_address_is_unchanged():
    url = "postgresql+psycopg://memorymate:memorymate@localhost:5432/memorymate"
    assert Settings(database_url=url).database_url == url


def test_online_server_refuses_the_default_login_secret(monkeypatch):
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://u:p@ep-x.neon.tech/neondb")
    monkeypatch.setattr(settings, "jwt_secret", "dev-only-secret-change-me")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        main._check_settings()


def test_online_server_accepts_a_long_secret(monkeypatch):
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://u:p@ep-x.neon.tech/neondb")
    monkeypatch.setattr(settings, "jwt_secret", "x" * 64)
    main._check_settings()   # no error


def test_laptop_can_keep_the_default_secret(monkeypatch):
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://memorymate:memorymate@localhost:5432/memorymate")
    monkeypatch.setattr(settings, "jwt_secret", "dev-only-secret-change-me")
    main._check_settings()   # fine on your own laptop
