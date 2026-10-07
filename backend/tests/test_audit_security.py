from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_rotating_usernames_share_an_ip_budget(tmp_path):
    app = create_app(
        Settings(
            data_dir=str(tmp_path), secret_key="x" * 40, admin_password="Strong-initial-password!"
        ),
        start_worker=False,
    )
    with TestClient(app) as client:
        for i in range(20):
            assert (
                client.post(
                    "/api/auth/login", json={"username": f"missing-{i}", "password": "bad"}
                ).status_code
                == 401
            )
        assert (
            client.post(
                "/api/auth/login", json={"username": "another", "password": "bad"}
            ).status_code
            == 429
        )


def test_limiter_expires_and_bounds_unique_keys():
    from app.login_limits import LoginLimiter

    limiter = LoginLimiter(capacity=4)
    for i in range(12):
        limiter.check(f"ip-{i}", f"user-{i}", at=0)
    assert limiter.size <= 4
    for i in range(20):
        limiter.check("one-ip", f"new-{i}", at=400)
    import pytest

    with pytest.raises(ValueError):
        limiter.check("one-ip", "last", at=401)
    limiter.check("one-ip", "last", at=701)
    assert limiter.size <= 4


def test_custom_credential_header_is_rejected_and_legacy_reads_are_scrubbed(tmp_path):
    app = create_app(
        Settings(
            data_dir=str(tmp_path),
            secret_key="x" * 40,
            admin_password="Strong-initial-password!",
            secure_cookie=False,
        ),
        start_worker=False,
    )
    with TestClient(app) as client:
        token = client.post(
            "/api/auth/login", json={"username": "admin", "password": "Strong-initial-password!"}
        ).json()["csrf_token"]
        headers = {"X-CSRF-Token": token}
        assert (
            client.post(
                "/api/catalog/services",
                headers=headers,
                json={
                    "name": "Unsafe",
                    "auth_header": "X-Access-Token",
                    "headers": {"x-access-token": "credential-marker"},
                },
            ).status_code
            == 422
        )
        old = app.state.db.save_catalog(
            "services",
            {
                "name": "Legacy",
                "auth_header": "X-Access-Token",
                "headers": {"X-Access-Token": "credential-marker", "Accept": "application/json"},
            },
        )
        assert "credential-marker" not in client.get("/api/catalog/services").text
        assert (
            "credential-marker"
            not in client.get(f"/api/catalog/services/{old['id']}/versions").text
        )
        assert client.get(f"/api/catalog/services/{old['id']}").json()["headers"] == {
            "Accept": "application/json"
        }


def test_legacy_credentials_are_encrypted_before_they_are_used(tmp_path):
    from app.auth import cipher
    from app.database import Database

    db = Database(tmp_path)
    old = db.save_catalog(
        "services",
        {
            "name": "Legacy",
            "auth_header": "X-Token",
            "auth_prefix": "",
            "headers": {"X-Token": "legacy-marker"},
        },
    )
    settings = Settings(
        data_dir=str(tmp_path), secret_key="x" * 40, admin_password="Strong-initial-password!"
    )
    app = create_app(settings, start_worker=False)
    saved = app.state.db.get_catalog("services", old["id"], True)
    assert cipher(settings).decrypt(saved["_secret"].encode()).decode() == "legacy-marker"
    assert (
        "legacy-marker" not in app.state.db.get_catalog("services", old["id"])["headers"].values()
    )
    with db.connect() as connection:
        assert "legacy-marker" not in connection.execute("SELECT body FROM versions").fetchone()[0]
