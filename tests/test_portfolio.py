"""
Portfolio endpoint tests.

POST  /portfolio/generate       → AI generation (marked slow — costs money)
GET   /portfolio/me             → own portfolio
PATCH /portfolio/me/section     → edit a section
PATCH /portfolio/template       → change template
POST  /portfolio/publish        → toggle published
GET   /portfolio/{username}     → public, no auth
"""
import pytest


# ── Own portfolio ─────────────────────────────────────────────────────────────

def test_get_own_portfolio_no_auth(client):
    resp = client.get("/portfolio/me")
    assert resp.status_code in (401, 403)


def test_get_own_portfolio(client, auth):
    resp = client.get("/portfolio/me", headers=auth)
    # 200 if already generated, 404 if fresh account
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        body = resp.json()
        assert "theme_color" in body
        assert "selected_template" in body
        assert "published" in body


def test_update_template(client, auth):
    resp = client.patch(
        "/portfolio/template",
        json={"selected_template": "modern_dark", "theme_color": "emerald"},
        headers=auth,
    )
    # 200 if portfolio exists, 404 if not yet generated
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        assert resp.json()["selected_template"] == "modern_dark"


def test_publish_toggle(client, auth):
    # Read current state first
    me = client.get("/portfolio/me", headers=auth)
    if me.status_code == 404:
        pytest.skip("no portfolio yet — generate first")

    current = me.json()["published"]

    resp = client.post(
        "/portfolio/publish",
        json={"published": not current},
        headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()["published"] == (not current)

    # Restore original state
    client.post("/portfolio/publish", json={"published": current}, headers=auth)


def test_edit_section_invalid(client, auth):
    resp = client.patch(
        "/portfolio/me/section",
        json={"section": "nonexistent", "data": {}},
        headers=auth,
    )
    assert resp.status_code == 400


def test_edit_section_personal(client, auth):
    me = client.get("/portfolio/me", headers=auth)
    if me.status_code == 404:
        pytest.skip("no portfolio yet")

    resp = client.patch(
        "/portfolio/me/section",
        json={
            "section": "personal",
            "data": {"bio": "Updated test bio — testing section edit."},
        },
        headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] is True


# ── Public portfolio ──────────────────────────────────────────────────────────

def test_public_portfolio_nonexistent(client):
    resp = client.get("/portfolio/this-user-does-not-exist-xyz123")
    assert resp.status_code == 404


def test_public_portfolio(client, auth):
    # Get our own username first
    me = client.get("/auth/me", headers=auth).json()
    username = me["username"]

    # Make sure portfolio is published
    pub = client.post("/portfolio/publish", json={"published": True}, headers=auth)
    if pub.status_code == 404:
        pytest.skip("no portfolio yet — generate first")

    resp = client.get(f"/portfolio/{username}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == username
    assert "generated_content" in body
    assert "theme_color" in body
    assert "selected_template" in body

    # Must include Cache-Control header for CDN
    assert "cache-control" in resp.headers


def test_public_portfolio_unpublished(client, auth):
    me = client.get("/auth/me", headers=auth).json()
    username = me["username"]

    client.post("/portfolio/publish", json={"published": False}, headers=auth)
    resp = client.get(f"/portfolio/{username}")
    assert resp.status_code == 404

    # Restore
    client.post("/portfolio/publish", json={"published": True}, headers=auth)


# ── Slow: actual AI generation ────────────────────────────────────────────────

@pytest.mark.slow
def test_generate_portfolio(client, auth):
    resp = client.post(
        "/portfolio/generate",
        json={"target_roles": ["Senior Data Engineer", "MLOps Engineer"]},
        headers=auth,
        timeout=120,
    )
    assert resp.status_code == 200, f"generate failed: {resp.text}"
    body = resp.json()
    assert "portfolio_id" in body
    assert "generated_content" in body
    gc = body["generated_content"]
    assert "personal" in gc
    assert "skills" in gc
    assert "experience" in gc
    assert "projects" in gc
    assert "education" in gc
