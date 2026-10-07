import asyncio

import pytest

from app.run_store import enqueue, snapshot


@pytest.mark.asyncio
async def test_supervisor_recovers_without_replaying_uncertain_work(team_client):
    from app.runner import worker
    from app.worker_supervisor import supervise

    client, headers = team_client
    plan = client.post("/api/demo", headers=headers).json()["plan_id"]
    db = client.app.state.db
    id = enqueue(db, snapshot(db, plan))
    with db.connect() as c:
        c.execute("UPDATE runs SET status='running' WHERE id=?", (id,))
    calls = []

    async def unreliable(app):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("Synthetic database outage")
        await worker(app)

    task = asyncio.create_task(supervise(client.app, worker_fn=unreliable, retry_delays=(0,)))
    try:

        async def recovered():
            while client.app.state.worker_state != "ok":
                await asyncio.sleep(0)

        await asyncio.wait_for(recovered(), 2)
        assert len(calls) == 2
        assert client.get("/api/runs/" + id).json()["status"] == "interrupted"
        assert client.get("/api/health").status_code == 200
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_persistent_worker_failure_requests_process_restart(team_client):
    from app.worker_supervisor import supervise

    client, _ = team_client
    exits = []

    async def failing(app):
        raise RuntimeError("Synthetic persistent outage")

    await supervise(client.app, worker_fn=failing, retry_delays=(0, 0), fatal=exits.append)
    assert exits == [1]
    assert client.get("/api/health").status_code == 503
