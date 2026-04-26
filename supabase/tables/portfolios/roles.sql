alter table portfolios enable row level security;

-- Anyone can read a published portfolio (powers the public /username page)
create policy "portfolios: public read published"
  on portfolios for select
  using (published = true or auth.uid() = user_id);

-- Users can only insert their own portfolio
create policy "portfolios: insert own"
  on portfolios for insert
  with check (auth.uid() = user_id);

-- Users can only update their own portfolio
create policy "portfolios: update own"
  on portfolios for update
  using (auth.uid() = user_id);

-- Users can only delete their own portfolio
create policy "portfolios: delete own"
  on portfolios for delete
  using (auth.uid() = user_id);
