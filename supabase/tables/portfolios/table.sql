create table if not exists portfolios (
  id                 uuid primary key default gen_random_uuid(),
  user_id            uuid references profiles(id) on delete cascade not null,
  theme_color        text default 'indigo',
  theme_category     text default 'software',
  target_roles       text[],
  generated_content  jsonb,
  generated_at       timestamptz,
  published          boolean default false,
  created_at         timestamptz default now()
);
