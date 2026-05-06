"""
One-time script to backfill embedding_vector for all job_listings where it's NULL.
Run from project root: python scripts/backfill_embeddings.py
"""
import os
import time
import logging
from dotenv import load_dotenv

load_dotenv()

import voyageai
from database.supabase_client import supabase_admin

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 50  # Voyage AI allows up to 128 texts per request
MODEL = "voyage-3"
DIMS = 1024


def backfill():
    client = voyageai.Client(api_key=os.getenv("VOYAGE_JOB_SEARCH_VECTOR_SECRET"))

    # Fetch all jobs with no embedding
    logger.info("Fetching jobs with no embedding...")
    rows = (
        supabase_admin.table("job_listings")
        .select("id, title, company, description")
        .is_("embedding_vector", "null")
        .execute()
    )

    jobs = rows.data or []
    logger.info(f"Found {len(jobs)} jobs to embed")

    total = 0
    for i in range(0, len(jobs), BATCH_SIZE):
        batch = jobs[i: i + BATCH_SIZE]

        texts = [
            f"{j['title']} at {j['company']}\n{(j.get('description') or '')[:3000]}"
            for j in batch
        ]

        try:
            result = client.embed(texts, model=MODEL)
            embeddings = result.embeddings
        except Exception as e:
            logger.error(f"Embedding failed for batch {i}-{i+len(batch)}: {e}")
            time.sleep(2)
            continue

        for job, embedding in zip(batch, embeddings):
            try:
                supabase_admin.table("job_listings") \
                    .update({"embedding_vector": embedding}) \
                    .eq("id", job["id"]) \
                    .execute()
            except Exception as e:
                logger.error(f"DB update failed for job {job['id']}: {e}")

        total += len(batch)
        logger.info(f"Progress: {total}/{len(jobs)} embedded")
        time.sleep(0.5)  # stay within rate limits

    logger.info(f"Done. {total} jobs embedded.")


if __name__ == "__main__":
    backfill()
