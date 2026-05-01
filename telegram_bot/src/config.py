import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_TELEGRAM_ID: int = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

# Database — Supabase (preferred) or local PostgreSQL fallback
SUPABASE_DB_URL: str = os.getenv("SUPABASE_DB_URL", "")

DB_HOST: str = os.getenv("DB_HOST", "localhost")
DB_PORT: str = os.getenv("DB_PORT", "5432")
DB_NAME: str = os.getenv("DB_NAME", "itsmb")
DB_USER: str = os.getenv("DB_USER", "postgres")
DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

_local_url = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
DATABASE_URL: str = SUPABASE_DB_URL if SUPABASE_DB_URL else _local_url

# Departments available for selection
DEPARTMENTS = [
    "Information Technology",
    "Computer Science",
    "Software Engineering",
    "Information Systems",
    "Electrical Engineering",
    "Mechanical Engineering",
    "Civil Engineering",
]

# Domain constants
BATCHES = ["2nd", "3rd", "4th"]
SECTIONS = ["A", "B"]
SEMESTERS = [1, 2]

# Time slots: (day, start_hour, end_hour)
# Monday=0 ... Friday=4, hours 8–17
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
HOURS = list(range(8, 17))  # 8,9,...,16  → slots 8-9, 9-10, ..., 16-17

# Morning = 8-12, Afternoon = 12-17
MORNING_CUTOFF = 12

DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
