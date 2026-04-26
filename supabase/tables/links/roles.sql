alter table links enable row level security;

-- Links are private — only the owner can access them
create policy "links: read own"
  on links for select
  using (auth.uid() = user_id);

create policy "links: insert own"
  on links for insert
  with check (auth.uid() = user_id);

create policy "links: update own"
  on links for update
  using (auth.uid() = user_id);

create policy "links: delete own"
  on links for delete
  using (auth.uid() = user_id);
