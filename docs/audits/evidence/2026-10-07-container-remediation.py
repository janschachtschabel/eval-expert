"""Opt-in destructive fault injection, restricted to the two named audit containers.

Requires the verification image and audit container on localhost:8118; never uses 8080.
EVAL_TEST_PASSWORD and EVAL_TEST_SECRET must match this disposable installation.
"""

import hashlib
import http.cookiejar
import json
import os
import subprocess
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

CONTAINER = "eval-expert-remediation-audit"
RESTORE = "eval-expert-remediation-restore"
VOLUME = "eval-expert-remediation-audit-data"
RESTORE_VOLUME = "eval-expert-remediation-restore-data"
IMAGE = "eval-expert:verification"
OUT = Path(__file__).resolve().parents[3] / "artifacts" / "container-remediation"


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True).strip()


def request(base, path, opener=None, data=None, csrf=None):
    headers = {"Content-Type": "application/json"}
    if csrf:
        headers["X-CSRF-Token"] = csrf
    req = urllib.request.Request(
        base + "/api" + path,
        headers=headers,
        data=None if data is None else json.dumps(data).encode(),
    )
    with (opener or urllib.request.build_opener()).open(req, timeout=5) as response:
        return json.load(response)


def healthy(base):
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        try:
            if request(base, "/health")["status"] == "ok":
                return
        except (OSError, ValueError):
            pass
        time.sleep(0.25)
    raise AssertionError("Application did not recover")


def login(base):
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    session = request(
        base,
        "/auth/login",
        opener,
        {"username": "admin", "password": os.environ["EVAL_TEST_PASSWORD"]},
    )
    return opener, session["csrf_token"]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def run():
    assert not OUT.exists(), (
        "Choose a fresh evidence directory; existing backups are retained"
    )
    info = json.loads(docker("inspect", CONTAINER))[0]
    assert any(m.get("Name") == VOLUME for m in info["Mounts"])
    assert "127.0.0.1" == info["HostConfig"]["PortBindings"]["8000/tcp"][0]["HostIp"]
    assert "8118" == info["HostConfig"]["PortBindings"]["8000/tcp"][0]["HostPort"]
    assert (
        RESTORE_VOLUME
        not in docker("volume", "ls", "--format", "{{.Name}}").splitlines()
    )
    base = "http://127.0.0.1:8118"
    healthy(base)
    client, csrf = login(base)
    page = request(base, "/runs/page?status=completed&limit=1", client)
    run_id = page["items"][0]["id"]
    original = request(base, f"/runs/{run_id}/export", client)
    expected = digest(original)
    provider = request(
        base,
        "/catalog/providers",
        client,
        {
            "name": "Backup fixture",
            "kind": "openai",
            "base_url": "https://api.openai.com/v1",
            "model": "synthetic-model",
            "api_key": "synthetic-restore-credential",
        },
        csrf,
    )
    assert provider["has_secret"] and "synthetic-restore-credential" not in json.dumps(
        provider
    )

    start = datetime.now(UTC).isoformat()
    docker(
        "exec",
        CONTAINER,
        "python",
        "-c",
        "from pathlib import Path; p=Path('/data/eval.db'); "
        "assert p.is_file(); p.rename('/data/eval.db.saved'); p.mkdir()",
    )
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        if (
            int(docker("inspect", "--format", "{{.RestartCount}}", CONTAINER))
            > info["RestartCount"]
        ):
            break
        time.sleep(0.25)
    else:
        raise AssertionError("Worker failure did not restart the container")
    events = docker(
        "events",
        "--since",
        start,
        "--until",
        datetime.now(UTC).isoformat(),
        "--filter",
        "container=" + CONTAINER,
        "--filter",
        "event=die",
        "--format",
        "{{json .}}",
    )
    assert any(
        json.loads(line)["Actor"]["Attributes"].get("exitCode") == "1"
        for line in events.splitlines()
    )
    docker(
        "run",
        "--rm",
        "--user",
        "0",
        "--entrypoint",
        "python",
        "-v",
        VOLUME + ":/data",
        IMAGE,
        "-c",
        "from pathlib import Path; p=Path('/data/eval.db'); assert p.is_dir(); "
        "p.rmdir(); Path('/data/eval.db.saved').rename(p)",
    )
    healthy(base)
    assert digest(request(base, f"/runs/{run_id}/export", client)) == expected
    print("worker_restart_verified", flush=True)

    OUT.mkdir(parents=True)
    docker("stop", CONTAINER)
    docker("cp", CONTAINER + ":/data", str(OUT / "backup"))
    env = {
        **os.environ,
        "EVAL_SECRET_KEY": os.environ["EVAL_TEST_SECRET"],
        "EVAL_ADMIN_PASSWORD": os.environ["EVAL_TEST_PASSWORD"],
    }
    subprocess.check_output(
        [
            "docker",
            "create",
            "--name",
            RESTORE,
            "--init",
            "--read-only",
            "--tmpfs",
            "/tmp:size=128m,mode=1777",
            "--security-opt",
            "no-new-privileges:true",
            "--cap-drop",
            "ALL",
            "-p",
            "127.0.0.1:8119:8000",
            "-v",
            RESTORE_VOLUME + ":/data",
            "-e",
            "EVAL_SECRET_KEY",
            "-e",
            "EVAL_ADMIN_PASSWORD",
            "-e",
            "EVAL_SECURE_COOKIE=false",
            IMAGE,
        ],
        env=env,
    )
    docker("cp", str(OUT / "backup") + "/.", RESTORE + ":/data")
    docker(
        "run",
        "--rm",
        "--user",
        "0",
        "--entrypoint",
        "python",
        "-v",
        RESTORE_VOLUME + ":/data",
        IMAGE,
        "-c",
        "import os; from pathlib import Path; "
        "[os.chown(p,10001,10001) for p in Path('/data').iterdir()]",
    )
    docker("start", RESTORE)
    restored = "http://127.0.0.1:8119"
    healthy(restored)
    new_client, _ = login(restored)
    assert digest(request(restored, f"/runs/{run_id}/export", new_client)) == expected
    assert request(restored, "/runs/page", new_client)["total"] == page["total"]
    # All runs in this fixture are complete; the filtered and unfiltered totals agree.
    docker(
        "exec",
        RESTORE,
        "python",
        "-c",
        "from app.database import Database; from app.auth import cipher; from app.config import Settings; "
        "s=Settings(); db=Database(s.data_dir); "
        f"value=db.get_catalog('providers',{provider['id']!r},internal=True); "
        "assert cipher(s).decrypt(value['_secret'].encode()).decode()=='synthetic-restore-credential'",
    )
    evidence = {
        "worker_exit_code": 1,
        "automatic_restart": True,
        "export_hash_preserved": True,
        "backup_restore": True,
        "encrypted_credentials_preserved": True,
        "cases_restored": len(original["results"]),
        "image": info["Image"],
    }
    (OUT / "result.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence), flush=True)


if __name__ == "__main__":
    run()
