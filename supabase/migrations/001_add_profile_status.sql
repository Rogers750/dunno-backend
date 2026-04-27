-- Add status column to profiles
-- Values: 'onboarding' | 'processing' | 'ready'
alter table profiles
  add column if not exists status text not null default 'onboarding';
