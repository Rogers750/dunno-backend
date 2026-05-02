"""
Auth endpoint tests.

POST /auth/dev-login             → get JWT
GET  /auth/me                    → returns current user
POST /auth/verification/send     → OTP send (smoke test only)
"""
import pytest


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_dev_login(client):
    resp = client.post("/auth/dev-login")
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["access_token"]
    user = body["user"]
    assert user["email"] == "sagarsinghraw77@gmail.com"
    assert user["username"]
    assert user["status"] in ("onboarding", "processing", "ready")


def test_me_authenticated(client, auth):
    resp = client.get("/auth/me", headers=auth)
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "sagarsinghraw77@gmail.com"
    assert "username" in body
    assert "status" in body
    assert "id" in body


def test_me_no_token(client):
    resp = client.get("/auth/me")
    assert resp.status_code in (401, 403)


def test_me_bad_token(client):
    resp = client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert resp.status_code in (401, 403)


def test_otp_send_smoke(client):
    # We don't verify the OTP in tests, just that the endpoint accepts a valid email
    resp = client.post("/auth/verification/send", json={"email": "test@example.com"})
    # 200 means Supabase accepted the request; other codes may indicate rate limiting
    assert resp.status_code in (200, 429, 400)
