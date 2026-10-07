import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import auth, catalog, connections, demo, runs
from .config import Settings
from .database import Database

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "1")
os.environ.setdefault("DEEPEVAL_DISABLE_PROGRESS_BAR", "1")


def create_app(settings=None, start_worker=True):
    settings = settings or Settings()
    settings.validate_runtime()
    db = Database(settings.data_dir)
    from .credentials import migrate_credentials

    migrate_credentials(db, settings)
    auth.bootstrap(db, settings)

    @asynccontextmanager
    async def lifespan(app):
        task = None
        lock = None
        if start_worker:
            import portalocker

            from .worker_supervisor import supervise

            lock = portalocker.Lock(Path(settings.data_dir) / "worker.lock", timeout=0)
            lock.acquire()
            task = asyncio.create_task(supervise(app))
            app.state.worker_task = task
        yield
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if lock:
            lock.release()

    app = FastAPI(
        title="Eval Expert",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings
    app.state.db = db
    app.state.worker_state = "starting" if start_worker else "disabled"
    app.state.login_attempts = auth.login_state()
    app.state.dummy_password = auth.hasher.hash("not-an-account-" + os.urandom(16).hex())
    app.include_router(auth.router, prefix="/api")
    app.include_router(catalog.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")
    app.include_router(demo.router, prefix="/api")
    app.include_router(connections.router, prefix="/api")

    @app.middleware("http")
    async def request_limits(request: Request, call_next):
        try:
            if int(request.headers.get("content-length", "0")) > 6_000_000:
                return JSONResponse({"detail": "Request exceeds 6 MB."}, status_code=413)
        except ValueError:
            return JSONResponse({"detail": "Invalid content length."}, status_code=400)
        if request.method in ("POST", "PUT", "PATCH"):
            chunks, size = [], 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > 6_000_000:
                    return JSONResponse({"detail": "Request exceeds 6 MB."}, status_code=413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        return await call_next(request)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        else:
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/api/health")
    def health():
        task = getattr(app.state, "worker_task", None)
        state = app.state.worker_state
        if state in ("starting", "recovering", "failed") or (task and task.done()):
            return JSONResponse({"status": "worker_" + state}, status_code=503)
        with db.connect() as connection:
            connection.execute("SELECT 1")
        return {"status": "ok", "version": "0.1.0"}

    directory = Path(settings.frontend_dir)
    if directory.is_dir():
        app.mount(
            "/assets", StaticFiles(directory=directory / "assets", check_dir=False), name="assets"
        )

        @app.get("/{path:path}")
        def frontend(path: str):
            if path.startswith("api/"):
                return JSONResponse({"detail": "Not found."}, status_code=404)
            target = (directory / path).resolve()
            if target.is_relative_to(directory.resolve()) and target.is_file():
                return FileResponse(target)
            return FileResponse(directory / "index.html")

    return app
