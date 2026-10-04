"""Vercel entry point (serverless): Vercel serves the ASGI object named `app`.
Locally you still run:  uvicorn app.main:app --port 8001"""
from app.main import app  # noqa: F401
