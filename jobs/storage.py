import logging

from database.supabase_client import supabase_admin

logger = logging.getLogger(__name__)

_BUCKET = "resumes"


def upload_resume_pdf(user_id: str, job_id: str, pdf_bytes: bytes) -> str:
    """Upload PDF to resumes/{user_id}/{job_id}.pdf. Returns storage path."""
    path = f"{user_id}/{job_id}.pdf"
    try:
        supabase_admin.storage.from_(_BUCKET).upload(
            path,
            pdf_bytes,
            {"content-type": "application/pdf", "upsert": "true"},
        )
        logger.info(f"[storage] uploaded resume pdf path={path}")
        return path
    except Exception as e:
        logger.error(f"[storage] upload failed path={path}: {e}")
        raise


def download_resume_pdf(path: str) -> bytes:
    """Download PDF bytes from Supabase Storage."""
    try:
        data = supabase_admin.storage.from_(_BUCKET).download(path)
        return data
    except Exception as e:
        logger.error(f"[storage] download failed path={path}: {e}")
        raise


def render_resume_pdf_sync(html: str) -> bytes:
    """Render HTML to PDF bytes using weasyprint."""
    from weasyprint import HTML
    return HTML(string=html).write_pdf()
