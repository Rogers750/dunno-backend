alter table profiles enable row level security;

-- Anyone can read a profile (needed for public portfolio lookup by username)
create policy "profiles: public read"
  on profiles for select
  using (true);

-- Users can only insert their own profile
create policy "profiles: insert own"
  on profiles for insert
  with check (auth.uid() = id);

-- Users can only update their own profile
create policy "profiles: update own"
  on profiles for update
  using (auth.uid() = id);

-- Users can only delete their own profile
create policy "profiles: delete own"
  on profiles for delete
  using (auth.uid() = id);
