"""Local maintenance commands. Access to the application filesystem is required."""

import argparse
import getpass

from .auth import hasher
from .config import Settings
from .database import Database


def reset_password(db, username, password):
    if len(password) < 12:
        raise ValueError("Passwords must contain at least 12 characters.")
    with db.connect() as connection:
        user = connection.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if not user:
            raise ValueError("User not found.")
        connection.execute(
            "UPDATE users SET password=? WHERE id=?", (hasher.hash(password), user["id"])
        )
        connection.execute("DELETE FROM sessions WHERE user_id=?", (user["id"],))
    db.audit(user["id"], "password.reset")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["reset-password"])
    parser.add_argument("username")
    args = parser.parse_args()
    password = getpass.getpass("New password: ")
    if password != getpass.getpass("Repeat password: "):
        raise SystemExit("Passwords did not match.")
    try:
        reset_password(Database(Settings().data_dir), args.username, password)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    print("Password updated and all existing sessions revoked.")
