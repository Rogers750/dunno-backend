-- ─── Resumes bucket policies ─────────────────────────────────────────────────
-- Files are stored at: resumes/{user_id}/resume.pdf
--
-- Design principle: INSERT uses a path-based check because owner_id is not yet
-- set when the object is being created (Supabase sets it after the upload
-- completes). For SELECT and UPDATE, owner_id IS available, so we use it.

-- Allows an authenticated user to upload a PDF only into their own folder.
-- (storage.foldername(name))[1] extracts the first path segment, which must
-- match the caller's user ID.
create policy "Users can upload their own resume file"
on storage.objects
for insert
to authenticated
with check (
  bucket_id = 'resumes'
  and (storage.foldername(name))[1] = (select auth.uid()::text)
);

-- Allows a user to read only their own resume files.
-- owner_id is set by Supabase automatically when the object is created.
create policy "Users can read their own resume file"
on storage.objects
for select
to authenticated
using (
  bucket_id = 'resumes'
  and owner_id = (select auth.uid()::text)
);

-- Allows a user to overwrite their own resume.
-- Dual check: must currently own the file (owner_id) AND the new path must
-- still map to their folder (prevents path-swapping tricks on upsert).
create policy "Users can update their own resume file"
on storage.objects
for update
to authenticated
using (
  bucket_id = 'resumes'
  and owner_id = (select auth.uid()::text)
)
with check (
  bucket_id = 'resumes'
  and (storage.foldername(name))[1] = (select auth.uid()::text)
);


-- ─── Avatars bucket policies ──────────────────────────────────────────────────
-- Files are stored at: avatars/{user_id}/avatar.{ext}
--
-- IMPORTANT: The 'avatars' bucket must be created as a PUBLIC bucket in the
-- Supabase dashboard (Storage → New bucket → toggle "Public bucket" ON).
-- Making the bucket public means get_public_url() returns a URL that any
-- browser can fetch without a signed token — required for portfolio pages
-- that load profile photos without any authentication.
--
-- Even though the bucket is public, these RLS policies are still needed to
-- control who can write, update, and delete objects inside it.

-- Allows anyone (including unauthenticated visitors) to read avatar files.
-- This is what powers the profile photo on public portfolio pages.
-- The bucket being marked Public in the dashboard handles CDN delivery;
-- this policy handles the Supabase API layer.
create policy "Public can read avatars"
on storage.objects
for select
using (bucket_id = 'avatars');

-- Allows an authenticated user to upload their avatar only into their own
-- folder (avatars/{user_id}/avatar.*). Path-based check is used here for
-- the same reason as resumes: owner_id is not set yet during INSERT.
create policy "Users can upload their own avatar"
on storage.objects
for insert
to authenticated
with check (
  bucket_id = 'avatars'
  and (storage.foldername(name))[1] = (select auth.uid()::text)
);

-- Allows a user to replace/update only their own avatar.
-- Dual check: must currently own the file (owner_id) AND the new path must
-- still sit inside their own folder (prevents cross-user file overwrites).
create policy "Users can update their own avatar"
on storage.objects
for update
to authenticated
using (
  bucket_id = 'avatars'
  and owner_id = (select auth.uid()::text)
)
with check (
  bucket_id = 'avatars'
  and (storage.foldername(name))[1] = (select auth.uid()::text)
);

-- Allows a user to delete only their own avatar.
-- Used by DELETE /portfolio/photo to clean up storage before clearing
-- the photo_url column in the profiles table.
create policy "Users can delete their own avatar"
on storage.objects
for delete
to authenticated
using (
  bucket_id = 'avatars'
  and owner_id = (select auth.uid()::text)
);
