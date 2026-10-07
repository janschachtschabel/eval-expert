from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EVAL_", env_file=".env", extra="ignore")
    data_dir: str = "./data"
    secret_key: str = ""
    admin_username: str = "admin"
    admin_password: str = ""
    secure_cookie: bool = True
    allowed_hosts: str = ""
    session_hours: int = 12
    frontend_dir: str = "frontend/dist/browser"

    def validate_runtime(self):
        if len(self.secret_key) < 32 or "replace" in self.secret_key.lower():
            raise ValueError(
                "EVAL_SECRET_KEY must be a generated secret of at least 32 characters."
            )
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
