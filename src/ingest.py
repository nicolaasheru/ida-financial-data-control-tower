from __future__ import annotations

import json
import time
from json import JSONDecodeError
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from .config import API_URL, DATASET_ID, RAW_FILE, RESOURCE_ID


TRANSIENT_HTTP_CODES = {408, 429, 500, 502, 503, 504}
MAX_PAGE_ATTEMPTS = 4
BASE_BACKOFF_SECONDS = 0.5


class IngestionError(RuntimeError):
    """Raised when the public source cannot be extracted without ambiguity."""


def _validate_page(payload: object) -> tuple[int, list[dict]]:
    if not isinstance(payload, dict):
        raise IngestionError("Source response must be a JSON object.")
    data = payload.get("data")
    if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
        raise IngestionError("Source response field 'data' must be a list of records.")
    try:
        count = int(payload["count"])
    except (KeyError, TypeError, ValueError) as error:
        raise IngestionError(
            "Source response field 'count' must be a non-negative integer."
        ) from error
    if count < 0:
        raise IngestionError("Source response count cannot be negative.")
    return count, data


def _request_page(
    request: Request,
    *,
    timeout: int,
    max_attempts: int,
    base_backoff_seconds: float,
    opener: Callable = urlopen,
    sleeper: Callable[[float], None] = time.sleep,
) -> tuple[int, list[dict]]:
    for attempt in range(1, max_attempts + 1):
        try:
            with opener(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return _validate_page(payload)
        except HTTPError as error:
            if error.code not in TRANSIENT_HTTP_CODES or attempt == max_attempts:
                raise IngestionError(
                    f"Source request failed with HTTP {error.code} after "
                    f"{attempt} attempt(s)."
                ) from error
        except (URLError, TimeoutError, JSONDecodeError) as error:
            if attempt == max_attempts:
                raise IngestionError(
                    f"Source request failed after {attempt} attempt(s): {error}"
                ) from error
        sleeper(base_backoff_seconds * (2 ** (attempt - 1)))
    raise AssertionError("Retry loop exited unexpectedly.")


def fetch_all(
    page_size: int = 1000,
    timeout: int = 60,
    *,
    max_attempts: int = MAX_PAGE_ATTEMPTS,
    base_backoff_seconds: float = BASE_BACKOFF_SECONDS,
    opener: Callable = urlopen,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict:
    """Fetch a complete, internally consistent snapshot of the WBG dataset."""
    if page_size <= 0:
        raise ValueError("page_size must be positive.")
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive.")

    records: list[dict] = []
    expected_count: int | None = None

    for skip in range(0, 1_000_000, page_size):
        params = {
            "datasetId": DATASET_ID,
            "resourceId": RESOURCE_ID,
            "top": page_size,
            "skip": skip,
            "type": "json",
        }
        request = Request(
            f"{API_URL}?{urlencode(params)}",
            headers={
                "User-Agent": "IDA-Financial-Control-Tower/0.1 "
                "(public-data research prototype)"
            },
        )
        page_count, page = _request_page(
            request,
            timeout=timeout,
            max_attempts=max_attempts,
            base_backoff_seconds=base_backoff_seconds,
            opener=opener,
            sleeper=sleeper,
        )
        if expected_count is None:
            expected_count = page_count
        elif page_count != expected_count:
            raise IngestionError(
                "Source record count changed during pagination "
                f"({expected_count:,} to {page_count:,}); extraction aborted "
                "to avoid mixing snapshots."
            )

        records.extend(page)
        if len(records) > expected_count:
            raise IngestionError(
                f"Source returned {len(records):,} records but declared "
                f"{expected_count:,}."
            )
        if len(records) == expected_count:
            break
        if not page or len(page) < page_size:
            break
    else:
        raise IngestionError("Pagination safety limit reached before completion.")

    expected_count = expected_count or 0
    if len(records) != expected_count:
        raise IngestionError(
            f"Incomplete extraction: received {len(records):,} of "
            f"{expected_count:,} records."
        )
    return {"count": len(records), "data": records}


def persist_raw(payload: dict, path: Path = RAW_FILE) -> None:
    """Atomically replace the cached snapshot only after a complete extraction."""
    count, data = _validate_page(payload)
    if len(data) != count:
        raise IngestionError(
            f"Refusing to persist {len(data):,} of {count:,} declared records."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary_path.replace(path)


def load_raw(path: Path = RAW_FILE, refresh: bool = False) -> pd.DataFrame:
    if refresh or not path.exists():
        payload = fetch_all()
        persist_raw(payload, path)
    else:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, JSONDecodeError) as error:
            raise IngestionError(f"Cached source snapshot is unreadable: {error}") from error
        count, data = _validate_page(payload)
        if len(data) != count:
            raise IngestionError(
                f"Cached source snapshot contains {len(data):,} of "
                f"{count:,} declared records."
            )
    return pd.DataFrame(payload["data"])
