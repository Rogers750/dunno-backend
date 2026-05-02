create extension if not exists vector;

create table if not exists job_listings (
  id                uuid primary key default gen_random_uuid(),
  job_hash          text unique not null,         -- md5(company.lower + title.lower + url)
  title             text not null,
  company           text not null,
  location          text,
  url               text not null,
  platform          text not null,               -- linkedin | naukri | wellfound | instahyre
  description       text,
  salary_range      text,                        -- nullable, e.g. "20-28 LPA"
  is_live           boolean default true,
  posted_at         timestamptz,
  expires_at        timestamptz,
  created_at        timestamptz default now(),
  embedding_vector  vector(1536)                 -- Phase 2 only. NULL in Phase 1.
);
