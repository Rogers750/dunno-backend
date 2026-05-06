alter table portfolios
  add column if not exists general_resume_json jsonb;

alter table portfolios
  add column if not exists general_cover_letter text;
