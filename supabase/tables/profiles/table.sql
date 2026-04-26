create table if not exists profiles (
  id          uuid references auth.users(id) on delete cascade primary key,
  username    text unique not null,
  email       text,
  created_at  timestamptz default now()
);
