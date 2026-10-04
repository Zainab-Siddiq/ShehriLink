# ShehriLink Frontend - Guide for the Integration Person

This document explains what the frontend does, which API calls it makes, which data shape it expects, and exactly
what to change to connect it to the final backend. Read sections 1-5 for the picture, section 6 for the work list.

---

## 1. What it is

A web app for the Municipal Complaint Resolution system, with two sides:

- **Citizen side:** report a problem, watch the AI agents handle it live, track a complaint by ID.
- **Officer side (`/admin`):** dashboard, complaints table, complaint detail, escalation queue, field teams.

Extras: dark mode toggle, English/Urdu toggle (Urdu switches the whole layout to right-to-left), mobile-friendly.

**Stack:** React 19, TypeScript, Vite, Tailwind CSS 3, React Router 7, Recharts (charts), lucide-react (icons).
No UI framework, no global state library. Language and theme are small React contexts.

## 2. Run it

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
npm run build        # type-checks (tsc -b) then builds to dist/
```

The dev server **proxies `/api/*` to the backend** (`vite.config.ts`). Default target is `http://localhost:8000`.
To point at another backend without editing code:

```bash
API_TARGET=http://localhost:9000 npm run dev      # PowerShell: $env:API_TARGET="http://localhost:9000"; npm run dev
```

All frontend calls use relative URLs (`/api/...`), so there is no CORS setup and no base-URL variable in the code.
For production, serve `dist/` behind a server that forwards `/api` to the backend (or change the URLs in `src/lib/api.ts`).

## 3. Pages and routes

| Route | File | What it does | Data source today |
|---|---|---|---|
| `/` | `pages/Landing.tsx` | Marketing page, 6 agent steps, stats strip | Stats strip uses **sample data** |
| `/submit` | `pages/Submit.tsx` | Complaint form, then animated result | **Backend:** `POST /api/complaints/process` |
| `/track`, `/track/:id` | `pages/Track.tsx` | Look up a complaint, progress bar, timeline | **Backend:** `GET /api/complaints/{id}`, falls back to sample data |
| `/admin` | `pages/admin/Dashboard.tsx` | 4 stat cards, 4 charts, "needs attention" list | Backend list + sample data |
| `/admin/complaints` | `pages/admin/Complaints.tsx` | Table: search, 4 filters, sort, pagination (12/page) | Backend list + sample data |
| `/admin/complaints/:id` | `pages/admin/ComplaintDetail.tsx` | All fields + full timeline | Backend list + sample data |
| `/admin/escalations` | `pages/admin/Escalations.tsx` | Escalated complaints only | Backend list + sample data |
| `/admin/teams` | `pages/admin/Teams.tsx` | Team cards with availability and workload | **Sample data only** |
| `*` | `pages/NotFound.tsx` | 404 | - |

There is **no login**. "Officer login" is a plain link to `/admin`.

## 4. Source layout

```
src/
  main.tsx, App.tsx            providers + routes
  index.css                    theme variables (light + .dark), shared classes (.card, .btn, .input)
  lib/
    api.ts                     ALL network calls (4 functions)         <-- main integration file
    types.ts                   Complaint, HistoryEntry, Team types      <-- the shape the UI expects
    useComplaints.ts           admin data hook: live list + sample data <-- integration file
    constants.ts               areas, zones, categories, status labels, simulation options
    i18n.tsx, ur.ts            English->Urdu translation (see section 8)
    theme.tsx                  dark mode + chart colors
  data/dummy.ts                sample data (40 complaints, teams) - delete once real data is wired
  components/                  Layouts, Timeline, ProgressSteps, ComplaintView, ui (badges, cards), Toggles
  pages/                       one file per route (table above)
```

## 5. What the frontend expects from the backend

### 5.1 API calls it makes today (all in `src/lib/api.ts`)

| Function | Request | Used by |
|---|---|---|
| `submitComplaint(payload)` | `POST /api/complaints/process` body `{complaint_id, description, location?, verification_scenario?}` | `/submit` |
| `getComplaint(id)` | `GET /api/complaints/{id}` (404 or network error -> falls back to sample data) | `/track/:id` |
| `listComplaints()` | `GET /api/complaints` (returns `[]` on any error) | `useComplaints` -> all admin pages |
| `getHealth()` | `GET /api/health` | not used by any page yet |

Important behaviours:

1. **Submit is one synchronous call that returns the finished complaint, including the full `history` array.**
   The UI then *replays* the history as an animation (one step every 650 ms). It does not poll.
2. **The browser generates the complaint ID** (`newComplaintId()` -> `C-1234`) and sends it. If the real backend
   creates the ID itself (e.g. `MC-0011`), delete this and use the ID from the response.
3. A response of **502/503/504** is shown to the user as "Cannot reach the server. Start the backend...".
   Other errors show `body.detail` (FastAPI style) as text.
4. `verification_scenario` (`success | fail_once | fail_twice | always_fail`) is a **mock-only** control behind the
   "Simulation options" link on `/submit`. Remove that block when real citizen verification exists.

### 5.2 The data shape the UI renders (`src/lib/types.ts`)

The UI works on one `Complaint` object. These are the fields it actually displays:

| Field | Type | Where it shows |
|---|---|---|
| `complaint_id` | string | everywhere (title, table, links, track lookup) |
| `description` | string | cards, table |
| `category`, `subcategory` | string, e.g. `streetlight`, `streetlight_not_working` | detail page, table, pie chart, filters |
| `area`, `zone` | string, e.g. `Canal Town`, `Zone A` | location block, table, zone chart, zone filter |
| `priority` | `LOW \| MEDIUM \| HIGH \| CRITICAL` (uppercase) | badges, priority chart/filter/sort |
| `department` | string, e.g. `Electrical Department` | cards, detail |
| `assigned_team`, `assigned_team_name` | string or null | cards, table |
| `failed_teams` | string[] | detail, escalations |
| `retry_count`, `max_retries` | number | "N failed attempts", detail, escalations |
| `status` | `RECEIVED \| ASSIGNED \| VERIFIED \| VERIFICATION_FAILED \| REPLANNING \| CLOSED \| ESCALATED` | badges, progress bar, stat cards, filters |
| `escalation_reason`, `citizen_feedback`, `team_report`, `verification_reason`, `priority_reason` | string or null | detail, escalations |
| `classification_confidence`, `location_confidence` | 0-1 number or null | detail page |
| `duplicate`, `related_complaint_id`, `duplicate_reason` | bool / string | "Possible duplicate" banner |
| `history` | `HistoryEntry[]` (below) | the timeline |
| `submitted_at` | ISO string (UI-only, optional) | table date, daily chart. If missing, `useComplaints` uses `history[0].timestamp` |

`HistoryEntry` (one timeline row):

```ts
{ agent: string,          // "Classification Agent"
  message: string,        // short title: "Classification completed" (falls back to `action`)
  action: string,
  result: string,         // shown after the agent name: "streetlight", "Canal Town (Zone A)", "retry 1 of 3"
  status: 'success' | 'failed' | 'replanning' | 'escalated' | 'info',   // picks icon + color
  timestamp: string,      // ISO
  details: Record<string, unknown> }   // up to 4 primitive entries shown as small key: value lines
```

`Team` (Teams page): `{ team_id, name, department, zone, available, active_tasks, capacity }`.

### 5.3 How the admin pages get their numbers

There is **no stats endpoint call**. `Dashboard.tsx` computes everything in the browser from the full complaint list:
totals, in-progress / closed / escalated counts, per-category, per-priority, per-zone, per-day (last 14 days).
So the list endpoint must return **all** complaints (or enough of them). With a paginated API (e.g. 50 per page),
either fetch all pages, or replace those computations with a stats endpoint (see 6.4).

## 6. How to connect the real backend (the work list)

### 6.1 Do the mapping in ONE place

Put an adapter in `src/lib/api.ts` that converts whatever the backend returns into the `Complaint` shape above.
After that no page needs to change. Pages never call `fetch` themselves.

### 6.2 If the backend is the SQLite/SQLAlchemy "database backend" (`/complaints`, `/dashboard/stats`, ...)

This is a suggested mapping based on reading that code. It has **not been run against this frontend**.

| UI field | Database backend | Notes |
|---|---|---|
| `complaint_id` | `reference_no` (`MC-0011`) | lookup also accepts the numeric id |
| `description` | `raw_text` | |
| `status` | `status` (lowercase, 12 values) | must be mapped to the 7 UI statuses, see below |
| `priority` | `priority` (lowercase) | `.toUpperCase()` |
| `zone` | `zone_id` -> `GET /zones` name | **no "area" exists** in the DB; use `address_text` for `area`, or hide the area line |
| `department` | `department_id` -> `GET /departments` name | |
| `assigned_team_name` | latest `assignments[].team_name` (from `GET /complaints/{id}/context`) | |
| `failed_teams` | assignments with `status = failed` | |
| `retry_count` | `reopen_count` | `max_retries` = backend `MAX_REOPENS` (3) |
| `history` | `GET /complaints/{id}/agent-activity` | see event mapping below |
| `escalation_reason` | latest `status_history` row with `to_status = escalated` -> `reason` | |
| `citizen_feedback` | latest `verifications[].evidence` | |

Status mapping (suggestion):

| Database status | UI status |
|---|---|
| `submitted`, `processing`, `duplicate` | `RECEIVED` |
| `assigned`, `in_progress`, `resolved`, `verification_pending` | `ASSIGNED` |
| `verified` | `VERIFIED` |
| `verification_failed` | `VERIFICATION_FAILED` |
| `reopened` | `REPLANNING` |
| `closed` | `CLOSED` |
| `escalated` | `ESCALATED` |

Timeline mapping: `agent_name` -> `agent`, `message` -> `message`, `created_at` -> `timestamp`, `data` -> `details`.
`event_type` -> UI `status`: `error`/`warning` -> `failed`, `decision`/`action`/`status_change`/`info` -> `success` or `info`.
Use `replanning` for a reopen event and `escalated` for the escalate event. The DB timeline is **per status change and
per agent log line**, so it will be much longer than the 8-13 rows the UI was designed around; consider filtering to
`event_type in (decision, action)`.

Teams page: `GET /teams` returns `{id, name, department_name, zone_name, is_active, technician_count,
available_technicians, active_assignments}`. Map `is_active` -> `available`, `active_assignments` -> `active_tasks`,
`technician_count` -> `capacity` (a reasonable proxy).

### 6.3 Submit flow (the biggest decision)

The UI expects *one call in, finished complaint out*. If the real system runs the agents as several separate calls or
in the background, there are two options:

- **A (no UI change):** add one backend endpoint that creates the complaint, runs the whole agent pipeline, and
  returns the finished complaint with its timeline. Point `submitComplaint()` at it.
- **B (small UI change):** create the complaint, then poll `GET /complaints/{id}/agent-activity?since_id=N` every
  1-2 s and append rows to the timeline as they arrive. `Timeline.tsx` currently replays a fixed array
  (`animate` prop), so it would need to accept a growing array instead.

### 6.4 Remove the sample data

When real data is wired, delete the sample-data fallbacks:

| File | What to remove |
|---|---|
| `lib/useComplaints.ts` | the `DUMMY_COMPLAINTS` merge (keep only the live list) |
| `lib/api.ts` | `findDummy` fallback in `getComplaint` |
| `pages/Landing.tsx` | stats strip reads `DUMMY_COMPLAINTS`; use a stats call or hard-code |
| `pages/admin/Teams.tsx` | `DUMMY_TEAMS` -> call the teams endpoint |
| `pages/admin/Dashboard.tsx` | subtitle says "sample data for presentation"; remove, and optionally use `GET /dashboard/stats` instead of client-side counts |
| `data/dummy.ts` | delete the file (`dailyCounts` is used by the dashboard: move it into the dashboard file first) |

### 6.5 Other things the backend side must provide

- Category names must match the UI list (`streetlight, road, water, drainage, garbage, sanitation, parks, sewerage,
  electricity, other`) or the filter dropdown and Urdu names will not match (`lib/constants.ts`).
- Zone names `Zone A-D` and the 12 area names are hard-coded in `lib/constants.ts` (used by the submit form's Area
  dropdown). Replace with `GET /zones` (and areas, if they exist) when available.
- The submit form sends `location` as free text `"<street>, <area>"`.
- No authentication exists on either side. If login is added, `/admin/*` routes need a guard in `App.tsx` and the
  fetch calls need an auth header in `api.ts`.

## 7. Known gaps (not built)

- Login / roles for officers.
- Citizen feedback screen ("was the problem solved? yes/no") - verification is simulated.
- Photo upload, map view.
- Admin actions (reassign, close, comment) - the admin side is read-only.
- Automated tests for the frontend. Checked so far: `tsc` type-check, production build, and manual browser testing
  of submit, track, admin pages, dark mode, Urdu, mobile width. `npm run lint` (oxlint) exits 0 with warnings only
  (React style hints such as "components created during render" in the sortable table header and
  "only export components" in the context files); none affect behaviour today.

## 8. Theme, dark mode, and Urdu (for anyone adding UI)

- **Colors** come from CSS variables in `src/index.css` (`:root` and `.dark`), mapped to Tailwind names in
  `tailwind.config.js` (`cream, sand, leaf, forest, ink, surface, deep, paper, sandc, crit, high, med`). Use those names
  (`bg-surface`, `text-forest`), not raw hex, and dark mode works automatically. Charts take literal colors from
  `useChartTheme()` in `lib/theme.tsx`.
- **Brand palette:** cream `#FBF5DD`, sand `#E7E1B1`, leaf `#306D29`, forest `#0D530E`.
- **Translation:** the English text *is* the key. Write `t('Report a problem')` using `const { t } = useI18n()`, and add
  `'Report a problem': '...Urdu...'` to `src/lib/ur.ts`. Missing keys simply show the English text.
  Team names ("Electrical Team A"), "retry 1 of 3" and "Canal Town (Zone A)" are translated by pattern in
  `lib/i18n.tsx`. Free text from citizens and the agents' reasons are shown as written.
- **RTL:** Urdu sets `<html dir="rtl" lang="ur">`. Use logical Tailwind classes (`ms-2`, `ps-9`, `start-3`,
  `text-start`), not `ml-2`, `pl-9`, `left-3`, `text-left`, so the layout flips correctly. Charts are kept left-to-right.
- Language and theme are remembered in `localStorage` (`sl-lang`, `sl-theme`).

## 9. Quick test checklist after integration

1. Submit a complaint on `/submit`: result card appears, timeline animates, outcome banner shows at the end.
2. Open `/track/<that id>`: same data, no animation.
3. `/admin/complaints`: the new complaint is in the table, filters and search work, detail page opens.
4. Force a failure path (replan, then escalation) and check `/admin/escalations` and the progress bar ("Escalated").
5. Stop the backend and submit: the page should show the "Cannot reach the server" message, not a blank screen.
6. Switch to Urdu and dark mode on each page; look for English leftovers and broken alignment.
7. Resize to phone width (375 px).
