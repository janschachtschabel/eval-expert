from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.manage import reset_password


def client(tmp_path):
    settings = Settings(
        data_dir=str(tmp_path),
        secret_key="a" * 40,
        admin_password="Strong-initial-password!",
        secure_cookie=False,
    )
    return TestClient(create_app(settings, start_worker=False))


def login(c):
    response = c.post(
        "/api/auth/login", json={"username": "admin", "password": "Strong-initial-password!"}
    )
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def test_auth_csrf_and_logout(tmp_path):
    with client(tmp_path) as c:
        assert c.get("/api/catalog/services").status_code == 401
        headers = login(c)
        assert c.post("/api/catalog/services", json={"name": "x"}).status_code == 403
        assert c.get("/api/auth/session").json()["user"]["role"] == "admin"
        assert c.post("/api/auth/logout", headers=headers).status_code == 204
        assert c.get("/api/catalog/services").status_code == 401


def test_secrets_are_encrypted_and_redacted(tmp_path):
    with client(tmp_path) as c:
        headers = login(c)
        response = c.post(
            "/api/catalog/providers",
            headers=headers,
            json={
                "name": "Judge",
                "kind": "openai",
                "model": "gpt-4.1-mini",
                "api_key": "test-key-never-store-in-cleartext",
            },
        )
        assert response.status_code == 200
        assert "test-key-never-store" not in response.text
        assert response.json()["has_secret"] is True
    assert b"test-key-never-store" not in (tmp_path / "eval.db").read_bytes()


def test_chunked_body_is_bounded(tmp_path):
    with client(tmp_path) as c:
        response = c.post("/api/auth/login", content=iter([b"x" * 3_100_000, b"x" * 3_100_000]))
        assert response.status_code == 413


def test_password_reset_revokes_sessions(tmp_path):
    with client(tmp_path) as c:
        login(c)
        reset_password(c.app.state.db, "admin", "New-strong-password!")
        assert c.get("/api/auth/session").status_code == 401
        assert (
            c.post(
                "/api/auth/login", json={"username": "admin", "password": "New-strong-password!"}
            ).status_code
            == 200
        )


def test_viewer_cannot_modify_and_catalog_is_versioned(tmp_path):
    with client(tmp_path) as c:
        headers = login(c)
        created = c.post(
            "/api/catalog/criteria",
            headers=headers,
            json={"name": "Title", "steps": ["Judge the supplied title."], "threshold": 0.7},
        ).json()
        updated = c.put(
            f"/api/catalog/criteria/{created['id']}",
            headers=headers,
            json={**created, "name": "Changed"},
        ).json()
        assert updated["version"] == 2
        assert c.get(f"/api/catalog/criteria/{created['id']}/versions").json()[0]["version"] == 1
        assert (
            c.post(
                "/api/users",
                headers=headers,
                json={
                    "username": "reader",
                    "role": "viewer",
                    "password": "Reader-strong-password!",
                },
            ).status_code
            == 200
        )
        c.post("/api/auth/logout", headers=headers)
        token = c.post(
            "/api/auth/login", json={"username": "reader", "password": "Reader-strong-password!"}
        ).json()["csrf_token"]
        assert (
            c.post(
                "/api/catalog/criteria", headers={"X-CSRF-Token": token}, json={"name": "Denied"}
            ).status_code
            == 403
        )
