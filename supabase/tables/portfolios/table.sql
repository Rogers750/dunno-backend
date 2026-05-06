create table if not exists portfolios (
  id                 uuid primary key default gen_random_uuid(),
  user_id            uuid references profiles(id) on delete cascade not null,
  theme_color        text default 'indigo',
  theme_category     text default 'software',
  selected_template  text default 'executive_minimal',  -- executive_minimal | modern_dark | creative_dev
  target_roles       text[],
  generated_content  jsonb,
  general_resume_json jsonb,
  general_cover_letter text,
  generated_at       timestamptz,
  published          boolean default false,
  created_at         timestamptz default now()
);
