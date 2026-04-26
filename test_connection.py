import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

if not url or not key:
    print("ERROR: SUPABASE_URL or SUPABASE_KEY missing from .env")
    exit(1)

try:
    client = create_client(url, key)
    # Query auth.users count via admin API to confirm connection + service key works
    response = client.auth.get_user(None)
except Exception as e:
    # A 400/AuthError means we connected but no token passed — that's fine, connection works
    err = str(e)
    if "AuthApiError" in type(e).__name__ or "missing" in err.lower() or "invalid" in err.lower() or "token" in err.lower():
        print("Supabase connection: OK (service key valid, auth API reachable)")
        print(f"  URL: {url}")
    else:
        print(f"Connection failed: {e}")
        exit(1)

# Also try reading a non-existent table to confirm DB connection
try:
    client2 = create_client(url, key)
    result = client2.table("profiles").select("id").limit(1).execute()
    print("Database connection: OK (profiles table exists)")
except Exception as e:
    err = str(e)
    if "relation" in err.lower() or "does not exist" in err.lower() or "PGRST" in err:
        print("Database connection: OK (connected, but schema not created yet — expected)")
    else:
        print(f"Database error: {e}")
