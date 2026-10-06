import hashlib
import secrets
import time
from collections import defaultdict, deque

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .database import new_id

router = APIRouter()
hasher = PasswordHasher()


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


class NewUser(Login):
    role: str = "viewer"


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def cipher(settings):
    import base64

    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest()))


def bootstrap(db, settings):
    with db.connect() as connection:
        if connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            return
        if len(settings.admin_password) < 12:
            raise ValueError("Set EVAL_ADMIN_PASSWORD (at least 12 characters) for first startup.")
        connection.execute(
            "INSERT INTO users VALUES(?,?,?,?,1)",
            (new_id(), settings.admin_username, hasher.hash(settings.admin_password), "admin"),
        )


def current_user(request: Request):
    token = request.cookies.get("eval_session", "")
    with request.app.state.db.connect() as connection:
        row = connection.execute(
            """SELECT users.id,username,role,csrf FROM sessions
            JOIN users ON users.id=sessions.user_id
            WHERE token=? AND expires>? AND active=1""",
            (digest(token), time.time()),
        ).fetchone()
    if not row:
        raise HTTPException(401, "Please sign in.")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        provided = request.headers.get("x-csrf-token", "")
        if not secrets.compare_digest(provided, row["csrf"]):
            raise HTTPException(403, "Invalid CSRF token.")
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
            raise HTTPException(403, "Invalid request origin.")
    return dict(row)


def editors(user=Depends(current_user)):
    if user["role"] not in ("admin", "editor"):
        raise HTTPException(403, "Editor role required.")
    return user


def administrators(user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator role required.")
    return user


@router.post("/auth/login")
def login(body: Login, request: Request, response: Response):
    attempts = request.app.state.login_attempts
    key = (request.client.host if request.client else "unknown") + ":" + body.username
    recent = attempts[key]
    while recent and recent[0] < time.monotonic() - 300:
        recent.popleft()
    if len(recent) >= 10:
        raise HTTPException(429, "Too many attempts; wait five minutes.")
    recent.append(time.monotonic())
    db = request.app.state.db
    with db.connect() as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE username=? AND active=1", (body.username,)
        ).fetchone()
        password = row["password"] if row else request.app.state.dummy_password
        try:
            valid = hasher.verify(password, body.password)
        except VerificationError:
            valid = False
        if not valid or not row:
            raise HTTPException(401, "Invalid username or password.")
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        connection.execute("DELETE FROM sessions WHERE expires<=?", (time.time(),))
        connection.execute(
            "INSERT INTO sessions VALUES(?,?,?,?)",
            (
                digest(token),
                row["id"],
                csrf,
                time.time() + request.app.state.settings.session_hours * 3600,
            ),
        )
    recent.clear()
    response.set_cookie(
        "eval_session",
        token,
        httponly=True,
        secure=request.app.state.settings.secure_cookie,
        samesite="strict",
        max_age=request.app.state.settings.session_hours * 3600,
        path="/",
    )
    db.audit(row["id"], "login")
    return {
        "user": {"id": row["id"], "username": row["username"], "role": row["role"]},
        "csrf_token": csrf,
    }


@router.get("/auth/session")
def session(user=Depends(current_user)):
    return {
        "user": {key: user[key] for key in ("id", "username", "role")},
        "csrf_token": user["csrf"],
    }


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, user=Depends(current_user)):
    with request.app.state.db.connect() as connection:
        connection.execute(
            "DELETE FROM sessions WHERE token=?", (digest(request.cookies["eval_session"]),)
        )
    response.delete_cookie("eval_session", path="/")


@router.get("/users")
def users(request: Request, user=Depends(administrators)):
    with request.app.state.db.connect() as connection:
        return [
            dict(row) for row in connection.execute("SELECT id,username,role,active FROM users")
        ]


@router.post("/users")
def add_user(body: NewUser, request: Request, user=Depends(administrators)):
    if body.role not in ("admin", "editor", "reviewer", "viewer") or len(body.password) < 12:
        raise HTTPException(422, "Use a valid role and a password of at least 12 characters.")
    from sqlite3 import IntegrityError

    try:
        with request.app.state.db.connect() as connection:
            id = new_id()
            connection.execute(
                "INSERT INTO users VALUES(?,?,?,?,1)",
                (id, body.username, hasher.hash(body.password), body.role),
            )
    except IntegrityError as error:
        raise HTTPException(409, "Username already exists.") from error
    request.app.state.db.audit(user["id"], "user.created", id)
    return {"id": id, "username": body.username, "role": body.role}


@router.post("/users/{id}/disable", status_code=204)
def disable_user(id: str, request: Request, user=Depends(administrators)):
    if id == user["id"]:
        raise HTTPException(422, "Cannot disable your own account.")
    with request.app.state.db.connect() as connection:
        connection.execute("UPDATE users SET active=0 WHERE id=?", (id,))
        connection.execute("DELETE FROM sessions WHERE user_id=?", (id,))
    request.app.state.db.audit(user["id"], "user.disabled", id)


def login_state():
    return defaultdict(deque)
