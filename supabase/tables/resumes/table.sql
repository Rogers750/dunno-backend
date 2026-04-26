create table if not exists resumes (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid references profiles(id) on delete cascade not null,
  file_url     text,
  raw_text     text,
  parsed       jsonb,
  uploaded_at  timestamptz default now()
);
