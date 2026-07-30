from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.store import (
    ReviewConflictError,
    ReviewNotFoundError,
    ReviewStore,
    ReviewValidationError,
)


ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = Path(
    os.getenv("REVIEW_DATABASE_PATH", ROOT / "data" / "reviews.sqlite3")
)
CORS_ALLOWED_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]


class ReviewUpdate(BaseModel):
    review_status: str
    review_outcome: str = ""
    reviewer: str = Field(min_length=1, max_length=120)
    review_notes: str = Field(default="", max_length=5000)
    review_confidence: str = ""
    evidence_url: str = Field(default="", max_length=2000)
    expected_version: int = Field(ge=0)


def create_app(
    database_path: Path = DATABASE_PATH,
    alerts_path: Path = ROOT / "artifacts" / "alerts.csv",
    seed_reviews_path: Path | None = ROOT / "artifacts" / "reviews.csv",
) -> FastAPI:
    app = FastAPI(
        title="IDA Financial Data Control Tower Review API",
        version="0.1.0",
        description=(
            "Persistent human-review workflow for an independent portfolio "
            "prototype using public IDA financial data."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ALLOWED_ORIGINS,
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
        allow_credentials=False,
        allow_methods=["GET", "PUT"],
        allow_headers=["Content-Type"],
    )
    store = ReviewStore(
        database_path=database_path,
        alerts_path=alerts_path,
        seed_reviews_path=seed_reviews_path,
    )
    app.state.review_store = store

    @app.get("/")
    def root() -> dict:
        return {
            "service": "IDA Financial Data Control Tower Review API",
            "status": "healthy",
            "health": "/health",
            "documentation": "/docs",
        }

    @app.get("/health")
    def health() -> dict:
        return {"status": "healthy", "database": "sqlite"}

    @app.get("/api/reviews")
    def list_reviews() -> list[dict]:
        return store.list_reviews()

    @app.get("/api/reviews/{record_key}")
    def get_review(record_key: str) -> dict:
        try:
            return store.get_review(record_key)
        except ReviewNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/api/reviews/{record_key}/history")
    def get_review_history(record_key: str) -> list[dict]:
        try:
            return store.get_history(record_key)
        except ReviewNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.put("/api/reviews/{record_key}")
    def update_review(record_key: str, payload: ReviewUpdate) -> dict:
        try:
            return store.update_review(record_key, payload.model_dump())
        except ReviewNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ReviewValidationError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except ReviewConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    return app


app = create_app()
