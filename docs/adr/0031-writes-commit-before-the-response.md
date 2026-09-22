# 0031 — A request's writes are committed before its response is sent

- **Status:** accepted
- **Date:** 2026-09-22
- **Deciders:** Eduardo
- **Tags:** transactions, correctness, api

## Context

Endpoints commit through `get_db`: the session commits when the dependency's
`yield` returns. FastAPI gives a generator dependency the `"request"` scope by
default, and that scope's exit stack closes **after** `await response(...)` —
the client has the status code before the commit has run
(`fastapi/routing.py`, `request_response`).

Two consequences. A client told `201` could read straight back and miss the
row: the quick patient-create e2e did, on CI's slower disk, while it always
passed locally. And a commit that failed after the response reported success
for data that was then rolled back.

Nothing in the suite could see it. `httpx`'s `ASGITransport` waits for the
whole app before returning, and `BaseHTTPMiddleware` runs the app in a task of
its own.

## Decision

The app mounts one dependency on every route,
`Depends(commit_before_response, scope="function")`
(`backend/app/main.py`). A `"function"`-scoped exit runs as the endpoint
returns, before the response is sent, and this one commits the request's
session. It is the same cached session the endpoint got from `Depends(get_db)`.

`get_db` keeps opening and closing the session at request scope. Its own
commit stays as the fallback for work done while a response streams.

## Consequences

### Good

- A success status means the data is durable. An immediate read finds it.
- A failed commit is the response (500) instead of a lie told first.
- One line covers all 436 `Depends(get_db)` sites and every module router:
  they are mounted onto `app.router` and inherit its dependencies.

### Bad / accepted trade-offs

- **Event handlers now run before the response**, not after it. They
  dispatch at commit (ADR 0019), and the commit moved. A slow handler adds
  to the request's latency. The bus contract already says a handler that
  must not block schedules its own background task.
- Every route opens a session, including ones that never touch the
  database. It is lazy — no connection is checked out until a query runs —
  so the cost is an object, not a round trip.

## Alternatives considered

- **`Depends(get_db, scope="function")` at every site.** 436 edits. And a
  function-scoped session closes before a `StreamingResponse` body runs, so
  every streaming endpoint would need an exception.
- **Explicit `await db.commit()` in each endpoint.** The rule nobody keeps
  across 436 sites, and new endpoints would silently fall back to the late
  commit.
- **Fix the e2e with a retry.** It would hide a real defect that production
  shares.

## How to verify the rule still holds

- `backend/tests/test_commit_before_response.py` drives `app.router`
  directly, so `send` runs inline in the app's own order, and looks for the
  created row from a separate connection at `http.response.start`. It fails
  without the app-level dependency.

## References

- `backend/app/database.py` — `get_db`, `commit_before_response`
- `backend/app/main.py` — `FastAPI(dependencies=[...])`
- `frontend/tests/e2e/agenda-quick-patient-create.spec.ts`
- ADR 0019 — events dispatch at commit
