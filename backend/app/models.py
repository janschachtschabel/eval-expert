from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Named(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)


class Service(Named):
    kind: Literal["http", "demo"] = "http"
    url: str = ""
    method: Literal["POST", "GET", "PUT", "PATCH"] = "POST"
    mapping: dict = Field(default_factory=lambda: {"$input": ""})
    headers: dict[str, str] = Field(default_factory=dict)
    auth_header: str = "Authorization"
    auth_prefix: str = "Bearer "
    timeout: int = Field(default=60, ge=1, le=180)
    response_schema: dict | None = None

    @field_validator("response_schema")
    @classmethod
    def local_schema(cls, value):
        if value:
            from .schemas import check_schema

            check_schema(value)
        return value

    @field_validator("headers")
    @classmethod
    def no_credentials_in_headers(cls, value):
        if any(key.lower() in {"authorization", "cookie", "x-api-key", "host"} for key in value):
            raise ValueError("Use the separate credential field for authentication headers.")
        return value

    @model_validator(mode="after")
    def separate_authentication(self):
        if self.auth_header.lower() in {key.lower() for key in self.headers}:
            raise ValueError(
                "Use the separate credential field for the configured authentication header."
            )
        return self


class Provider(Named):
    kind: Literal["openai", "bapi-openai", "bapi-academiccloud"] = "openai"
    base_url: str = "https://api.openai.com/v1"
    model: str = Field(min_length=1, max_length=160)
    token_parameter: Literal["max_tokens", "max_completion_tokens"] = "max_completion_tokens"
    max_tokens: int = Field(default=4096, ge=128, le=16384)
    temperature: float | None = Field(default=None, ge=0, le=2)
    json_mode: bool = False


class Criterion(Named):
    steps: list[str] = Field(min_length=1, max_length=12)
    threshold: float = Field(default=0.7, ge=0, le=1)
    output_path: str = Field(default="", pattern=r"^(/|$)")
    context_path: str = Field(default="/source", pattern=r"^(/|$)")
    context_source: Literal["input", "output"] = "input"
    require_context: bool = False


class Dataset(Named):
    cases: list[dict] = Field(min_length=1, max_length=1000)
    demo: bool = False


class FieldSpec(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    output_path: str = Field(pattern=r"^(/|$)")
    reference_path: str = Field(pattern=r"^(/|$)")
    aliases: dict[str, str] = Field(default_factory=dict)


class Plan(Named):
    service_id: str
    dataset_id: str
    mode: Literal["reference", "judge", "combined"] = "reference"
    fields: list[FieldSpec] = Field(default_factory=list, max_length=20)
    criterion_ids: list[str] = Field(default_factory=list, max_length=12)
    provider_id: str | None = None

    @model_validator(mode="after")
    def selected_mode(self):
        if self.mode == "judge":
            self.fields = []
        if self.mode == "reference":
            self.criterion_ids, self.provider_id = [], None
        if len({field.name for field in self.fields}) != len(self.fields):
            raise ValueError("Reference field names must be unique.")
        return self


class Schedule(Named):
    plan_id: str
    cron: str = "0 8 * * 1"
    timezone: str = "Europe/Berlin"
    enabled: bool = True


MODELS = {
    "services": Service,
    "providers": Provider,
    "criteria": Criterion,
    "datasets": Dataset,
    "plans": Plan,
    "schedules": Schedule,
}


class RunStart(BaseModel):
    plan_id: str = Field(min_length=1, max_length=100)


class SchedulePreview(BaseModel):
    cron: str = Field(min_length=1, max_length=100)
    timezone: str = Field(min_length=1, max_length=100)
