"""Helpers to build OpenAI-compatible clients for OpenAI or Vertex AI."""

from __future__ import annotations

from typing import Dict, Any
import json

import google.auth
import google.auth.transport.requests
from google.oauth2 import service_account

from resident_agent.core.config import Settings


_CLOUD_PLATFORM_SCOPE = ["https://www.googleapis.com/auth/cloud-platform"]


def _vertex_base_url(settings: Settings) -> str:
    if not settings.vertex_project_id:
        raise ValueError(
            "VERTEX_PROJECT_ID is required when VERTEX_AI_ENABLED=true."
        )

    return (
        "https://aiplatform.googleapis.com/v1/"
        f"projects/{settings.vertex_project_id}/"
        f"locations/{settings.vertex_location}/endpoints/openapi"
    )


def _vertex_credentials(settings: Settings):
    if settings.vertex_service_account_json:
        info = json.loads(settings.vertex_service_account_json)
        return service_account.Credentials.from_service_account_info(
            info,
            scopes=_CLOUD_PLATFORM_SCOPE,
        )

    credentials, _ = google.auth.default(scopes=_CLOUD_PLATFORM_SCOPE)
    return credentials


def _vertex_access_token(settings: Settings) -> str:
    credentials = _vertex_credentials(settings)
    credentials.refresh(google.auth.transport.requests.Request())
    return credentials.token


def build_openai_client_kwargs(settings: Settings) -> Dict[str, Any]:
    """Build AsyncOpenAI kwargs for either OpenAI or Vertex AI mode."""
    if settings.vertex_ai_enabled:
        return {
            "api_key": _vertex_access_token(settings),
            "base_url": _vertex_base_url(settings),
        }

    kwargs: Dict[str, Any] = {"api_key": settings.openai_api_key}
    if settings.openai_api_base_url:
        kwargs["base_url"] = settings.openai_api_base_url
    return kwargs
