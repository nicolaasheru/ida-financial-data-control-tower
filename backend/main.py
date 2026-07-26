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


class ReviewUpdate(BaseModel):
    review_status: str
    review_outcome: str = ""
    reviewer: str = Field(min_length=1, max_length=120)
    review_notes: str = Field(default="", max_length=5000)
    review_confidence: str = ""
    evidence_url: str = Field(default="", max_length=2000)
    expected_version: int = Field(ge=0)


def create_app(database_path: Path = DATABASE_PATH) -> FastAPI:
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
        allow_origins=[],
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
        allow_credentials=False,
        allow_methods=["GET", "PUT"],
        allow_headers=["Content-Type"],
    )
    store = ReviewStore(
        database_path=database_path,
        alerts_path=ROOT / "artifacts" / "alerts.csv",
        seed_reviews_path=ROOT / "artifacts" / "reviews.csv",
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

    @app.get("/api/reviews/{row_id}")
    def get_review(row_id: int) -> dict:
        try:
            return store.get_review(row_id)
        except ReviewNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/api/reviews/{row_id}/history")
    def get_review_history(row_id: int) -> list[dict]:
        try:
            return store.get_history(row_id)
        except ReviewNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.put("/api/reviews/{row_id}")
    def update_review(row_id: int, payload: ReviewUpdate) -> dict:
        try:
            return store.update_review(row_id, payload.model_dump())
        except ReviewNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ReviewValidationError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except ReviewConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    return app


app = create_app()
