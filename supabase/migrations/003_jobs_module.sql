-- Migration 003: jobs module
-- Run in Supabase SQL Editor in this order.

-- Step 1 — Enable pgvector (needed for embedding_vector column)
create extension if not exists vector;

-- Step 2 — Add ctc column to profiles
alter table profiles
  add column if not exists ctc jsonb;
-- Shape: { "current_base_in_lakhs": 18, "expected_base_in_lakhs": 25 }
-- Single source of truth for compensation. Do not store CTC elsewhere.

-- Step 3 — job_listings: deduplicated live job postings across all platforms
create table if not exists job_listings (
  id                uuid primary key default gen_random_uuid(),
  job_hash          text unique not null,
  title             text not null,
  company           text not null,
  location          text,
  url               text not null,
  platform          text not null,           -- linkedin | naukri | wellfound | instahyre
  description       text,
  salary_range      text,                    -- nullable, e.g. "20-28 LPA"
  is_live           boolean default true,
  posted_at         timestamptz,
  expires_at        timestamptz,
  created_at        timestamptz default now(),
  embedding_vector  vector(1536)             -- NULL in Phase 1. Reserved for Phase 2 pgvector matching.
);

-- Step 4 — user_matched_jobs: per-user AI-generated job match data
create table if not exists user_matched_jobs (
  id                   uuid primary key default gen_random_uuid(),
  user_id              uuid not null references profiles(id) on delete cascade,
  job_id               uuid not null references job_listings(id) on delete cascade,
  match_score          float not null,
  score_breakdown      jsonb,
  resume_json          jsonb,
  cover_letter         text,
  project_suggestions  jsonb,
  company_info         jsonb,
  pdf_path             text,                 -- Supabase Storage path: resumes/{user_id}/{job_id}.pdf
  status               text default 'new',  -- new | saved | applied
  created_at           timestamptz default now(),
  unique(user_id, job_id)
);

-- Step 5 — RLS: users can only read their own matched jobs
alter table user_matched_jobs enable row level security;

create policy "Users can read own matched jobs"
on user_matched_jobs for select
to authenticated
using (user_id = (select auth.uid()::uuid));

-- job_listings is publicly readable (no user-specific data)
alter table job_listings enable row level security;

create policy "Anyone can read job listings"
on job_listings for select
using (true);
