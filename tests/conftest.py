"""
Shared fixtures for the integration test suite.

By default tests run against http://localhost:8000.
Point at Railway or any environment by setting TEST_BASE_URL:

    TEST_BASE_URL=https://dunno-backend-production.up.railway.app pytest tests/

All tests use the dev-login endpoint to authenticate as the seed user
(sagarsinghraw77@gmail.com). That endpoint must be available — it is
intentionally excluded from production in real deployments, but we keep
it for developer testing.

Expensive tests (portfolio generate, jobs crew) are marked @pytest.mark.slow
and skipped by default. Run them explicitly with:
    pytest tests/ -m slow
"""
import io
import os
import pytest
import httpx

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")


# ── Shared state (populated once per session) ─────────────────────────────────

_session: dict = {}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture(scope="session")
def client(base_url) -> httpx.Client:
    with httpx.Client(base_url=base_url, timeout=30) as c:
        yield c


@pytest.fixture(scope="session")
def token(client) -> str:
    """Authenticate once via dev-login and reuse the token for all tests."""
    resp = client.post("/auth/dev-login")
    assert resp.status_code == 200, f"dev-login failed: {resp.text}"
    t = resp.json()["access_token"]
    _session["token"] = t
    return t


@pytest.fixture(scope="session")
def auth(token) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def sample_pdf() -> bytes:
    """
    Minimal but valid PDF with resume-like content.
    Enough text for pypdf to extract and for DeepSeek to process.
    """
    content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length 280>>stream
BT
/F1 14 Tf
50 750 Td (Sagar Singh Rawal) Tj
0 -20 Td (Senior Data Engineer) Tj
/F1 11 Tf
0 -30 Td (EXPERIENCE) Tj
0 -18 Td (Dezerv  -  Senior Data Engineer  -  2022-Present) Tj
0 -14 Td (Built data pipelines processing 100M events per day.) Tj
0 -30 Td (SKILLS) Tj
0 -18 Td (Python, Spark, Kafka, Airflow, AWS, SQL, Flink) Tj
0 -30 Td (EDUCATION) Tj
0 -18 Td (NIT Kurukshetra  -  B.Tech Computer Science  -  2016-2020) Tj
ET
endstream
endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
xref
0 6
0000000000 65535 f\x20
0000000009 00000 n\x20
0000000058 00000 n\x20
0000000115 00000 n\x20
0000000274 00000 n\x20
0000000605 00000 n\x20
trailer<</Size 6/Root 1 0 R>>
startxref
678
%%EOF"""
    return content


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: marks tests as slow (AI calls, skipped by default)")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("-m", default="") == "slow":
        skip_slow = pytest.mark.skip(reason="slow test — run with: pytest -m slow")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
