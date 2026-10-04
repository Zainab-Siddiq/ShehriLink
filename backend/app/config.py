import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _database_url() -> str:
    """SQLite file by default. Set DATABASE_URL to a Postgres URL (e.g. Neon) for hosting on serverless
    platforms; the usual `postgres://` / `postgresql://` forms are mapped to the psycopg2 driver."""
    url = os.getenv("DATABASE_URL", "").strip() or f"sqlite:///{os.path.join(BASE_DIR, 'municipal.db')}"
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


DATABASE_URL = _database_url()

# After this many reopens a complaint is ESCALATED instead of looping forever.
MAX_REOPENS = int(os.getenv("MAX_REOPENS", "3"))

# Load the demo data the first time the (empty) database is used. Handy on hosted databases (AUTO_SEED=1).
AUTO_SEED = os.getenv("AUTO_SEED", "0").strip().lower() in ("1", "true", "yes")

# /demo/* can wipe the whole database. Set ENABLE_DEMO_ROUTES=0 on a public deployment.
ENABLE_DEMO_ROUTES = os.getenv("ENABLE_DEMO_ROUTES", "1").strip().lower() not in ("0", "false", "no")
