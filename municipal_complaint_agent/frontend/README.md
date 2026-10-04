# ShehriLink frontend

React + Vite + TypeScript + Tailwind. Talks to the FastAPI backend in `../app`.

## Run

```bash
# terminal 1 - backend (http://localhost:8000)
cd ..
python run.py

# terminal 2 - frontend (http://localhost:5173)
cd frontend
npm install
npm run dev
```

Vite proxies `/api/*` to `localhost:8000` (see `vite.config.ts`), so no CORS or env setup is needed.

## Pages

| Route | What it does | Data |
|---|---|---|
| `/` | Landing page | static + sample stats |
| `/submit` | Report a problem, then watch the agent timeline | **real backend** (`POST /api/complaints/process`) |
| `/track/:id` | Progress bar + timeline | backend first, falls back to sample data (try `C-2001`) |
| `/admin` | Dashboard charts | **live** (`GET /api/complaints`) + sample data |
| `/admin/complaints`, `/admin/complaints/:id` | Filter / search / sort table, full detail | **live** + sample data (live ones tagged NEW) |
| `/admin/escalations` | Complaints that need a human | **live** + sample data |
| `/admin/teams` | Team availability and workload | **sample data** |

Sample data lives in `src/data/dummy.ts` (seeded, so it is identical on every load).

## Going from sample data to real data

The backend currently has no list/stats/teams endpoints and keeps results in memory. To make the admin side real, add
`GET /api/complaints`, `GET /api/stats`, `GET /api/teams` (backed by PostgreSQL), then replace the `DUMMY_*` imports
in `src/pages/admin/*` with calls in `src/lib/api.ts`. Types in `src/lib/types.ts` already mirror `ComplaintState`.

## Dark mode and Urdu

- **Dark mode:** toggle in the header (sun/moon). Follows the system setting on first visit, then remembers the choice.
  Colors are CSS variables in `src/index.css` (`:root` and `.dark`), mapped in `tailwind.config.js`.
- **Urdu (RTL):** toggle in the header (اردو / EN). The whole layout flips to right-to-left and the choice is remembered.
  English text is the translation key; add or fix Urdu in `src/lib/ur.ts`. Use `t('English text')` from `useI18n()` in any new UI.
  Team names, "retry 1 of 3" and "Area (Zone A)" are translated by pattern in `src/lib/i18n.tsx`.
- Complaint text typed by citizens and free-text reasons produced by the backend agents are shown as written (not translated).

## Theme

Colors are in `tailwind.config.js`: cream `#FBF5DD`, sand `#E7E1B1`, leaf `#306D29`, forest `#0D530E`.
Priority colors (crit / high / med) are separate so urgency stays readable.
