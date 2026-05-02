create table if not exists user_matched_jobs (
  id                   uuid primary key default gen_random_uuid(),
  user_id              uuid not null references profiles(id) on delete cascade,
  job_id               uuid not null references job_listings(id) on delete cascade,
  match_score          float not null,
  score_breakdown      jsonb,
  -- { "role": 8.5, "skills": 9.0, "experience": 7.0,
  --   "education": 6.5, "company_type": 8.0, "compensation": 7.5 }
  -- compensation is null if no salary data available.
  resume_json          jsonb,
  cover_letter         text,
  project_suggestions  jsonb,
  -- { "suggestions": [{ "name", "description", "difficulty", "ai_build_time", "why_relevant" }] }
  company_info         jsonb,
  -- { "glassdoor_rating", "description", "culture_notes", "size", "founded" }
  pdf_path             text,                 -- resumes/{user_id}/{job_id}.pdf — null until PDF is generated
  status               text default 'new',  -- new | saved | applied
  created_at           timestamptz default now(),
  unique(user_id, job_id)
);
