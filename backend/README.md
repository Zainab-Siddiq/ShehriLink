# Municipal Complaint Resolution - Backend

FastAPI + SQLite + SQLAlchemy + Pydantic. A complaint can only be closed through a PASSED verification.

## Run

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m app.seed.seed_data --reset     # create tables + load demo data
uvicorn app.main:app --reload --port 8000
```

Swagger UI: http://localhost:8000/docs

## Tests

```bash
python -m pytest -q
```

## Demo (complaint MC-0011, "Streetlight outside my house hasn't worked for 3 days.")

After understanding -> investigation -> decision -> assignment:

```bash
curl -X POST localhost:8000/demo/complaints/11/simulate-technician
curl -X POST localhost:8000/demo/complaints/11/simulate-verification   # FAILS -> reopened (cycle 2)
# POST /complaints/11/decision with is_replan=true, POST /complaints/11/assignments, then:
curl -X POST localhost:8000/demo/complaints/11/simulate-technician
curl -X POST localhost:8000/demo/complaints/11/simulate-verification   # PASSES -> closed
```

Reset data any time: `POST /demo/reset`.
