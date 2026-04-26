create table if not exists projects (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid references profiles(id) on delete cascade not null,
  source         text not null,
  title          text,
  description    text,
  url            text,
  tags           text[],
  included       boolean default true,
  display_order  int default 0,
  created_at     timestamptz default now()
);
