"""
Seed the curriculum data from curriculum.json into the database.

Usage (from telegram_bot/ directory):
    python -m scripts.seed_curriculum
    python -m scripts.seed_curriculum --force   # re-seed even if data exists
"""
import json
import sys
import argparse
from pathlib import Path

# Allow running from telegram_bot/ root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database.db import init_db, get_session
from src.database.models import CurriculumSemester, CurriculumCourse


CURRICULUM_FILE = Path(__file__).resolve().parent.parent.parent / "curriculum.json"


def seed(force: bool = False) -> None:
    init_db()

    with get_session() as session:
        existing = session.query(CurriculumSemester).count()
        if existing and not force:
            print(f"ℹ️  Curriculum already seeded ({existing} semesters). Use --force to re-seed.")
            return

        if force:
            # Clear existing curriculum data
            session.query(CurriculumCourse).delete()
            session.query(CurriculumSemester).delete()
            print("🗑  Cleared existing curriculum data.")

        data = json.loads(CURRICULUM_FILE.read_text(encoding="utf-8"))
        semesters_added = 0
        courses_added = 0

        for sem_data in data["semesters"]:
            sem = CurriculumSemester(
                year=sem_data["year"],
                semester=sem_data["semester"],
                label=sem_data["label"],
                status=sem_data.get("status"),
            )
            session.add(sem)
            session.flush()  # get sem.id

            for c in sem_data["courses"]:
                course = CurriculumCourse(
                    semester_id=sem.id,
                    code=c.get("code", "TBD"),
                    title=c.get("title", "TBD"),
                    full_name=c.get("full_name"),
                    credits=c.get("credits"),
                    credit_hours=c.get("credit_hours"),
                    note=c.get("note"),
                )
                session.add(course)
                courses_added += 1

            semesters_added += 1
            print(f"  ✅ {sem_data['label']} — {len(sem_data['courses'])} courses")

        print(f"\n✅ Seeded {semesters_added} semesters, {courses_added} courses.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed curriculum data into the database.")
    parser.add_argument("--force", action="store_true", help="Re-seed even if data exists.")
    args = parser.parse_args()
    seed(force=args.force)
