-- Migration 004: job run status tracking

CREATE TABLE job_runs (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid NOT NULL REFERENCES profiles(id),
  status        text DEFAULT 'idle',     -- idle | running | done | failed
  progress      jsonb,
  trigger       text,                    -- signup | cron | manual
  started_at    timestamptz,
  finished_at   timestamptz,
  error_message text,
  created_at    timestamptz DEFAULT now()
);

CREATE INDEX idx_job_runs_user_status ON job_runs(user_id, status);
