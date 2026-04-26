# Project Context

## What exists right now

This repo (`Rogers750/knowme`) is **Sagar Singh Rawal's personal portfolio website** — the reference implementation and design benchmark for the platform we are building next.

### Live URLs
- **Primary**: https://sagar-rawal-de.vercel.app
- **Alias**: https://knowme-zeta.vercel.app
- **GitHub**: https://github.com/Rogers750/knowme

### Tech stack (existing portfolio)
- **Frontend**: React + Vite + TypeScript + Tailwind CSS
- **API**: Single Vercel serverless function (`api/chat.ts`) — proxies DeepSeek chat
- **Hosting**: Vercel (team: `blacksoundsgoods-projects`, project: `knowme-zt5x`)
- **Design**: Dark theme (`#07070f` bg, `#818cf8` indigo accent, Space Grotesk headings, Inter body)

### What the portfolio contains
- Hero section with name, title, impact stats ($300K+, 100M+ events/day, 3.5yr, 3 fintechs)
- Experience timeline: Dezerv → CoinDCX → Jumbotail → Alephs360
- Skills grouped by category (Languages, Data Engineering, ML/AI, AWS, Tools)
- Personal Projects: Meshtheorem (VITON fashion app), PDF Cutter, Path18 (medical AI)
- About: education (NIT Kurukshetra, GPA 8.0), sports (U-14 Bengal, U-16 UP cricket), writing (Medium/CoinDCX)
- Contact section
- Floating AI chat widget — powered by DeepSeek via `/api/chat`, system prompt contains Sagar's full profile

### Vercel env vars set
- `DEEPSEEK_API_KEY` — set on both `knowme` and `knowme-zt5x` Vercel projects

### Key files
- `frontend/src/App.tsx` — full portfolio UI, all data inlined as constants
- `frontend/src/components/Chat.tsx` — chat widget + full system prompt with Sagar's profile
- `api/chat.ts` — Node.js serverless function proxying DeepSeek
- `vercel.json` — build config (`cd frontend && npm install && npm run build`, output: `frontend/dist`)

---

## What we are building next: Dunno

**Dunno** is a SaaS platform where anyone can sign up and get a beautiful, AI-generated portfolio page at `dunno.app/username` — personalised from their resume, GitHub, Behance, and Dribbble.

Sagar's portfolio above is the design reference and the first working example of what Dunno generates.

### The product in one line
> Sign up → upload resume + links → AI builds your portfolio → share `dunno.app/yourname`

---

## Onboarding flow

```
1. Sign up  →  email + password  OR  email + OTP (magic link)
2. Theme    →  pick color theme + category template
               (Software Engineer / Designer / Product Manager)
               OR "choose for me" — AI picks from resume tone + job category
3. Resume   →  upload PDF resume + type target roles (e.g. "Senior Data Engineer, MLOps")
4. Links    →  paste GitHub profile URL, individual repo URLs, Behance, Dribbble
               → platform auto-fetches all data
               → user sees a checklist, can uncheck/search to exclude items
5. Generate →  AI analyses resume + links + theme → builds portfolio content
6. Live     →  portfolio published at dunno.app/username
```

---

## Tech stack (Dunno platform)

| Layer | Choice | Notes |
|---|---|---|
| Framework | **Next.js 15 (App Router)** | Dynamic `/[username]` routes, SSR for SEO, API routes, Vercel native |
| Auth | **Supabase Auth** | Email+password + magic link OTP built-in |
| Database | **Supabase Postgres** | User profiles, portfolio configs, projects, links |
| File storage | **Supabase Storage** | Resume PDF uploads |
| Resume parsing | **PDF parsing + Claude API** | Extract text from PDF, Claude structures it |
| AI generation | **Claude API (claude-sonnet-4-6)** | Resume + GitHub data + tone → portfolio content |
| GitHub scraping | **GitHub public REST API** | Fetch repos, stars, languages, descriptions — no auth needed for public data |
| Styling | **Tailwind CSS** | Same as existing portfolio |
| Hosting | **Vercel** | Already set up, path routing works perfectly |

---

## Database schema

```sql
-- Users (managed by Supabase Auth, extended here)
profiles
  id          uuid references auth.users primary key
  username    text unique not null
  email       text
  created_at  timestamptz default now()

-- Portfolio configuration per user
portfolios
  id              uuid primary key default gen_random_uuid()
  user_id         uuid references profiles(id)
  theme_color     text        -- e.g. "indigo", "emerald", "amber"
  theme_category  text        -- "software" | "design" | "product" | "ai_chosen"
  target_roles    text[]      -- e.g. ["Senior Data Engineer", "MLOps Engineer"]
  generated_at    timestamptz
  published       boolean default false

-- Raw + structured resume data
resumes
  id          uuid primary key default gen_random_uuid()
  user_id     uuid references profiles(id)
  file_url    text        -- Supabase Storage URL
  raw_text    text        -- extracted PDF text
  parsed      jsonb       -- structured: { summary, experience[], skills[], education[] }
  uploaded_at timestamptz default now()

-- External links provided by user
links
  id        uuid primary key default gen_random_uuid()
  user_id   uuid references profiles(id)
  type      text    -- "github_profile" | "github_repo" | "behance" | "dribbble"
  url       text
  fetched   jsonb   -- raw API response / scraped data
  included  boolean default true  -- user can uncheck to exclude

-- Individual projects/repos shown on portfolio
projects
  id          uuid primary key default gen_random_uuid()
  user_id     uuid references profiles(id)
  source      text    -- "github" | "behance" | "manual"
  title       text
  description text
  url         text
  tags        text[]
  included    boolean default true
  display_order int
```

---

## URL structure

```
dunno.app/                    → marketing / landing page
dunno.app/login               → auth
dunno.app/onboarding          → multi-step onboarding wizard
dunno.app/dashboard           → user's portfolio management
dunno.app/[username]          → public portfolio page (the generated portfolio)
dunno.app/api/...             → Next.js API routes
```

---

## AI generation logic

When the user completes onboarding, the platform:

1. Takes `resumes.parsed` (structured resume JSON)
2. Takes all `links` where `included = true` + their `fetched` data
3. Takes `portfolios.theme_category` + `portfolios.target_roles`
4. Sends to Claude with a prompt that:
   - Extracts key impact metrics (numbers, cost savings, % improvements)
   - Identifies strongest technical skills by evidence, not just listed skills
   - Picks tone from resume writing style (formal vs casual, concise vs detailed)
   - Selects which projects/repos to feature based on relevance to target roles
   - Generates: summary, experience highlights, skill groupings, project descriptions
5. Saves output to `portfolios.generated_content` (jsonb)
6. The `/[username]` page renders this content using the chosen theme template

---

## Theme system

Each theme = color palette + layout variant

**Color themes**: indigo (default, like Sagar's), emerald, amber, rose, sky, slate
**Category templates**:
- `software` — timeline-heavy, metrics-forward, skill tags (like Sagar's)
- `design` — project-grid-first, visual, Behance/Dribbble prominent
- `product` — story-first, impact metrics, roadmap-style experience
- `ai_chosen` — Claude picks based on job category + resume tone

---

## Decisions already made

- Platform name: **Dunno**
- Route pattern: `dunno.app/username` (paths, not subdomains)
- Username: user picks it during signup
- GitHub scraping: auto-fetch everything, user unchecks what to exclude
- Theme AI: picks based on job category + personality/tone from resume
- Editing: users can change narrative after generation (build later)
- Monetisation: free for all (for now)
- Existing Sagar portfolio stays live separately as the design reference

---

## What to build first (suggested order)

1. Next.js project setup + Supabase connection
2. Auth (sign up / login / OTP)
3. Onboarding wizard (theme → resume → links)
4. Resume upload + PDF parsing
5. GitHub API fetching + project checklist
6. Claude AI generation pipeline
7. `/[username]` portfolio renderer with theme system
8. Dashboard (published status, regenerate)

---

## Reference implementation

The existing portfolio at `sagar-rawal-de.vercel.app` is the gold standard for what a `software` category + indigo theme portfolio should look like. When building the `/[username]` renderer, use `frontend/src/App.tsx` in this repo as the template baseline.

Owner: Sagar Singh Rawal (sagarsinghraw77@gmail.com)
