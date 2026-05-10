create table if not exists feedback (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references profiles(id) on delete set null,
  name        text,
  email       text,
  type        text not null default 'feedback',  -- 'feedback' | 'feature_request' | 'bug'
  message     text not null,
  created_at  timestamptz default now()
);

create index if not exists feedback_user_id_idx on feedback(user_id);
create index if not exists feedback_created_at_idx on feedback(created_at desc);
