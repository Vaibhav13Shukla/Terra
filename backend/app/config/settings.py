"""Application configuration (§65 — environment management).

Reads from environment variables / .env (see ../../.env.example). No secrets
live here or in git — only configuration. Every field has a safe local-dev
default so the app and test suite run with zero setup (§61).
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    aws_region: str = "us-west-2"

    terra_provider: str = "sentinel-2-l2a"
    stac_url: str = "https://earth-search.aws.element84.com/v1"

    s3_results_bucket: str | None = None
    dynamodb_table: str | None = None

    bedrock_enabled: bool = False
    bedrock_model_id: str = "anthropic.claude-3-5-haiku-20241022-v1:0"

    # 'memory' (default, local/dev/tests) or 'dynamodb' (deployed)
    terra_job_store: str = "memory"


@lru_cache
def get_settings() -> Settings:
    return Settings()
