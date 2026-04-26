alter table projects enable row level security;

-- Public can read projects for any published portfolio
create policy "projects: public read for published portfolios"
  on projects for select
  using (
    auth.uid() = user_id
    or exists (
      select 1 from portfolios p
      where p.user_id = projects.user_id
      and p.published = true
    )
  );

create policy "projects: insert own"
  on projects for insert
  with check (auth.uid() = user_id);

create policy "projects: update own"
  on projects for update
  using (auth.uid() = user_id);

create policy "projects: delete own"
  on projects for delete
  using (auth.uid() = user_id);
