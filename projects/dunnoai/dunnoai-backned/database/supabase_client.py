import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


def _create_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    return create_client(url, key)


supabase: Client = _create_client()
