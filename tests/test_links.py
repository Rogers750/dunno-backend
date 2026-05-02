"""
Links endpoint tests.

POST  /links/github          → add GitHub profile (fetches all repos)
GET   /links/me              → list all links
GET   /links/repos           → list repos with inclusion status
PATCH /links/{id}/toggle     → toggle included flag
"""
import pytest

GITHUB_PROFILE_URL = "https://github.com/Rogers750"
GITHUB_REPO_URL = "https://github.com/Rogers750/knowme"


def test_add_github_profile(client, auth):
    resp = client.post(
        "/links/github",
        json={"url": GITHUB_PROFILE_URL},
        headers=auth,
    )
    assert resp.status_code == 200, f"github link failed: {resp.text}"
    body = resp.json()
    assert body["type"] == "github_profile"
    assert "repos_saved" in body
    assert isinstance(body["repos_saved"], int)


def test_add_github_repo(client, auth):
    resp = client.post(
        "/links/github",
        json={"url": GITHUB_REPO_URL},
        headers=auth,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "github_repo"


def test_add_invalid_github_url(client, auth):
    resp = client.post(
        "/links/github",
        json={"url": "https://github.com/user/repo/extra/path"},
        headers=auth,
    )
    assert resp.status_code == 400


def test_add_link_no_auth(client):
    resp = client.post("/links/github", json={"url": GITHUB_PROFILE_URL})
    assert resp.status_code in (401, 403)


def test_get_links(client, auth):
    resp = client.get("/links/me", headers=auth)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_get_repos(client, auth):
    resp = client.get("/links/repos", headers=auth)
    assert resp.status_code == 200
    repos = resp.json()
    assert isinstance(repos, list)
    if repos:
        first = repos[0]
        assert "id" in first
        assert "included" in first
        assert "name" in first
        assert "url" in first
        assert "stars" in first


def test_toggle_repo(client, auth):
    repos = client.get("/links/repos", headers=auth).json()
    if not repos:
        pytest.skip("no repos available to toggle")

    repo = repos[0]
    original = repo["included"]

    resp = client.patch(f"/links/{repo['id']}/toggle", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["included"] == (not original)

    # Toggle back
    client.patch(f"/links/{repo['id']}/toggle", headers=auth)


def test_toggle_nonexistent(client, auth):
    resp = client.patch("/links/00000000-0000-0000-0000-000000000000/toggle", headers=auth)
    assert resp.status_code == 404
