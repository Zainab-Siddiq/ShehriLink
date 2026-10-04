"""Vercel entry point (serverless): Vercel serves the ASGI object named `app`.
Locally you still run:  python run.py"""
from app.main import app  # noqa: F401
