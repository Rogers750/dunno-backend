"""
Resume endpoint tests.

POST /resume/upload   → upload PDF, extract text
GET  /resume/me       → get resume metadata
"""
import io
import pytest


def test_upload_resume(client, auth, sample_pdf):
    resp = client.post(
        "/resume/upload",
        files={"file": ("resume.pdf", io.BytesIO(sample_pdf), "application/pdf")},
        headers=auth,
    )
    assert resp.status_code == 200, f"upload failed: {resp.text}"
    body = resp.json()
    assert "id" in body
    assert "file_url" in body
    assert body["chars_extracted"] > 0


def test_upload_resume_no_auth(client, sample_pdf):
    resp = client.post(
        "/resume/upload",
        files={"file": ("resume.pdf", io.BytesIO(sample_pdf), "application/pdf")},
    )
    assert resp.status_code in (401, 403)


def test_upload_non_pdf(client, auth):
    resp = client.post(
        "/resume/upload",
        files={"file": ("resume.txt", io.BytesIO(b"not a pdf"), "text/plain")},
        headers=auth,
    )
    assert resp.status_code == 400


def test_get_resume(client, auth):
    resp = client.get("/resume/me", headers=auth)
    # 200 if resume was already uploaded, 404 if running against a clean account
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        body = resp.json()
        assert "id" in body
        assert "file_url" in body
