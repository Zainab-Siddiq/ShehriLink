from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .routers import agent, assignments, complaints, dashboard, demo, reference, verifications


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()  # creates tables if missing
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

for r in (complaints.router, agent.router, assignments.router, verifications.router,
          reference.router, dashboard.router, demo.router):
    app.include_router(r)


@app.get("/health", tags=["Meta"])
def health():
    return {"status": "ok"}


@app.get("/", tags=["Meta"])
def root():
    return {"service": "Municipal Complaint Resolution API", "docs": "/docs"}
