-- Add min_experience to job_listings for pre-filtering before LLM scoring.
-- Parsed from description text at upsert time using regex — no LLM needed.
-- NULL means we couldn't parse it — those jobs are always included in results.
alter table job_listings
  add column if not exists min_experience float;

-- Resize embedding vector from 1536 → 768 dims for Voyage AI.
-- Drop and recreate — safe since all values are currently NULL (Phase 1).
alter table job_listings
  drop column if exists embedding_vector;

alter table job_listings
  add column embedding_vector vector(768);

-- Index for fast cosine similarity search once embeddings are populated.
create index if not exists job_listings_embedding_idx
  on job_listings
  using ivfflat (embedding_vector vector_cosine_ops)
  with (lists = 100);
