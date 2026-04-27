create table if not exists profiles (
  id          uuid references auth.users(id) on delete cascade primary key,
  username    text unique not null,
  email       text,
  status      text not null default 'onboarding', -- onboarding | processing | ready
  created_at  timestamptz default now()
);
