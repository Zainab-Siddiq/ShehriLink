"""Vercel entry point (serverless). Locally you still run:  python run.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402,F401  (Vercel serves the ASGI object named `app`)
