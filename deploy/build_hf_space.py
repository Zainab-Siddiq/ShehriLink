"""Assemble a ready-to-push Hugging Face Space folder.

    python deploy/build_hf_space.py [OUT_DIR]        (default: ../ShehriLink-space)

Builds the React app and copies backend + agent + built frontend + start.py + README.md into OUT_DIR.
Run it again whenever the code changes, then commit and push OUT_DIR to the Space.
"""
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HF = Path(__file__).resolve().parent / "hf"
FRONTEND = REPO / "municipal_complaint_agent" / "frontend"
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", "tests", "test_*.db", ".env", "conftest.py")


def run(cmd: list, cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, shell=sys.platform == "win32")


def requirements() -> str:
    """Runtime requirements of both backends, de-duplicated (tests are not needed in the Space)."""
    seen: dict = {}
    for f in (REPO / "backend" / "requirements.txt", REPO / "municipal_complaint_agent" / "requirements.txt"):
        for line in f.read_text(encoding="utf-8").splitlines():
            req = line.split("#")[0].strip()
            name = req.lower().replace("[", " ").split()[0].split(">")[0].split("<")[0].split("=")[0] if req else ""
            if req and name not in ("pytest",) and name not in seen:
                seen[name] = req
    return "\n".join(seen.values()) + "\n"


def main() -> None:
    out = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else REPO.parent / "ShehriLink-space"

    if not (FRONTEND / "node_modules").is_dir():
        run(["npm", "ci"], FRONTEND)
    run(["npm", "run", "build"], FRONTEND)

    for name in ("backend", "agent", "static"):                  # keep out/.git, replace everything else
        shutil.rmtree(out / name, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)

    shutil.copytree(REPO / "backend", out / "backend", ignore=SKIP)
    shutil.copytree(REPO / "municipal_complaint_agent" / "app", out / "agent" / "app", ignore=SKIP)
    shutil.copy2(REPO / "municipal_complaint_agent" / "run.py", out / "agent" / "run.py")
    shutil.copytree(FRONTEND / "dist", out / "static")
    shutil.copy2(HF / "start.py", out / "start.py")
    shutil.copy2(HF / "README.md", out / "README.md")
    (out / "requirements.txt").write_text(requirements(), encoding="utf-8")
    (out / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
    print(f"Space folder ready: {out}")


if __name__ == "__main__":
    main()
