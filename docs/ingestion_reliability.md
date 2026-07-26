# Ingestion reliability contract

## Objective

The ingestion layer must either produce one complete, internally consistent
public-data snapshot or fail without replacing the last valid cache.

## Retry policy

- Maximum four attempts per page.
- Exponential delays of 0.5, 1, and 2 seconds by default.
- Retries are limited to timeouts, connection failures, malformed JSON during
  transport, and HTTP 408, 429, 500, 502, 503, or 504.
- Non-transient client errors fail immediately.

## Integrity checks

- Responses must contain a non-negative integer `count` and a list of record
  objects in `data`.
- Every page must report the same source count.
- Extraction stops when the declared count is reached, not merely when a page
  happens to be short.
- More records than declared, an early empty or short page, or the pagination
  safety limit fails the run.
- Cached snapshots are validated again before conversion to a DataFrame.

## Persistence behavior

Successful refreshes are written to a temporary sibling file and atomically
replace the prior cache. An interrupted or rejected extraction cannot leave a
partially written snapshot at the production cache path.

## Deliberate limitation

The public API does not expose a snapshot token or transaction boundary. Count
consistency cannot prove that no values changed between pages, but it prevents
the most visible mixed-snapshot failure mode. A production source should provide
immutable extraction versions, checksums, lineage metadata, orchestration-level
retry, and operational alerting.
