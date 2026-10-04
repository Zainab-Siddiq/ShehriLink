# Municipal Complaint Resolution Agent (Agentic AI backend)

A **LangGraph** multi-agent backend that turns a citizen complaint into a *closed-loop* resolution:

```
Complaint -> Classify -> Locate -> Duplicate check -> Priority -> Department -> Assign
          -> Verify resolution -> (Close | Replan -> Reassign -> Verify ... | Escalate)
```

The key feature is **closed-loop verification**: a team saying "fixed" is not enough. The complaint is only
closed when independent evidence (a citizen follow-up) confirms it. Otherwise the system **replans and
reassigns**, and **escalates** to a human after a configurable number of failures.

Works **without any API key** (deterministic mock mode) and with OpenAI / Anthropic / Gemini / any
OpenAI-compatible server when you add a key.

---

## 1. Quick start

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py demo                                      # runs all 5 scenarios in your terminal
python run.py                                           # starts the API: http://localhost:8000  (docs: /docs)
python -m pytest -q                                     # 64 tests, no network / API key needed
```

Python 3.10+ is required (tested on 3.12).

---

## 2. Architecture

```
   Frontend  --HTTP-->  FastAPI (app/main.py)   POST /api/complaints/process
                              |
                              v
                  LangGraph workflow (app/graph/workflow.py)
                  shared state = ComplaintState (Pydantic); every agent appends to `history`

 START
   |
   v
 [Classification] -> [Location] -> [History/Duplicate] -> [Priority] -> [Department] -> [Assignment] <------+
                                                                                            |    |           |
                                                                          no team available |    | team found|
                                                                                            |    v           |
                                                                                            |  [Verification]|
                                                                                            |   |     |    | |
                                                                                            |   |     |    | |
                                                           verified ------------------------+---+     |    | |
                                                              |                             |         |    | |
                                                              v                             |   failed, retries left
                                                           [Close] --> END                  |         |    | |
                                                                                            |         v    | |
                                                                                            |      [Replan]-+ (loop back to Assignment)
                                                                                            |
                                          failed, retries used up ---------------+          |
                                                                                 v          v
                                                                              [Escalate] --> END

 Agents --> app/llm.py                    (mock | openai | anthropic | google) + rule-based fallback
 Agents --> app/data/mock_database.py     (ComplaintRepository)  <-- swap for PostgreSQL
```

**Design principle:** the LLM is used where language understanding is needed (classification, location
extraction, ambiguous duplicates, priority adjustment, judging verification evidence). Everything that must
be predictable (zone lookup, priority rules, department routing, team assignment, loop control) is
**deterministic code**. If the LLM fails, each agent falls back to rules and records the problem in `errors`.

---

## 3. Agent responsibilities

| # | Agent (file) | Job | LLM? | Fallback / guardrail |
|---|---|---|---|---|
| 1 | Classification (`agents/classification.py`) | category + subcategory + confidence | structured output | keyword scoring |
| 2 | Location (`agents/location.py`) | area, zone, location text. **Never invents**: missing -> `unknown` | extracts area text | regex over known areas; zone always from the area table |
| 3 | History/Duplicate (`agents/history.py`) | detect duplicate / related open complaint | only for "unsure" cases | normalised cosine text similarity + location similarity (no vector DB) |
| 4 | Priority (`agents/priority.py`) | LOW / MEDIUM / HIGH / CRITICAL + reason | may adjust rule baseline by **+-1 level** | explicit rule engine + guidelines |
| 5 | Department (`agents/department.py`) | responsible department + reason | only for category `other` | category -> department table |
| 6 | Assignment (`agents/assignment.py`) | team by department, zone, availability, workload, previous failures | no (deterministic) | no team -> escalation |
| 7 | Verification (`agents/verification.py`) | team report vs citizen feedback -> verified / failed | judges the evidence | keyword judge |
| - | Replan / Close / Escalate (`agents/lifecycle.py`) | control nodes of the loop | no | - |

---

## 4. LangGraph workflow & the verification/replan loop

Defined in `app/graph/workflow.py`; branching logic in `app/graph/routing.py`:

```
assignment --team found--> verification --resolved------------------------------------> close --> END
     ^   |                       |
     |   |                       +--failed AND retry_count <  max_retries--> replan --+
     |   |                       |                                                    |
     +---+---------------------------------------------------------------------------+  (back to assignment)
     |                           +--failed AND retry_count >= max_retries--> escalate --> END
     +--no team available----------------------------------------------------> escalate --> END
```

How the loop works:

1. The assigned team "reports" the fix (`team_report`).
2. The Verification Agent gets independent evidence (`citizen_feedback`) and decides `verified` or `failed`.
3. On **failure** `retry_count` is incremented (it counts failed verifications so far).
4. **Replan** adds the failed team to `failed_teams`; the Assignment Agent then prefers a *different* available team
   (same-zone team -> all-zone Rapid Response team -> other zones).
5. When `retry_count >= MAX_RETRIES` (default **3**) the complaint is **ESCALATED** instead of looping forever.
   A hard LangGraph `recursion_limit` is a second safety net.

So with `MAX_RETRIES=3` a complaint gets at most **3 team attempts**; the 3rd failed verification escalates.

### Controlling the mock verification (for demos)

Send `verification_scenario` in the request (or set `VERIFICATION_SCENARIO` in `.env`):

| scenario | behaviour |
|---|---|
| `success` | first verification passes |
| `fail_once` | fails, replan + reassign, then passes |
| `fail_twice` / `fail_<n>` | first *n* verifications fail, then pass |
| `always_fail` | never passes -> escalation after `MAX_RETRIES` |

For real evidence later, implement `VerificationProvider` in `app/data/mock_database.py`
(e.g. an SMS/app follow-up with the citizen) and register it with `set_verification_provider(...)`.

---

## 5. State structure (`app/graph/state.py`)

```
complaint_id, description, location                                   <- input
category, subcategory, classification_confidence                      <- Classification
area, zone, location_text, location_confidence                        <- Location
duplicate, related_complaint_id, duplicate_reason                     <- History/Duplicate
priority, priority_reason                                             <- Priority
department, department_reason                                         <- Department
assigned_team, assigned_team_name, assignment_reason, failed_teams    <- Assignment / Replan
verification_scenario, team_report, citizen_feedback,
verification_status (pending|verified|failed), verification_reason, resolved   <- Verification
retry_count, max_retries, escalation_reason                           <- loop control
status   RECEIVED | ASSIGNED | VERIFIED | VERIFICATION_FAILED | REPLANNING | CLOSED | ESCALATED
history  [HistoryEntry]   <- Agent Activity Timeline
errors   [str]            <- LLM failures / fallbacks (the workflow still completes)
```

`HistoryEntry`:

```json
{"agent": "Resolution Verification Agent", "action": "Verification failed", "result": "failed",
 "status": "failed", "message": "Verification failed", "timestamp": "2026-10-03T18:26:11+00:00",
 "details": {"attempt": 1, "citizen_feedback": "Streetlight is still not working.", "reason": "..."}}
```

`status` is one of `success` (check), `failed` (cross), `replanning` (loop arrow), `escalated` (warning), `info` (dot):
ready to render as the timeline. `message` is the short text ("Classification completed", "Replanning", ...).

---

## 6. Environment variables

Copy `.env.example` to `.env` (never commit `.env`).

| Variable | Meaning | Default |
|---|---|---|
| `LLM_PROVIDER` | `mock`, `openai`, `anthropic`, `google` | `mock` |
| `MODEL_NAME` | model id (empty = provider default) | empty |
| `API_KEY` | provider key | empty |
| `LLM_BASE_URL` | OpenAI-compatible endpoint (Groq, OpenRouter, Ollama...) | empty |
| `LLM_TIMEOUT` | seconds per LLM call | `30` |
| `MAX_RETRIES` | failed verifications before escalation | `3` |
| `VERIFICATION_SCENARIO` | default mock scenario | `success` |

### Changing the LLM provider

Only `.env` changes, no code:

```bash
# OpenAI
LLM_PROVIDER=openai
MODEL_NAME=gpt-4o-mini
API_KEY=sk-...

# Anthropic (Claude)
LLM_PROVIDER=anthropic
MODEL_NAME=claude-haiku-4-5-20251001
API_KEY=sk-ant-...

# Gemini  (pip install langchain-google-genai)
LLM_PROVIDER=google
MODEL_NAME=gemini-2.5-flash
API_KEY=...

# Groq / OpenRouter / local Ollama through the OpenAI-compatible route
LLM_PROVIDER=openai
LLM_BASE_URL=https://api.groq.com/openai/v1      # Ollama: http://localhost:11434/v1
MODEL_NAME=<model id>
API_KEY=<key>                                     # Ollama: any non-empty text
```

Another provider? Add one `if provider == "...":` branch in `_build_chat_model()` in `app/llm.py`.
`GET /api/health` shows which mode is active. If a key is wrong or the API is down, the response still
completes using rules, and `errors` lists what failed.

---

## 7. API

Start: `python run.py` -> http://localhost:8000/docs (CORS is open, so a frontend dev server can call it).

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/complaints/process` | run the full workflow, returns final state + history |
| `GET` | `/api/complaints/{id}` | last processed result of a complaint |
| `GET` | `/api/scenarios` | the 5 demo requests + verification scenarios (handy for a demo button) |
| `GET` | `/api/health` | provider, mode, retry limit |

### Example request

```bash
curl -X POST http://localhost:8000/api/complaints/process \
  -H "Content-Type: application/json" \
  -d '{
        "complaint_id": "C-1004",
        "description": "The streetlight in front of my house in Canal Town is not working since yesterday.",
        "location": "Canal Town",
        "verification_scenario": "fail_once"
      }'
```

PowerShell: `Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/complaints/process -ContentType "application/json" -Body '{...}'`

### Example response (shortened)

```json
{
  "complaint_id": "C-1004",
  "category": "streetlight",
  "subcategory": "streetlight_not_working",
  "area": "Canal Town",
  "zone": "Zone A",
  "duplicate": false,
  "priority": "MEDIUM",
  "department": "Electrical Department",
  "assigned_team": "ELEC-RR",
  "assigned_team_name": "Electrical Rapid Response Team",
  "failed_teams": ["ELEC-A"],
  "verification_status": "verified",
  "verification_reason": "The reported issue is confirmed resolved.",
  "resolved": true,
  "retry_count": 1,
  "max_retries": 3,
  "status": "CLOSED",
  "errors": [],
  "history": [
    {"agent": "Classification Agent", "status": "success", "message": "Classification completed", "result": "streetlight"},
    {"agent": "Location Agent", "status": "success", "message": "Location identified", "result": "Canal Town (Zone A)"},
    {"agent": "History/Duplicate Agent", "status": "success", "message": "Duplicate check completed", "result": "no duplicate"},
    {"agent": "Priority Agent", "status": "success", "message": "Priority determined", "result": "MEDIUM"},
    {"agent": "Department Agent", "status": "success", "message": "Department selected", "result": "Electrical Department"},
    {"agent": "Assignment Agent", "status": "success", "message": "Team assigned", "result": "ELEC-A"},
    {"agent": "Electrical Team A", "status": "success", "message": "Resolution attempted"},
    {"agent": "Resolution Verification Agent", "status": "failed", "message": "Verification failed", "result": "failed"},
    {"agent": "Replanning Agent", "status": "replanning", "message": "Replanning", "result": "retry 1 of 3"},
    {"agent": "Assignment Agent", "status": "success", "message": "New team assigned", "result": "ELEC-RR"},
    {"agent": "Electrical Rapid Response Team", "status": "success", "message": "Resolution attempted"},
    {"agent": "Resolution Verification Agent", "status": "success", "message": "Verification passed", "result": "verified"},
    {"agent": "Closure Agent", "status": "success", "message": "Complaint closed", "result": "CLOSED"}
  ]
}
```

(Every history item also has `action`, `timestamp` and `details`.)
Errors: invalid body or unknown `verification_scenario` -> `422`; unexpected failure -> `500`; unknown id on GET -> `404`.

---

## 8. Demo scenarios

`python run.py demo` runs all five (or `python run.py demo <name>`). The same requests are returned by
`GET /api/scenarios` and covered by `tests/test_scenarios.py`.

| Name | What you will see |
|---|---|
| `normal` | broken streetlight (University Town) -> ELEC-A -> verified -> **CLOSED** |
| `high_priority` | open manhole near a school -> priority **HIGH**, Sewerage Department |
| `duplicate` | Hayatabad Phase 3 streetlight -> **duplicate of #102** |
| `failed_verification` | "fixed" -> verification **fails** -> replan -> ELEC-RR -> verified -> CLOSED |
| `max_retry` | verification fails 3 times -> **ESCALATED** |

Free-form try-out: `python run.py complaint "Garbage not collected in Gulbahar" --scenario fail_twice`

Mock data (departments, zones, areas, teams, existing complaints, verification texts) lives in `app/data/mock_data.py`.
Known areas: University Town, Canal Town, Tehkal (Zone A) / Hayatabad, Regi Model Town, Industrial Estate (Zone B) /
Saddar, Gulbahar, Peshawar Cantt (Zone C) / Ring Road, Warsak Road, Charsadda Road (Zone D). A complaint mentioning
none of them gets `area: "unknown"` and goes to the department's all-zone rapid-response team.

---

## 9. Integration guide

**Frontend team**
- Call `POST /api/complaints/process`; render `history` as the Agent Activity Timeline
  (`status` = icon, `message` = text, `details` = tooltip data).
- Show `status` (`CLOSED` / `ESCALATED`), `priority`, `department`, `assigned_team_name`, `retry_count`.
- Use `GET /api/scenarios` to build a "Run demo" menu; pass `verification_scenario` to force success/failure live.
- The call is synchronous (instant in mock mode, a few seconds with an LLM): show a spinner.

**Database team (PostgreSQL)**
- Implement `ComplaintRepository` (a few small methods, documented in `app/data/mock_database.py`):
  open complaints, areas/aliases, department names, teams, save/get processed complaint.
- Register it once at startup: `from app.data.mock_database import set_repository; set_repository(PostgresRepository(...))`.
- No agent code changes. `get_open_complaints` must not return CLOSED complaints.

**Real verification** (citizen SMS/app answer): implement `VerificationProvider.get_resolution_evidence(...)`
and call `set_verification_provider(...)`. The graph currently verifies synchronously; for a real asynchronous
follow-up, re-run the graph when the citizen answers.

---

## 10. Project structure

```
municipal_complaint_agent/
|-- README.md  requirements.txt  .env.example  .gitignore  pytest.ini  run.py
|-- app/
|   |-- main.py                 FastAPI endpoints
|   |-- config.py               env settings
|   |-- llm.py                  provider-agnostic LLM + structured output + fallback
|   |-- graph/    state.py  workflow.py  routing.py
|   |-- agents/   classification  location  history  priority  department
|   |             assignment  verification  lifecycle (replan/close/escalate)
|   |-- data/     mock_data.py  mock_database.py (repository interface)
|   |-- models/   schemas.py    structured outputs + request model
|   `-- utils/    similarity.py dependency-free duplicate similarity
`-- tests/        test_agents.py  test_workflow.py  test_scenarios.py
```

## 11. Troubleshooting

- *Symbols garbled on a Windows terminal:* `run.py` switches stdout to UTF-8; use Windows Terminal or `chcp 65001`.
- *`errors` contains "LLM call failed":* wrong key/model name or no network. The result is still valid (rule fallback).
  Set `LLM_PROVIDER=mock` to demo fully offline.
- *Port in use:* `python run.py serve --port 9000`.
