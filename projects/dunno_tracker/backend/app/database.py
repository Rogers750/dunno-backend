# Kept for backwards compatibility — new code should import get_repo() directly.
from app.repositories import get_repo

__all__ = ["get_repo"]
