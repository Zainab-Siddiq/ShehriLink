"""Entry point of the Hugging Face Space (Gradio SDK, used only as a free Python host).

Starts the database backend on 127.0.0.1:8001 and the agent backend on :7860, which also
serves the built React app from ./static (see STATIC_DIR in agent/app/main.py).
"""
import atexit
import os
import runpy
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# Free Gradio Spaces run on ZeroGPU, which refuses to keep a Space alive unless it registers a
# @spaces.GPU function. We never call it (the app needs no GPU); it only satisfies that startup check.
try:
    import spaces

    @spaces.GPU
    def _zerogpu_placeholder() -> int:
        return 0
except ImportError:                      # running anywhere else (local machine, normal CPU host)
    pass

ROOT = Path(__file__).resolve().parent
PORT = os.getenv("PORT", "7860")

os.environ.setdefault("STATIC_DIR", str(ROOT / "static"))
os.environ.setdefault("DB_BACKEND_URL", "http://127.0.0.1:8001")
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("VERIFICATION_SCENARIO", "manual")

# The database file is not part of the Space repo: create it and load the demo data (no-op if it has data).
subprocess.run([sys.executable, "-m", "app.seed.seed_data"], cwd=ROOT / "backend", check=False)

db = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001"],
                      cwd=ROOT / "backend")
atexit.register(db.terminate)

for _ in range(60):                                   # wait until the database backend answers
    try:
        urllib.request.urlopen("http://127.0.0.1:8001/health", timeout=1)
        break
    except Exception:
        time.sleep(0.5)

agent_dir = ROOT / "agent"
os.chdir(agent_dir)
sys.path.insert(0, str(agent_dir))
sys.argv = ["run.py", "serve", "--host", "0.0.0.0", "--port", PORT]
runpy.run_path(str(agent_dir / "run.py"), run_name="__main__")
