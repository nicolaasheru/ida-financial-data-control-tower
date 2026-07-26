import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError

from src.ingest import IngestionError, fetch_all, load_raw, persist_raw


class MockResponse:
    def __init__(self, payload):
        self.body = (
            payload
            if isinstance(payload, bytes)
            else json.dumps(payload).encode("utf-8")
        )

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.body


class SequenceOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def __call__(self, request, timeout):
        response = self.responses[self.calls]
        self.calls += 1
        if isinstance(response, Exception):
            raise response
        return MockResponse(response)


class IngestionReliabilityTests(unittest.TestCase):
    def test_transient_network_failure_is_retried(self):
        opener = SequenceOpener(
            [
                URLError("temporary DNS failure"),
                {"count": 2, "data": [{"id": 1}, {"id": 2}]},
            ]
        )
        delays = []
        result = fetch_all(
            page_size=2,
            max_attempts=3,
            opener=opener,
            sleeper=delays.append,
        )
        self.assertEqual(result["count"], 2)
        self.assertEqual(opener.calls, 2)
        self.assertEqual(delays, [0.5])

    def test_transient_server_error_is_retried(self):
        error = HTTPError(
            url="https://example.invalid",
            code=503,
            msg="Unavailable",
            hdrs=None,
            fp=None,
        )
        opener = SequenceOpener(
            [error, {"count": 1, "data": [{"id": 1}]}]
        )
        result = fetch_all(
            page_size=1000,
            max_attempts=2,
            opener=opener,
            sleeper=lambda _: None,
        )
        self.assertEqual(result["count"], 1)

    def test_non_transient_client_error_fails_without_retry(self):
        error = HTTPError(
            url="https://example.invalid",
            code=400,
            msg="Bad request",
            hdrs=None,
            fp=None,
        )
        opener = SequenceOpener([error])
        with self.assertRaises(IngestionError):
            fetch_all(opener=opener, sleeper=lambda _: None)
        self.assertEqual(opener.calls, 1)

    def test_incomplete_extraction_is_rejected(self):
        opener = SequenceOpener(
            [
                {"count": 3, "data": [{"id": 1}, {"id": 2}]},
                {"count": 3, "data": []},
            ]
        )
        with self.assertRaisesRegex(IngestionError, "Incomplete extraction"):
            fetch_all(page_size=2, opener=opener, sleeper=lambda _: None)

    def test_count_change_during_pagination_is_rejected(self):
        opener = SequenceOpener(
            [
                {"count": 3, "data": [{"id": 1}, {"id": 2}]},
                {"count": 4, "data": [{"id": 3}]},
            ]
        )
        with self.assertRaisesRegex(IngestionError, "changed during pagination"):
            fetch_all(page_size=2, opener=opener, sleeper=lambda _: None)

    def test_malformed_payload_is_rejected(self):
        opener = SequenceOpener([{"count": 1, "data": "not-a-list"}])
        with self.assertRaisesRegex(IngestionError, "list of records"):
            fetch_all(opener=opener, sleeper=lambda _: None)

    def test_atomic_snapshot_round_trip_and_cache_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            payload = {"count": 1, "data": [{"id": 1}]}
            persist_raw(payload, path)
            frame = load_raw(path, refresh=False)
            self.assertEqual(frame.iloc[0]["id"], 1)
            self.assertFalse(path.with_suffix(".json.tmp").exists())

            path.write_text(
                json.dumps({"count": 2, "data": [{"id": 1}]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(IngestionError, "declared records"):
                load_raw(path, refresh=False)


if __name__ == "__main__":
    unittest.main()
