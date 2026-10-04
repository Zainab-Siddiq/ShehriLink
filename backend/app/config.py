import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'municipal.db')}")

# After this many reopens a complaint is ESCALATED instead of looping forever.
MAX_REOPENS = int(os.getenv("MAX_REOPENS", "3"))
