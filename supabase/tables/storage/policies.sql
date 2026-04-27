-- Storage RLS policies for the "resumes" bucket
-- Files are stored at {user_id}/resume.pdf
-- owner_id is set by Supabase Storage automatically to the uploader's auth.uid()

create policy "Users can upload their own files"
on storage.objects
for insert
to authenticated
with check (
  (select auth.uid()) = owner_id::uuid
);

create policy "Users can read their own files"
on storage.objects
for select
to authenticated
using (
  (select auth.uid()) = owner_id::uuid
);
