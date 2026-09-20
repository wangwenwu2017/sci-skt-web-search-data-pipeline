"""Reuse runtime policy; keep search settings separate and credentials out of artifacts."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from sci_pipeline.config import ApiSettings, RunConfig, read_environment


class SourceRunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    execution: RunConfig = Field(default_factory=RunConfig)
    search_provider: Literal["tavily"] = "tavily"
    search_timeout_sec: int = Field(default=60, ge=5, le=300)
    policy_version: Literal["source-v1"] = "source-v1"


class SourceApiSettings(ApiSettings):
    tavily_api_key: SecretStr

    @classmethod
    def load(cls, env_file: Path):
        values = read_environment(env_file)
        key = (values.get("TAVILY_API_KEY") or "").strip()
        if not key:
            raise ValueError("Missing settings: TAVILY_API_KEY")
        return cls(**ApiSettings.load(env_file).model_dump(), tavily_api_key=key)

    def environment(self) -> dict[str, str]:
        return {**super().environment(), "TAVILY_API_KEY": self.tavily_api_key.get_secret_value()}
