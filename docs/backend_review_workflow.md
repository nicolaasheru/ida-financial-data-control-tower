# Phase 3 — Analyst review backend

## Purpose

The review service turns the dashboard from a read-only investigation surface
into a persistent human-control workflow. The anomaly model creates and
prioritizes alerts; it cannot resolve its own output.

## Architecture

- **FastAPI** exposes review and audit endpoints.
- **SQLite** provides transactional local persistence.
- **Optimistic version checks** reject stale updates.
- **Append-only review events** preserve status and outcome history.
- **The Python pipeline** reads the database when present and otherwise falls
  back to `artifacts/reviews.csv`.
- **The dashboard** falls back to its synchronized static snapshot if the API
  is offline.

## Status transitions

```text
Pending → In Review → Resolved
                       ↓
                  In Review (reopen)
```

- Pending alerts cannot have an outcome.
- In-review alerts may remain without an outcome or use
  `needs_more_information`.
- Resolved alerts require a final outcome, reviewer, notes, and confidence.
- Final outcomes are `confirmed_data_issue`, `legitimate_exception`, and
  `false_positive`.

## Endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/health` | Service health |
| GET | `/api/reviews` | Persisted review records |
| GET | `/api/reviews/{row_id}` | Current review or default pending state |
| GET | `/api/reviews/{row_id}/history` | Append-only audit history |
| PUT | `/api/reviews/{row_id}` | Validated versioned review update |

## Local operation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd dashboard && npm install && cd ..
bash scripts/run-full-stack.sh
```

The API runs at `http://127.0.0.1:8000`; interactive API documentation is
available at `/docs`. Vite prints the dashboard URL in the terminal.

## Production direction

SQLite is intentionally local. The Azure design will replace it with Azure
Database for PostgreSQL while preserving the API contract, transition rules,
version checks, and audit-event model.
