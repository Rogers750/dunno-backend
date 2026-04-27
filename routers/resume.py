import io
import logging
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pypdf import PdfReader
from supabase import Client

from database.supabase_client import create_user_client, supabase

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer(auto_error=False)


def _get_user(credentials: HTTPAuthorizationCredentials):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    try:
        result = supabase.auth.get_user(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if not result.user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return result.user


def _get_user_supabase(credentials: HTTPAuthorizationCredentials) -> Client:
    return create_user_client(credentials.credentials)


@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = _get_user(credentials)
    user_supabase = _get_user_supabase(credentials)
    logger.info(f"[resume/upload] user={user.id} file={file.filename}")

    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    contents = await file.read()

    # extract text from PDF
    try:
        reader = PdfReader(io.BytesIO(contents))
        raw_text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        logger.info(f"[resume/upload] extracted {len(raw_text)} chars from PDF")
    except Exception as e:
        logger.error(f"[resume/upload] PDF parsing failed: {e}")
        raise HTTPException(status_code=400, detail="Failed to parse PDF")

    # upload to supabase storage
    storage_path = f"{user.id}/resume.pdf"
    try:
        user_supabase.storage.from_("resumes").upload(
            storage_path, contents, {"content-type": "application/pdf", "upsert": "true"}
        )
        file_url = user_supabase.storage.from_("resumes").get_public_url(storage_path)
        logger.info(f"[resume/upload] uploaded to storage path={storage_path}")
    except Exception as e:
        logger.error(f"[resume/upload] storage upload failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload file")

    # upsert resume row
    existing = user_supabase.table("resumes").select("id").eq("user_id", user.id).execute()
    if existing.data:
        user_supabase.table("resumes").update({
            "file_url": file_url,
            "raw_text": raw_text,
            "parsed": None,
        }).eq("user_id", user.id).execute()
        resume_id = existing.data[0]["id"]
    else:
        result = user_supabase.table("resumes").insert({
            "user_id": user.id,
            "file_url": file_url,
            "raw_text": raw_text,
        }).execute()
        resume_id = result.data[0]["id"]

    logger.info(f"[resume/upload] saved resume id={resume_id}")
    return {"id": resume_id, "file_url": file_url, "chars_extracted": len(raw_text)}


@router.get("/me")
async def get_resume(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = _get_user(credentials)
    user_supabase = _get_user_supabase(credentials)
    result = user_supabase.table("resumes").select("id, file_url, uploaded_at").eq("user_id", user.id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="No resume found")
    return result.data[0]
