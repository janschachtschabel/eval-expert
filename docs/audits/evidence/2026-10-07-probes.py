import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.run_store import enqueue, read_run, snapshot
from app.runner import execute_case
from app.scheduler import tick
from app.benchmarks import compare_fields

evidence = {}
with tempfile.TemporaryDirectory() as folder:
    app = create_app(Settings(data_dir=folder, secret_key="audit-only-" + "a" * 40,
        admin_password="Audit-password-for-tests!", secure_cookie=False,
        frontend_dir=folder), start_worker=False)
    with TestClient(app, raise_server_exceptions=False) as client:
        login = client.post("/api/auth/login",
            json={"username":"admin", "password":"Audit-password-for-tests!"}).json()
        headers = {"X-CSRF-Token": login["csrf_token"]}
        probes = {
            "short_csv_row": ("/api/catalog/datasets", {"name":"Bad CSV","format":"csv",
                "content":"id,title,reference.subject\n1,Title\n".replace("\\n", "\n")}),
            "schedule_preview_wrong_type": ("/api/connections/schedule-preview",
                {"cron":"0 8 * * *","timezone":[]}),
            "missing_recompute_run": ("/api/runs/missing/recompute", {}),
            "wrong_plan_id_type": ("/api/runs", {"plan_id":[]}),
        }
        for name,(url,body) in probes.items():
            response=client.post(url,headers=headers,json=body)
            evidence[name]={"status":response.status_code}
        created=client.post("/api/catalog/criteria",headers=headers,
            json={"name":"Original","description":"original","steps":["Judge clarity."]}).json()
        first=client.put("/api/catalog/criteria/"+created["id"],headers=headers,
            json={**created,"description":"first editor change"}).json()
        second=client.put("/api/catalog/criteria/"+created["id"],headers=headers,
            json={**created,"name":"second editor change"}).json()
        evidence["stale_update"]={"first_version":first["version"],"second_version":second["version"],
            "first_change_lost":second["description"] != first["description"]}
        service=client.post("/api/catalog/services",headers=headers,json={
            "name":"Secret header","url":"https://metadata.example.test/",
            "auth_header":"X-Access-Token","headers":{"X-Access-Token":"synthetic-credential-marker"}}).json()
        evidence["custom_auth_header_public"]={
            "credential_in_public_catalog":"synthetic-credential-marker" in json.dumps(service)}
        demo=client.post("/api/demo",headers=headers,json={}).json()
        plan_id=demo["plan_id"]
        db=app.state.db
        saved=snapshot(db,plan_id)
        client.delete("/api/catalog/services/"+saved["service"]["id"],headers=headers)
        invalid=client.post("/api/runs",headers=headers,json={"plan_id":plan_id})
        evidence["delete_referenced_service"]={"start_after_delete_status":invalid.status_code,
            "plan_still_exists":client.get("/api/catalog/plans/"+plan_id).status_code==200}
        app.state.login_attempts.clear()
        for i in range(11):
            status=client.post("/api/auth/login",json={"username":"unknown-one","password":"wrong"}).status_code
        different=client.post("/api/auth/login",json={"username":"unknown-two","password":"wrong"}).status_code
        evidence["login_throttle"]={"same_name_attempt_11":status,"different_name_same_ip":different,
            "buckets":len(app.state.login_attempts)}
        for i in range(12):
            client.post("/api/auth/login",json={"username":f"unique-{i}","password":"wrong"})
        evidence["login_throttle"]["buckets_after_unique_names"]=len(app.state.login_attempts)
        for i in range(20):
            enqueue(db,saved)
        scheduled=db.save_catalog("schedules",{"name":"Queue probe","enabled":True,
            "plan_id":plan_id,"cron":"0 8 * * *","timezone":"Europe/Berlin"})
        old_due="2026-01-01T00:00:00+00:00"
        with db.connect() as connection:
            connection.execute("INSERT INTO schedule_state VALUES(?,?)",(scheduled["id"],old_due))
        with patch("app.scheduler.snapshot",return_value=saved):
            tick(db)
        with db.connect() as connection:
            due=connection.execute("SELECT next_due FROM schedule_state WHERE id=?",(scheduled["id"],)).fetchone()[0]
            count=connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            last=connection.execute("SELECT action FROM audit ORDER BY id DESC LIMIT 1").fetchone()[0]
        evidence["full_queue_schedule"]={"queued_count":count,"due_advanced_without_run":due != old_due,"audit":last}
        case={"id":"one","input":{"title":"Example"},"reference":{"subject":["math"],"level":["primary"]}}
        config={"service":{"kind":"demo"},"criteria":[],"plan":{"fields":[
            {"name":"subject","output_path":"/subject","reference_path":"/subject"},
            {"name":"level","output_path":"/level","reference_path":"/level"}]}}
        async def fake_target(*args,**kwargs):
            return {"subject":["math"],"level":{"invalid":"type"},"raw":"evidence"}
        with patch("app.runner.call_target",side_effect=fake_target):
            result=asyncio.run(execute_case(app,config,case))
        evidence["invalid_output_field"]={"status":result["status"],"raw_output_lost":result["output"] is None}
        with db.connect() as connection:
            connection.execute("UPDATE runs SET status='completed'")
        large_saved={**saved,"dataset":{**saved["dataset"],"cases":[{"id":"1","input":{"text":"x"*100_000},"reference":{}}]}}
        for i in range(201):
            run_id=enqueue(db,large_saved)
            with db.connect() as connection:
                connection.execute("UPDATE runs SET status='completed' WHERE id=?",(run_id,))
        from app.run_store import list_runs
        listing=list_runs(db)
        with db.connect() as connection:
            snapshot_bytes=connection.execute("SELECT SUM(LENGTH(snapshot)) FROM (SELECT snapshot FROM runs ORDER BY created DESC LIMIT 200)").fetchone()[0]
            count=connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        evidence["run_list_loading"]={"total_runs":count,"listed":len(listing),"snapshots_read_bytes":snapshot_bytes,"response_bytes":len(json.dumps(listing))}
        evidence["classification_time_seconds"]={}
        for size in [100,1000]:
            samples=[{"reference":{"keywords":[f"term-{i}"]},"output":{"keywords":[f"term-{i}"]},"status":"success"} for i in range(size)]
            begin=time.perf_counter()
            compare_fields(samples,[{"name":"keywords","reference_path":"/keywords","output_path":"/keywords"}])
            evidence["classification_time_seconds"][str(size)]=round(time.perf_counter()-begin,3)
        app.state.worker_task=SimpleNamespace(done=lambda:True)
        evidence["failed_worker"]={"health":client.get('/api/health').status_code,"catalog_still_served":client.get('/api/catalog/plans').status_code}
        del app.state.worker_task
        viewer=client.post('/api/users',headers=headers,json={"username":"audit-viewer","password":"Audit-viewer-password!","role":"viewer"})
        viewer_login=client.post('/api/auth/login',json={"username":"audit-viewer","password":"Audit-viewer-password!"})
        evidence["custom_auth_header_public"]["viewer_can_read_credential"]= "synthetic-credential-marker" in client.get('/api/catalog/services').text
print(json.dumps(evidence,indent=2))
