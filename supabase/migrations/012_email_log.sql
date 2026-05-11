create table if not exists email_log (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references profiles(id) on delete cascade not null,
  type        text not null default 'jobs_digest',
  sent_at     timestamptz default now(),
  jobs_count  int,
  job_ids     uuid[]
);

create index if not exists email_log_user_id_idx on email_log(user_id);
create index if not exists email_log_sent_at_idx on email_log(sent_at desc);
