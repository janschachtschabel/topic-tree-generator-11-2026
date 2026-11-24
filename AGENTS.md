# Project: topic-tree-generator (Themenbaum-Dienst)

FastAPI service that generates edu-sharing collection structures ("Themenbäume")
with an LLM. v1 endpoint `/generate-topic-tree` must stay format-compatible;
v2 lives at `POST /v2/topic-tree`. Active plan: `docs/plans/2026-11-24-topic-tree-v2.md`
(read it first; tick task checkboxes there as you go).

## Tech stack
- Python 3.13, FastAPI, Pydantic v2, pydantic-settings, openai SDK (async), loguru
- Dependency manager: uv (`uv.lock` is committed)
- Runtime: gunicorn + uvicorn-worker; prometheus-client (multiprocess)
- Tests: pytest; lint/format: ruff (line length 120)

## Commands
- Install: `uv sync`
- Test:    `uv run pytest -q`
- Lint:    `uv run ruff check` and `uv run ruff format --check`
- Run dev: `uv run python -m app` (public :8000, internal :9000)
- Helm:    `helm lint --strict deploy/helm/topic-tree` (once the chart exists)

## Conventions
- Identifiers, comments, docstrings, README, commit messages: English.
  Plans/design docs: German (team language). LLM prompts and user-facing API texts: German.
- TDD: write the failing test first; every bug fix gets a regression test.
- Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`); one logical change per commit.
- Work on a feature branch; never commit to `main` without the owner's consent.
- No new dependency without a one-line justification in the plan or commit body.

## Architecture rules
- Code lives in `app/`; `tests/` mirrors it. Dependencies point inward:
  `api` → `pipeline` → `domain`/`schemas`; `llm`, `vocab`, `context` are infrastructure used by `pipeline`/`api`.
  `domain/` and `schemas/` import nothing from `api/`, `pipeline/` or `llm/`.
- Files ≤ ~300 lines, functions ≤ ~50 lines; split by responsibility before crossing.
- All prompts live as files in `app/prompts/`. The system prompt (`system.md`) is static and identical for
  every LLM call (provider prompt caching). Never put request-specific text into it.
- Deterministic work (parsing, shape checks, applying change ops, key generation) is plain code, not LLM.

## Rules (must hold)
- The service never calls the edu-sharing repository. `nodeId` values are passed through unchanged.
- A delegation token (`Authorization: Bearer bdt_…`) is forwarded unchanged to the b-api and nothing else;
  never log, store or reformat it. Never send `X-API-KEY` or `X-Edu-*` headers.
- No silent gaps: every failed LLM step yields an entry in `warnings`; never return a partial tree without one.
- LLM calls never stream (the b-api cuts streams after ~30 s).
- Error responses are JSON `{"error": {"code", "message", "trace_id"}}`; never echo exception text to clients.
- Fetching `ref` URLs only from hosts in `REF_ALLOWED_HOSTS`, with size and time limits.
- Secrets only from env; never in logs, OpenAPI examples, or tests' fixtures that resemble real keys.
