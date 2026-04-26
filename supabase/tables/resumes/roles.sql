alter table resumes enable row level security;

-- Resumes are private — only the owner can access them
create policy "resumes: read own"
  on resumes for select
  using (auth.uid() = user_id);

create policy "resumes: insert own"
  on resumes for insert
  with check (auth.uid() = user_id);

create policy "resumes: update own"
  on resumes for update
  using (auth.uid() = user_id);

create policy "resumes: delete own"
  on resumes for delete
  using (auth.uid() = user_id);
