create table if not exists job_runs (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references profiles(id),
  status        text default 'idle',     -- idle | running | done | failed
  progress      jsonb,
  -- {
  --   "current_step": 3,
  --   "total_steps": 7,
  --   "current_agent": "Agent 3 — Company Researcher",
  --   "completed_agents": ["Agent 1", "Agent 2"],
  --   "jobs_found": 10,
  --   "jobs_processed": 2
  -- }
  trigger       text,                    -- manual | cron
  started_at    timestamptz,
  finished_at   timestamptz,
  error_message text,                    -- populated only when status = failed
  created_at    timestamptz default now()
);

create index idx_job_runs_user_status on job_runs(user_id, status);

-- RLS: users can only read their own runs. Writes use supabase_admin (bypasses RLS).
alter table job_runs enable row level security;

create policy "Users can read own job runs"
on job_runs for select
to authenticated
using (user_id = (select auth.uid()::uuid));
