"""Generate local deployment secrets without displaying them in terminal logs."""

import argparse
import secrets
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--dev", action="store_true", help="Allow session cookies over local HTTP")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
destination = root / ".env"
if destination.exists():
    raise SystemExit(".env already exists; it was not overwritten.")
text = (root / ".env.example").read_text()
text = text.replace("EVAL_SECRET_KEY=\n", "EVAL_SECRET_KEY=" + secrets.token_urlsafe(48) + "\n")
text = text.replace("EVAL_ADMIN_PASSWORD=\n", "EVAL_ADMIN_PASSWORD=" + secrets.token_urlsafe(24) + "\n")
if args.dev:
    text = text.replace("EVAL_SECURE_COOKIE=true", "EVAL_SECURE_COOKIE=false")
destination.write_text(text, encoding="utf-8")
try:
    destination.chmod(0o600)
except OSError:
    pass
print("Created .env. Read EVAL_ADMIN_PASSWORD there; keep this file private.")
