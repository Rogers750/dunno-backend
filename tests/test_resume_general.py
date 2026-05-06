from types import SimpleNamespace

from fastapi.testclient import TestClient

from main import app


def test_generate_general_resume_and_cover_no_auth():
    client = TestClient(app)
    resp = client.post("/resume/general")
    assert resp.status_code in (401, 403)


def test_generate_general_resume_and_cover_success(monkeypatch):
    import routers.resume as resume_router

    expected = {
        "resume_json": {"basics": {"name": "Test User"}},
        "cover_letter": "Test cover letter",
    }

    monkeypatch.setattr(
        resume_router,
        "_get_user",
        lambda credentials: SimpleNamespace(id="user-123"),
    )

    import jobs.crew as crew

    monkeypatch.setattr(
        crew,
        "build_general_resume_and_cover",
        lambda user_id: expected,
    )

    client = TestClient(app)
    resp = client.post("/resume/general", headers={"Authorization": "Bearer test-token"})

    assert resp.status_code == 200
    assert resp.json() == expected


def test_get_general_resume_and_cover_success(monkeypatch):
    import routers.resume as resume_router

    monkeypatch.setattr(
        resume_router,
        "_get_user",
        lambda credentials: SimpleNamespace(id="user-123"),
    )

    class FakeTable:
        def select(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def execute(self):
            return SimpleNamespace(
                data=[{
                    "general_resume_json": {"basics": {"name": "Test User"}},
                    "general_cover_letter": "Saved cover letter",
                }]
            )

    class FakeSupabase:
        def table(self, _name):
            return FakeTable()

    monkeypatch.setattr(
        resume_router,
        "_get_user_supabase",
        lambda credentials: FakeSupabase(),
    )

    client = TestClient(app)
    resp = client.get("/resume/general", headers={"Authorization": "Bearer test-token"})

    assert resp.status_code == 200
    assert resp.json() == {
        "resume_json": {"basics": {"name": "Test User"}},
        "cover_letter": "Saved cover letter",
    }
