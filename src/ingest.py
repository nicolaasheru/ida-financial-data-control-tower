from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from .config import API_URL, DATASET_ID, RAW_FILE, RESOURCE_ID


def fetch_all(page_size: int = 1000, timeout: int = 60) -> dict:
    """Fetch every page from the official WBG Finances API."""
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
        url = f"{API_URL}?{urlencode(params)}"
        request = Request(
            url,
            headers={
                "User-Agent": "IDA-Financial-Control-Tower/0.1 "
                "(public-data research prototype)"
            },
        )
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        page = payload.get("data", [])
        if expected_count is None:
            expected_count = int(payload.get("count", 0))
        records.extend(page)
        if len(page) < page_size:
            break

    if expected_count is not None and len(records) != expected_count:
        raise RuntimeError(
            f"Incomplete extraction: received {len(records):,} of "
            f"{expected_count:,} records."
        )
    return {"count": len(records), "data": records}


def persist_raw(payload: dict, path: Path = RAW_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_raw(path: Path = RAW_FILE, refresh: bool = False) -> pd.DataFrame:
    if refresh or not path.exists():
        payload = fetch_all()
        persist_raw(payload, path)
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
    return pd.DataFrame(payload["data"])
