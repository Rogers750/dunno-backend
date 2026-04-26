import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)

from routers import auth, resume, links

app = FastAPI(title="KnowMe API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://0.0.0.0:3000",
        "http://127.0.0.1:3000",
        "https://knowme.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(resume.router, prefix="/resume", tags=["resume"])
app.include_router(links.router, prefix="/links", tags=["links"])


@app.get("/health")
def health():
    return {"status": "ok"}
