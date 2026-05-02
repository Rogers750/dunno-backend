LOCAL_URL  = http://localhost:8000
PROD_URL   = https://dunno-backend-production.up.railway.app

.PHONY: dev install test test-fast test-slow test-auth test-resume test-links test-portfolio test-jobs test-prod

# ── Dev server ────────────────────────────────────────────────────────────────

dev:
	uv run uvicorn main:app --reload --port 8000

# ── Dependencies ──────────────────────────────────────────────────────────────

install:
	uv pip install -r requirements-dev.txt

# ── Tests (against local server by default) ───────────────────────────────────

test:
	TEST_BASE_URL=$(LOCAL_URL) uv run pytest tests/ -v --tb=short -m "not slow"

test-fast: test

test-slow:
	TEST_BASE_URL=$(LOCAL_URL) uv run pytest tests/ -v --tb=short -m slow

test-auth:
	TEST_BASE_URL=$(LOCAL_URL) uv run pytest tests/test_auth.py -v

test-resume:
	TEST_BASE_URL=$(LOCAL_URL) uv run pytest tests/test_resume.py -v

test-links:
	TEST_BASE_URL=$(LOCAL_URL) uv run pytest tests/test_links.py -v

test-portfolio:
	TEST_BASE_URL=$(LOCAL_URL) uv run pytest tests/test_portfolio.py -v -m "not slow"

test-jobs:
	TEST_BASE_URL=$(LOCAL_URL) uv run pytest tests/test_jobs.py -v -m "not slow"

# ── Tests against production Railway deployment ───────────────────────────────

test-prod:
	TEST_BASE_URL=$(PROD_URL) uv run pytest tests/ -v --tb=short -m "not slow"

test-prod-slow:
	TEST_BASE_URL=$(PROD_URL) uv run pytest tests/ -v --tb=short -m slow
