"""
Jobs endpoint tests.

PATCH /profile/ctc         → update CTC
GET   /jobs                → list matched jobs
GET   /jobs/{id}           → full job detail
GET   /jobs/{id}/resume    → resume JSON
GET   /jobs/{id}/cover     → cover letter
GET   /jobs/{id}/projects  → project suggestions
GET   /jobs/{id}/company   → company info
POST  /jobs/{id}/apply     → mark applied
"""
import pytest


# ── CTC ───────────────────────────────────────────────────────────────────────

def test_update_ctc(client, auth):
    resp = client.patch(
        "/profile/ctc",
        json={"current_base_in_lakhs": 18.0, "expected_base_in_lakhs": 25.0},
        headers=auth,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ctc"]["current_base_in_lakhs"] == 18.0
    assert body["ctc"]["expected_base_in_lakhs"] == 25.0


def test_update_ctc_invalid(client, auth):
    # Negative values must be rejected (gt=0 validator)
    resp = client.patch(
        "/profile/ctc",
        json={"current_base_in_lakhs": -5.0, "expected_base_in_lakhs": 25.0},
        headers=auth,
    )
    assert resp.status_code == 422


def test_update_ctc_missing_field(client, auth):
    resp = client.patch(
        "/profile/ctc",
        json={"current_base_in_lakhs": 18.0},
        headers=auth,
    )
    assert resp.status_code == 422


def test_update_ctc_no_auth(client):
    resp = client.patch(
        "/profile/ctc",
        json={"current_base_in_lakhs": 18.0, "expected_base_in_lakhs": 25.0},
    )
    assert resp.status_code in (401, 403)


# ── Jobs list ─────────────────────────────────────────────────────────────────

def test_list_jobs_no_auth(client):
    resp = client.get("/jobs")
    assert resp.status_code in (401, 403)


def test_list_jobs(client, auth):
    resp = client.get("/jobs", headers=auth)
    assert resp.status_code == 200
    jobs = resp.json()
    assert isinstance(jobs, list)
    # Jobs crew may not have run yet on a fresh account
    if jobs:
        first = jobs[0]
        assert "id" in first
        assert "job" in first
        assert "match_score" in first
        assert "status" in first
        assert first["status"] != "applied"
        # Sorted by score DESC
        scores = [j["match_score"] for j in jobs]
        assert scores == sorted(scores, reverse=True)


def test_list_jobs_max_10(client, auth):
    resp = client.get("/jobs", headers=auth)
    assert resp.status_code == 200
    assert len(resp.json()) <= 10


# ── Individual job detail ─────────────────────────────────────────────────────

def _first_job_id(client, auth) -> str | None:
    jobs = client.get("/jobs", headers=auth).json()
    return jobs[0]["id"] if jobs else None


def test_get_job_detail(client, auth):
    match_id = _first_job_id(client, auth)
    if not match_id:
        pytest.skip("no matched jobs yet — run jobs crew first")

    resp = client.get(f"/jobs/{match_id}", headers=auth)
    assert resp.status_code == 200
    body = resp.json()
    assert "job" in body
    assert "match_score" in body
    assert "score_breakdown" in body
    assert "company_info" in body
    assert "resume_json" in body
    assert "cover_letter" in body
    assert "project_suggestions" in body


def test_get_job_not_found(client, auth):
    resp = client.get("/jobs/00000000-0000-0000-0000-000000000000", headers=auth)
    assert resp.status_code == 404


def test_get_resume_json(client, auth):
    match_id = _first_job_id(client, auth)
    if not match_id:
        pytest.skip("no matched jobs yet")

    resp = client.get(f"/jobs/{match_id}/resume", headers=auth)
    assert resp.status_code == 200
    assert "resume_json" in resp.json()


def test_get_cover_letter(client, auth):
    match_id = _first_job_id(client, auth)
    if not match_id:
        pytest.skip("no matched jobs yet")

    resp = client.get(f"/jobs/{match_id}/cover", headers=auth)
    assert resp.status_code == 200
    assert "cover_letter" in resp.json()


def test_get_project_suggestions(client, auth):
    match_id = _first_job_id(client, auth)
    if not match_id:
        pytest.skip("no matched jobs yet")

    resp = client.get(f"/jobs/{match_id}/projects", headers=auth)
    assert resp.status_code == 200
    suggestions = resp.json()["project_suggestions"]
    assert isinstance(suggestions, list)
    if suggestions:
        assert len(suggestions) == 3
        for s in suggestions:
            assert "name" in s
            assert "difficulty" in s
            assert s["difficulty"] in ("easy", "medium", "hard")


def test_get_company_info(client, auth):
    match_id = _first_job_id(client, auth)
    if not match_id:
        pytest.skip("no matched jobs yet")

    resp = client.get(f"/jobs/{match_id}/company", headers=auth)
    assert resp.status_code == 200
    info = resp.json()["company_info"]
    assert isinstance(info, dict)


# ── Apply ─────────────────────────────────────────────────────────────────────

def test_apply_not_found(client, auth):
    resp = client.post("/jobs/00000000-0000-0000-0000-000000000000/apply", headers=auth)
    assert resp.status_code == 404


def test_apply_job(client, auth):
    jobs = client.get("/jobs", headers=auth).json()
    if not jobs:
        pytest.skip("no matched jobs yet")

    match_id = jobs[-1]["id"]  # use the lowest-scored job to avoid disrupting top matches
    resp = client.post(f"/jobs/{match_id}/apply", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["status"] == "applied"

    # Applied jobs must not appear in /jobs list
    remaining = client.get("/jobs", headers=auth).json()
    ids_in_list = [j["id"] for j in remaining]
    assert match_id not in ids_in_list


# ── Slow: full jobs crew via trigger ─────────────────────────────────────────

@pytest.mark.slow
def test_generate_triggers_jobs_crew(client, auth):
    """
    Generating a portfolio kicks off the jobs crew as a background task.
    This test waits for the task to complete and verifies jobs appear.
    WARNING: costs DeepSeek + Apify credits.
    """
    import time

    resp = client.post(
        "/portfolio/generate",
        json={"target_roles": ["Senior Data Engineer"]},
        headers=auth,
        timeout=120,
    )
    assert resp.status_code == 200

    # Poll for up to 3 minutes for jobs to appear
    for _ in range(18):
        time.sleep(10)
        jobs = client.get("/jobs", headers=auth).json()
        if jobs:
            assert jobs[0]["match_score"] > 0
            return

    pytest.fail("Jobs crew did not produce results within 3 minutes")
