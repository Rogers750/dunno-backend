# dunno-backend

FastAPI backend for Dunno, an AI portfolio generator that turns a user's resume and GitHub data into a publishable portfolio profile.

## Goal

The product flow is:

1. User signs in with email OTP or Google via Supabase Auth.
2. User uploads a PDF resume.
3. User connects a GitHub profile or repos.
4. Backend stores resume and repo data in Supabase.
5. DeepSeek generates structured portfolio content.
6. User edits, selects a template, uploads a profile photo, and publishes.

This repo is the backend that powers that flow.

## Stack

- FastAPI
- Supabase Auth, Postgres, and Storage
- DeepSeek API for portfolio generation
- GitHub public API for repo ingestion
- Railway deployment target

## Current Features

- Auth
  - `POST /auth/verification/send`
  - `POST /auth/verification/verify`
  - `POST /auth/google`
  - `POST /auth/dev-login`
  - `GET /auth/me`
- Resume
  - `POST /resume/upload`
  - `GET /resume/me`
- Links and repos
  - `POST /links/github`
  - `GET /links/me`
  - `GET /links/repos`
  - `PATCH /links/{link_id}/toggle`
- Portfolio
  - `POST /portfolio/generate`
  - `GET /portfolio/me`
  - `PATCH /portfolio/me/section`
  - `PATCH /portfolio/template`
  - `POST /portfolio/publish`
  - `POST /portfolio/photo`
  - `DELETE /portfolio/photo`
  - `POST /portfolio/repos/refresh`
  - `PATCH /portfolio/repos/{link_id}`
  - `GET /portfolio/{username}`
- Infra
  - `GET /health`

## Project Structure

```text
database/
  supabase_client.py      # base clients + per-request user-scoped client
models/
  auth.py                 # request/response models
routers/
  auth.py                 # auth endpoints
  resume.py               # resume upload + retrieval
  links.py                # GitHub ingestion + inclusion toggles
  portfolio.py            # AI generation, editing, publishing, photo upload
supabase/
  tables/                 # table schema and RLS SQL
main.py                   # FastAPI app, CORS, router registration
```

## Environment Variables

Required in `.env`:

```env
SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_SERVICE_KEY=
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

Notes:

- `SUPABASE_KEY` is the normal anon/public key used with a per-request bearer token.
- `SUPABASE_SERVICE_KEY` is still used for admin-only backend operations such as dev login and any explicit admin flows.
- Resume upload uses a user-scoped Supabase client so Storage RLS is enforced with the caller's token.

## Local Development

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the API:

```bash
uvicorn main:app --reload
```

Open docs:

```text
http://127.0.0.1:8000/docs
```

## CORS

The backend currently allows:

- `http://localhost:3000`
- `http://0.0.0.0:3000`
- `http://127.0.0.1:3000`
- `https://knowme.vercel.app`
- `https://dunnoai.vercel.app`
- `https://dunno.app`
- `https://www.dunno.app`

Update `main.py` if frontend origins change.

## Resume Upload Contract

Endpoint:

```text
POST /resume/upload
```

Requirements:

- `Authorization: Bearer <supabase_access_token>`
- `multipart/form-data`
- file field name must be `file`
- only PDF files are accepted

Behavior:

- extracts text from the PDF
- stores the PDF in Supabase Storage under `{user_id}/resume.pdf`
- upserts a single logical resume record for the user in the `resumes` table

## Supabase Notes

This backend depends on:

- auth users in Supabase Auth
- `profiles`, `resumes`, `links`, `projects`, and `portfolios` tables
- RLS policies under `supabase/tables/**/roles.sql`
- Storage policies for resume and avatar buckets

Important:

- Storage upload authorization should be based on `bucket_id` and folder path, not only `owner_id`.
- For `upsert: true` uploads, Storage also needs `update` permission.

## AI Generation

`POST /portfolio/generate` combines:

- resume raw text
- included GitHub repo metadata
- target roles
- extra context from the user

It sends that payload to DeepSeek and expects strict JSON portfolio output, which is then stored in the portfolio record for later editing and publishing.

## Deployment

Primary deployment target is Railway.

Recommended checks for Railway:

- repo connected to `Rogers750/dunno-backend`
- branch set to `main`
- required environment variables present
- correct start command configured for FastAPI

If Railway misses a push, verify the service source settings before debugging Git locally.

## Status

This backend already supports:

- auth
- resume ingestion
- GitHub repo ingestion
- AI portfolio generation
- portfolio retrieval/editing/publishing
- profile photo upload

Remaining quality work is mostly around:

- schema hardening
- deployment polish
- richer validation and error handling
- broader automated testing
