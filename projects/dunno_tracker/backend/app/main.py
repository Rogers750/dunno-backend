from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from app.config import settings
from app.routers import agents, people, events, fingerprints, sessions, dashboard
from app.auth import generate_api_key

app = FastAPI(
    title="Dunno Analytics API",
    description="LLM Analytics for AI Agents",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(agents.router)
app.include_router(people.router)
app.include_router(events.router)
app.include_router(fingerprints.router)
app.include_router(sessions.router)
app.include_router(dashboard.router)


@app.get("/")
def root():
    return {"name": "Voker Analytics API", "docs": "/docs", "health": "/health"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    from fastapi.responses import FileResponse
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "favicon.ico"))


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.post("/setup")
def setup(project_name: str = "DunnoAI", slug: str = "dunnoai", key_name: str = "Default"):
    """
    One-time bootstrap: creates the first project + API key.
    Returns the raw API key — copy it immediately, it won't be shown again.
    Disabled automatically once a project already exists.
    """
    from app.repositories import get_repo
    repo = get_repo()
    if repo.get_project_count() > 0:
        raise HTTPException(status_code=403, detail="Setup already complete. Use the dashboard to manage keys.")

    project = repo.create_project(project_name, slug)
    project_id = project["id"]

    raw_key, prefix, key_hash = generate_api_key()
    repo.insert_api_key(project_id, key_name, prefix, key_hash)

    return {
        "project_id": project_id,
        "project_name": project_name,
        "api_key": raw_key,
        "message": "Save this API key — it will not be shown again.",
    }
