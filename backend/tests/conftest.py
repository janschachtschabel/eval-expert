import os

os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "1"
os.environ["DEEPEVAL_DISABLE_PROGRESS_BAR"] = "1"

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def team_client(tmp_path):
    app = create_app(
        Settings(
            data_dir=str(tmp_path),
            secret_key="x" * 40,
            admin_password="Strong-initial-password!",
            secure_cookie=False,
        ),
        start_worker=False,
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        token = client.post(
            "/api/auth/login", json={"username": "admin", "password": "Strong-initial-password!"}
        ).json()["csrf_token"]
        yield client, {"X-CSRF-Token": token}
