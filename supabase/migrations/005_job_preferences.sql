-- Add job_preferences jsonb column to profiles.
-- Stores location, company type, and experience range preferences used for
-- filtering and scoring job matches in the jobs crew pipeline.

alter table profiles
  add column if not exists job_preferences jsonb default '{}'::jsonb;
