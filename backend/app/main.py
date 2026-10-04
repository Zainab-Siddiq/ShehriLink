import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from .config import AUTO_SEED, ENABLE_DEMO_ROUTES
from .database import SessionLocal, init_db
from .routers import agent, assignments, complaints, dashboard, demo, reference, verifications
from .seed.seed_data import seed

_ready = False
_ready_lock = threading.Lock()


def ensure_ready() -> None:
    """Create the tables (and optionally load the demo data) once per process. Idempotent."""
    global _ready
    if _ready:
        return
    with _ready_lock:
        if _ready:
            return
        init_db()  # creates tables if missing
        if AUTO_SEED:
            db = SessionLocal()
            try:
                seed(db)  # does nothing when data exists
                db.commit()
            finally:
                db.close()
        _ready = True


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_ready()
    yield


app = FastAPI(
    title="Municipal Complaint Resolution API",
    version="1.0.0",
    description="Backend for the closed-loop municipal complaint agent. "
                "A complaint can only be closed through a PASSED verification.",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
                   expose_headers=["X-Total-Count"])


@app.middleware("http")
async def _init_on_first_request(request: Request, call_next):
    # Serverless hosts may not run the lifespan hook, so make sure the database is ready on the first request.
    if not _ready:
        await run_in_threadpool(ensure_ready)
    return await call_next(request)


routers = [complaints.router, agent.router, assignments.router, verifications.router,
           reference.router, dashboard.router]
if ENABLE_DEMO_ROUTES:
    routers.append(demo.router)
for r in routers:
    app.include_router(r)


@app.get("/health", tags=["Meta"])
def health():
    return {"status": "ok"}


@app.get("/", tags=["Meta"])
def root():
    return {"service": "Municipal Complaint Resolution API", "docs": "/docs"}
