# Free deployment: Vercel + Neon (no credit card)

```
Browser -> Vercel project "shehrilink"        (React app)
              | /api/*  (rewrite)
              v
           Vercel project "shehrilink-agent"  (agent backend, serverless)
              | HTTPS
              v
           Vercel project "shehrilink-db"     (database backend, serverless)
              | SQL
              v
           Neon Postgres                       (free, data is persistent)
```

All three Vercel projects come from the SAME GitHub repo; each one uses a different **Root Directory**.

## 1. Neon (database)
1. Sign up at https://neon.com (GitHub/Google login, no card) and create a project.
2. Copy the **connection string** (`postgresql://user:password@ep-...neon.tech/neondb?sslmode=require`).
   Prefer the **pooled** one (host contains `-pooler`). Keep it secret.

## 2. Vercel project 1: database backend
Add New -> Project -> import the repo, then:

| Setting | Value |
|---|---|
| Project name | `shehri-link-db` |
| Root Directory | `backend` |
| Framework Preset | FastAPI |

Environment variables:

| Name | Value |
|---|---|
| `DATABASE_URL` | the Neon connection string |
| `AUTO_SEED` | `1` (loads the demo data the first time) |
| `ENABLE_DEMO_ROUTES` | `0` (otherwise anyone can call `POST /demo/reset` and wipe the data) |

Deploy, then open `https://shehri-link-db.vercel.app/health` -> `{"status":"ok"}`.

## 3. Vercel project 2: agent backend

| Setting | Value |
|---|---|
| Project name | `shehri-link` |
| Root Directory | `municipal_complaint_agent` |
| Framework Preset | FastAPI |

Environment variables:

| Name | Value |
|---|---|
| `DB_BACKEND_URL` | `https://shehri-link-db.vercel.app` |
| `LLM_PROVIDER` | `mock` |
| `VERIFICATION_SCENARIO` | `manual` |

Check `https://shehri-link.vercel.app/api/health`.

## 4. Vercel project 3: frontend

| Setting | Value |
|---|---|
| Project name | `shehrilink` |
| Root Directory | `municipal_complaint_agent/frontend` |
| Framework Preset | Vite |

No environment variables. `frontend/vercel.json` forwards `/api/*` to `https://shehri-link.vercel.app`.

## If a project name is already taken
Vercel then gives the project a different URL (e.g. `shehrilink-agent-xyz.vercel.app`). Fix the three places that
mention it: `DB_BACKEND_URL` (project 2) and the `destination` in `municipal_complaint_agent/frontend/vercel.json`.

## Notes and limits
* **401 / login page when opening a URL:** Project -> Settings -> Deployment Protection -> turn Vercel Authentication off
  for Production (it is meant for previews).
* **Cold starts:** the first request after a quiet period takes a few seconds (three functions wake up one after
  the other). Submitting a complaint makes ~20 calls to the database backend; Vercel's default function time limit is enough for that.
* **Free tiers** have monthly limits (Vercel Hobby, Neon free); a demo stays far below them.
* **No login:** the admin pages and the database API are open to anyone who knows the URL. Fine for a demo; add
  authentication before real use.
* **Real LLM:** set `LLM_PROVIDER`/`API_KEY` on project 2 and add `requirements-llm.txt` to `requirements.txt`
  (it is not installed by default to keep the serverless bundle small).
