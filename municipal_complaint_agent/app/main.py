"""
FastAPI integration layer.

Run:  python run.py          (or)   uvicorn app.main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app import __version__
from app.config import get_settings
from app.data.mock_data import DEMO_SCENARIOS, SCENARIO_HELP
from app.data.mock_database import get_repository
from app.graph.state import ComplaintState
from app.graph.workflow import ManualVerificationError, process_complaint, verify_manually
from app.models.schemas import ManualVerificationRequest, ProcessComplaintRequest

app = FastAPI(
    title="Municipal Complaint Resolution Agent",
    description="Agentic (LangGraph) backend: classify -> locate -> dedupe -> prioritise -> route -> "
                "assign -> verify -> replan/close/escalate.",
    version=__version__,
)

# Allow a frontend dev server (React/Vite/Next on another port) to call the API.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health() -> dict:
    s = get_settings()
    return {"status": "ok", "version": __version__, "llm_provider": s.llm_provider,
            "llm_enabled": s.llm_enabled, "max_retries": s.max_retries,
            "default_verification_scenario": s.verification_scenario}


@app.get("/api/scenarios")
def scenarios() -> dict:
    """Ready-made demo requests + the verification scenarios you can force."""
    return {"demo_requests": DEMO_SCENARIOS, "verification_scenarios": SCENARIO_HELP}


@app.post("/api/complaints/process", response_model=ComplaintState)
def process(req: ProcessComplaintRequest) -> ComplaintState:
    """Run a complaint through the full agent workflow and return the final state
    (including `history` = the Agent Activity Timeline)."""
    try:
        return process_complaint(
            complaint_id=req.complaint_id,
            description=req.description,
            location=req.location,
            verification_scenario=req.verification_scenario,
        )
    except Exception as exc:  # last-resort guard; agents already handle LLM failures
        raise HTTPException(status_code=500, detail=f"Workflow failed: {type(exc).__name__}: {exc}")


@app.post("/api/complaints/{complaint_id}/verify", response_model=ComplaintState)
def verify(complaint_id: str, req: ManualVerificationRequest) -> ComplaintState:
    """Manual verification (scenario `manual`): passed=true closes the complaint, passed=false sends it
    back through replan/reassign (or escalates after max retries)."""
    try:
        return verify_manually(complaint_id, req.passed, req.note)
    except ManualVerificationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Verification failed: {type(exc).__name__}: {exc}")


@app.get("/api/complaints", response_model=list[ComplaintState])
def list_complaints() -> list[ComplaintState]:
    """All complaints processed so far, newest first."""
    return [ComplaintState.model_validate(d) for d in get_repository().list_processed_complaints()]


@app.get("/api/complaints/{complaint_id}", response_model=ComplaintState)
def get_complaint(complaint_id: str) -> ComplaintState:
    """Fetch the last processed result of a complaint (from the repository)."""
    data = get_repository().get_processed_complaint(complaint_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Complaint '{complaint_id}' has not been processed.")
    return ComplaintState.model_validate(data)


# ------------------------------------------------------------ built frontend (single-container deploy)
# Set STATIC_DIR to the Vite build output (frontend/dist) and this API serves the web app too,
# so everything lives on one origin. Registered last so every /api route above wins.
_static = os.getenv("STATIC_DIR", "").strip()
if _static and (Path(_static) / "index.html").is_file():
    _root = Path(_static).resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        target = (_root / path).resolve()
        if path and target.is_file() and _root in target.parents:
            return FileResponse(target)
        return FileResponse(_root / "index.html")        # React Router handles the path
