# Municipal Complaint Resolution - integrated project

Three existing parts, connected:

```
Frontend (React, :5173)  ->  Agent backend (LangGraph, :8000)  ->  Database backend (FastAPI + SQLite, :8001)
```

Run each part in its own terminal (Python 3.11+ and Node 18+).

**1. Database backend** (`backend/`)
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --port 8001          # municipal.db already contains the demo data
# reset the data any time:  python -m app.seed.seed_data --reset
```

**2. Agent backend** (`municipal_complaint_agent/`)
```bash
cd municipal_complaint_agent
pip install -r requirements.txt
cp .env.example .env                      # Windows: copy .env.example .env   (DB_BACKEND_URL=http://localhost:8001)
python run.py                             # http://localhost:8000
```

**3. Frontend** (`municipal_complaint_agent/frontend/`)
```bash
cd municipal_complaint_agent/frontend
npm install
npm run dev                               # http://localhost:5173
```

Notes
* Integration code: `municipal_complaint_agent/app/data/http_repository.py` (agent -> database backend) and a few lines in `run.py`. The frontend and the agents are unchanged.
* Without `DB_BACKEND_URL` the agents use their in-memory mock data (standalone mode, as before).
* Keep `MAX_RETRIES` (agent `.env`) equal to `MAX_REOPENS` (database backend, default 3) - both default to 3.
* The database backend must be running before a complaint is submitted, otherwise the frontend shows "Cannot reach the database backend ...".
* Zone/department/category names differ between the two projects; they are translated by the tables at the top of `http_repository.py`.
* Manual verification (default, `VERIFICATION_SCENARIO=manual`): a new complaint stays open ("Team assigned") until an officer opens it in the admin page (`/admin/complaints/<id>`) and clicks "Fixed - close complaint" or "Not fixed - reassign" (API: `POST /api/complaints/{id}/verify`). The other scenarios (`success`, `fail_once`, ...) still simulate the result automatically; pick them under "Simulation options" on the Submit page.
* Each part keeps its own README and tests.
* Free hosting without a card (Hugging Face Space, Gradio SDK as a Python host): `python deploy/build_hf_space.py` assembles a Space folder (backend + agent + built frontend + `start.py`); push that folder to the Space.
