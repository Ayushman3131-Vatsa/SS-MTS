from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.common.config import Settings


ALLOWED_CORS_METHODS = [
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "HEAD",
    "OPTIONS",
]
ALLOWED_CORS_HEADERS = [
    "Accept",
    "Authorization",
    "Content-Type",
    "X-CSRF-Token",
]


def configure_cors(app: FastAPI, settings: Settings) -> None:
    """Allow explicitly configured browser origins to use credentialed API calls."""

    if not settings.cors_origins:
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=ALLOWED_CORS_METHODS,
        allow_headers=ALLOWED_CORS_HEADERS,
    )
