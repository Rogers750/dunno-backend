create table if not exists links (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references profiles(id) on delete cascade not null,
  type        text not null,
  url         text not null,
  fetched     jsonb,
  included    boolean default true,
  created_at  timestamptz default now()
);
