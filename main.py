import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)

from routers import auth, resume, links, portfolio
from jobs.router import jobs_router, profile_router
from jobs.cron import start_jobs_cron


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_jobs_cron()
    yield


app = FastAPI(title="KnowMe API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://0.0.0.0:3000",
        "http://127.0.0.1:3000",
        "https://knowme.vercel.app",
        "https://dunnoai.vercel.app",
        "https://dunno.app",
        "https://www.dunno.app",
        "https://dunnoai.com",
        "https://www.dunnoai.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(resume.router, prefix="/resume", tags=["resume"])
app.include_router(links.router, prefix="/links", tags=["links"])
app.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
app.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
app.include_router(profile_router, prefix="/profile", tags=["profile"])


@app.get("/health")
def health():
    return {"status": "ok"}
