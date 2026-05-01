"""
Seed all curriculum courses into the `courses` table.

Mapping:
  Year 1 Sem II  → batch=2nd,  semester=2
  Year 2 Sem I   → batch=3rd,  semester=1
  Year 2 Sem II  → batch=3rd,  semester=2
  Year 3 Sem I   → batch=4th,  semester=1
  Year 3 Sem II  → batch=4th,  semester=2
  Year 4         → skipped (TBD placeholders)

Run:
    python3 -m scripts.seed_courses
    python3 -m scripts.seed_courses --force   # clear and re-seed
"""
import sys, os, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.database.db import init_db, get_session
from src.database.models import Course

# (curriculum_year, curriculum_semester) → (batch, semester)
BATCH_MAP = {
    (1, 2): ("2nd", 2),
    (2, 1): ("3rd", 1),
    (2, 2): ("3rd", 2),
    (3, 1): ("4th", 1),
    (3, 2): ("4th", 2),
}

COURSES = [
    # ── Year 1 Semester II ────────────────────────────────────────────────────
    {"year": 1, "sem": 2, "name": "Introduction to Emerging Technologies",       "credit_hours": 3, "is_lab": False},
    {"year": 1, "sem": 2, "name": "Communicative English Language Skills II",    "credit_hours": 3, "is_lab": False},
    {"year": 1, "sem": 2, "name": "Basic Computer Programming",                  "credit_hours": 3, "is_lab": True},
    {"year": 1, "sem": 2, "name": "Applied Mathematics",                         "credit_hours": 3, "is_lab": False},
    {"year": 1, "sem": 2, "name": "History of Ethiopia and the Horn of Africa",  "credit_hours": 3, "is_lab": False},
    {"year": 1, "sem": 2, "name": "Anthropology of Ethiopian Societies and Cultures", "credit_hours": 2, "is_lab": False},
    {"year": 1, "sem": 2, "name": "Moral and Civic Education",                   "credit_hours": 2, "is_lab": False},

    # ── Year 2 Semester I ─────────────────────────────────────────────────────
    {"year": 2, "sem": 1, "name": "Global Trends",                               "credit_hours": 2, "is_lab": False},
    {"year": 2, "sem": 1, "name": "Inclusiveness",                               "credit_hours": 2, "is_lab": False},
    {"year": 2, "sem": 1, "name": "Basic Computer Programming II",               "credit_hours": 3, "is_lab": True},
    {"year": 2, "sem": 1, "name": "Fundamentals of Database Systems",            "credit_hours": 3, "is_lab": True},
    {"year": 2, "sem": 1, "name": "Introduction to Statistics",                  "credit_hours": 3, "is_lab": False},
    {"year": 2, "sem": 1, "name": "Fundamentals of Electricity and Electronics Devices", "credit_hours": 3, "is_lab": True},
    {"year": 2, "sem": 1, "name": "Economics",                                   "credit_hours": 3, "is_lab": False},

    # ── Year 2 Semester II ────────────────────────────────────────────────────
    {"year": 2, "sem": 2, "name": "Operating Systems",                           "credit_hours": 3, "is_lab": True},
    {"year": 2, "sem": 2, "name": "Computer Organization and Architecture",      "credit_hours": 3, "is_lab": False},
    {"year": 2, "sem": 2, "name": "Data Communication and Computer Networks",    "credit_hours": 3, "is_lab": False},
    {"year": 2, "sem": 2, "name": "Data Structures and Algorithms",              "credit_hours": 3, "is_lab": True},
    {"year": 2, "sem": 2, "name": "Discrete Mathematics",                        "credit_hours": 3, "is_lab": False},
    {"year": 2, "sem": 2, "name": "Internet Programming I",                      "credit_hours": 3, "is_lab": True},

    # ── Year 3 Semester I ─────────────────────────────────────────────────────
    {"year": 3, "sem": 1, "name": "Systems Analysis and Design",                 "credit_hours": 3, "is_lab": False},
    {"year": 3, "sem": 1, "name": "Multimedia Systems",                          "credit_hours": 3, "is_lab": True},
    {"year": 3, "sem": 1, "name": "Object-Oriented Programming",                 "credit_hours": 3, "is_lab": True},
    {"year": 3, "sem": 1, "name": "Internet Programming II",                     "credit_hours": 3, "is_lab": True},
    {"year": 3, "sem": 1, "name": "Advanced Database Systems",                   "credit_hours": 3, "is_lab": True},
    {"year": 3, "sem": 1, "name": "Telecommunication Technologies",              "credit_hours": 2, "is_lab": False},

    # ── Year 3 Semester II ────────────────────────────────────────────────────
    {"year": 3, "sem": 2, "name": "Geographic Information Systems and Remote Sensing", "credit_hours": 3, "is_lab": True},
    {"year": 3, "sem": 2, "name": "Introduction to Distributed Systems",         "credit_hours": 3, "is_lab": False},
    {"year": 3, "sem": 2, "name": "Information Technology Project Management",   "credit_hours": 3, "is_lab": False},
    {"year": 3, "sem": 2, "name": "Event-Driven Programming",                    "credit_hours": 3, "is_lab": True},
    {"year": 3, "sem": 2, "name": "Information Storage and Retrieval",           "credit_hours": 3, "is_lab": False},
    {"year": 3, "sem": 2, "name": "Computer Maintenance and Technical Support",  "credit_hours": 3, "is_lab": True},
]


def seed(force: bool = False) -> None:
    init_db()
    with get_session() as session:
        existing = session.query(Course).count()
        if existing and not force:
            print(f"ℹ️  Courses already seeded ({existing} rows). Use --force to re-seed.")
            return

        if force:
            session.query(Course).delete()
            print("🗑  Cleared existing courses.")

        added = 0
        for c in COURSES:
            batch, semester = BATCH_MAP[(c["year"], c["sem"])]
            course = Course(
                name=c["name"],
                credit_hours=c["credit_hours"],
                is_lab=c["is_lab"],
                batch=batch,
                semester=semester,
                instructor="TBA",
            )
            session.add(course)
            added += 1

        print(f"\n✅ Seeded {added} courses:\n")
        # Print summary by batch
        for (yr, sm), (batch, semester) in sorted(BATCH_MAP.items()):
            group = [c for c in COURSES if c["year"] == yr and c["sem"] == sm]
            print(f"  Year {yr} Sem {sm} → batch={batch}, semester={semester} ({len(group)} courses)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    seed(force=args.force)
