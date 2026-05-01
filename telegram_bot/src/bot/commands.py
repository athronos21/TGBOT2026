"""
Pure data-access helpers called by conversation handlers.
All DB operations live here so handlers stay clean.
"""
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session

from src.database.models import (
    Course, Room, LabBatchAssignment, TimeSlot, ScheduleEntry,
    CurriculumSemester, CurriculumCourse, AdminProfile,
)
from src.config import DAYS, HOURS, BATCHES, SEMESTERS


# ── Admin / Department ────────────────────────────────────────────────────────

def get_admin_profile(session: Session, telegram_id: int) -> Optional[AdminProfile]:
    """Return the admin's profile, or None if not set up yet."""
    return session.query(AdminProfile).filter_by(telegram_id=telegram_id).first()


def set_admin_department(
    session: Session,
    telegram_id: int,
    department: str,
    full_name: Optional[str] = None,
) -> AdminProfile:
    """Create or update the admin's department selection."""
    profile = session.query(AdminProfile).filter_by(telegram_id=telegram_id).first()
    if profile:
        profile.department = department
        if full_name:
            profile.full_name = full_name
    else:
        profile = AdminProfile(
            telegram_id=telegram_id,
            department=department,
            full_name=full_name,
        )
        session.add(profile)
    session.flush()
    return profile


MAX_BULK_COURSES = 10   # maximum subjects accepted in one bulk message


# ── Courses ──────────────────────────────────────────────────────────────────

def add_course(
    session: Session,
    name: str,
    credit_hours: int,
    is_lab: bool,
    batch: str,
    semester: int,
    instructor: str = "TBA",
) -> Course:
    """
    Add a course. credit_hours must be between 1 and 4 (inclusive).
    Raises ValueError if out of range.
    """
    if not (1 <= credit_hours <= 4):
        raise ValueError(f"Credit hours must be between 1 and 4, got {credit_hours}.")
    course = Course(
        name=name,
        credit_hours=credit_hours,
        is_lab=is_lab,
        batch=batch,
        semester=semester,
        instructor=instructor.strip() if instructor.strip() else "TBA",
    )
    session.add(course)
    session.flush()
    return course


def parse_bulk_courses(raw_text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Parse a bulk course message.  Each non-empty line must follow:

        CourseName | credit_hours | instructor | lab/class | batch | semester

    Fields:
        credit_hours  : integer 1–4
        instructor    : any text, or "tba" / "skip" → stored as "TBA"
        lab/class     : "lab" or "class" (case-insensitive)
        batch         : "2nd", "3rd", or "4th"
        semester      : 1 or 2

    Returns:
        (valid_rows, error_lines)
        valid_rows  — list of dicts ready to pass to add_course()
        error_lines — list of human-readable error strings
    """
    valid: List[Dict[str, Any]] = []
    errors: List[str] = []

    lines = [l.strip() for l in raw_text.strip().splitlines() if l.strip()]

    if len(lines) > MAX_BULK_COURSES:
        errors.append(
            f"❌ Too many courses. Maximum is {MAX_BULK_COURSES} per message "
            f"(you sent {len(lines)})."
        )
        return valid, errors

    for i, line in enumerate(lines, start=1):
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 6:
            errors.append(
                f"Line {i}: wrong number of fields — expected 6, got {len(parts)}.\n"
                f"  ↳ `{line}`"
            )
            continue

        name, cr_raw, instructor_raw, type_raw, batch_raw, sem_raw = parts

        # ── name
        if not name:
            errors.append(f"Line {i}: course name is empty.\n  ↳ `{line}`")
            continue

        # ── credit hours
        if not cr_raw.isdigit() or not (1 <= int(cr_raw) <= 4):
            errors.append(
                f"Line {i}: credit hours must be 1–4, got `{cr_raw}`.\n  ↳ `{line}`"
            )
            continue
        credit_hours = int(cr_raw)

        # ── instructor
        instructor = "TBA" if instructor_raw.lower() in ("tba", "skip", "") else instructor_raw

        # ── lab / class
        type_lower = type_raw.lower()
        if type_lower not in ("lab", "class"):
            errors.append(
                f"Line {i}: type must be `lab` or `class`, got `{type_raw}`.\n  ↳ `{line}`"
            )
            continue
        is_lab = type_lower == "lab"

        # ── batch
        if batch_raw not in BATCHES:
            errors.append(
                f"Line {i}: batch must be one of {BATCHES}, got `{batch_raw}`.\n  ↳ `{line}`"
            )
            continue

        # ── semester
        if not sem_raw.isdigit() or int(sem_raw) not in SEMESTERS:
            errors.append(
                f"Line {i}: semester must be 1 or 2, got `{sem_raw}`.\n  ↳ `{line}`"
            )
            continue

        valid.append(
            dict(
                name=name,
                credit_hours=credit_hours,
                instructor=instructor,
                is_lab=is_lab,
                batch=batch_raw,
                semester=int(sem_raw),
            )
        )

    return valid, errors


def list_courses(session: Session) -> List[Course]:
    return session.query(Course).order_by(Course.batch, Course.name).all()


def delete_course(session: Session, course_id: int) -> bool:
    course = session.get(Course, course_id)
    if course:
        session.delete(course)
        session.flush()
        return True
    return False


def update_instructor(session: Session, course_id: int, instructor: str) -> bool:
    """Update the instructor for a course. Returns False if course not found."""
    course = session.get(Course, course_id)
    if not course:
        return False
    course.instructor = instructor.strip() if instructor.strip() else "TBA"
    session.flush()
    return True


# ── Rooms ─────────────────────────────────────────────────────────────────────

def add_room(
    session: Session,
    name: str,
    room_type: str,
    capacity: Optional[int] = None,
) -> Room:
    room = Room(name=name, room_type=room_type, capacity=capacity)
    session.add(room)
    session.flush()
    return room


def list_rooms(session: Session) -> List[Room]:
    return session.query(Room).order_by(Room.room_type, Room.name).all()


def list_labs(session: Session) -> List[Room]:
    """Return only lab rooms, each with their batch_assignments eagerly loaded."""
    return (
        session.query(Room)
        .filter(Room.room_type == "lab")
        .order_by(Room.name)
        .all()
    )


def delete_room(session: Session, room_id: int) -> bool:
    room = session.get(Room, room_id)
    if room:
        session.delete(room)
        session.flush()
        return True
    return False


# ── Lab ↔ Batch assignments  (strict 1-to-1) ─────────────────────────────────

def assign_lab_to_batch(
    session: Session, room_id: int, batch: str
) -> tuple:
    """
    Assign a lab to exactly one batch.
    Enforces:
      - The lab is not already assigned to a different batch.
      - The batch does not already have a different lab.
    Returns (ok: bool, error_message: str | None).
    """
    from src.database.models import LabBatchAssignment

    # Check: lab already assigned to something?
    existing_lab = (
        session.query(LabBatchAssignment).filter_by(room_id=room_id).first()
    )
    if existing_lab and existing_lab.batch != batch:
        lab = session.get(Room, room_id)
        return False, (
            f"Lab *{lab.name}* is already assigned to *{existing_lab.batch} Year*. "
            f"Remove that assignment first."
        )

    # Check: batch already has a lab?
    existing_batch = (
        session.query(LabBatchAssignment).filter_by(batch=batch).first()
    )
    if existing_batch and existing_batch.room_id != room_id:
        other_lab = session.get(Room, existing_batch.room_id)
        return False, (
            f"*{batch} Year* already has lab *{other_lab.name}* assigned. "
            f"Remove that assignment first."
        )

    # Upsert
    if existing_lab:
        existing_lab.batch = batch          # same lab, update batch (shouldn't happen but safe)
    elif existing_batch:
        existing_batch.room_id = room_id    # same batch, swap lab
    else:
        session.add(LabBatchAssignment(room_id=room_id, batch=batch))

    session.flush()
    return True, None


def remove_lab_assignment(session: Session, room_id: int) -> bool:
    """Remove the batch assignment for a lab. Returns True if one existed."""
    from src.database.models import LabBatchAssignment
    deleted = session.query(LabBatchAssignment).filter_by(room_id=room_id).delete()
    session.flush()
    return deleted > 0


def get_lab_batch_assignments(session: Session) -> dict:
    """
    Return a dict: room_id → batch (str)
    Only includes labs that have an assignment.
    """
    from src.database.models import LabBatchAssignment
    rows = session.query(LabBatchAssignment).all()
    return {row.room_id: row.batch for row in rows}


# ── Time Slots ────────────────────────────────────────────────────────────────

def seed_time_slots(session: Session) -> int:
    """Insert all Mon–Fri 8–17 slots if not already present. Returns count added."""
    added = 0
    for day in DAYS:
        for hour in HOURS:
            exists = (
                session.query(TimeSlot)
                .filter_by(day=day, start_hour=hour)
                .first()
            )
            if not exists:
                session.add(TimeSlot(day=day, start_hour=hour, end_hour=hour + 1))
                added += 1
    session.flush()
    return added


# ── Schedule ──────────────────────────────────────────────────────────────────

def clear_schedule(session: Session) -> int:
    count = session.query(ScheduleEntry).delete()
    return count


def get_schedule(
    session: Session,
    batch: Optional[str] = None,
    section: Optional[str] = None,
    semester: Optional[int] = None,
) -> List[ScheduleEntry]:
    q = session.query(ScheduleEntry)
    if batch:
        q = q.filter(ScheduleEntry.batch == batch)
    if section:
        q = q.filter(ScheduleEntry.section == section)
    if semester:
        q = q.filter(ScheduleEntry.semester == semester)
    return (
        q.join(ScheduleEntry.time_slot)
        .order_by(TimeSlot.day, TimeSlot.start_hour)
        .all()
    )


def format_schedule_text(entries: List[ScheduleEntry]) -> str:
    """Return a nicely formatted schedule string for Telegram."""
    if not entries:
        return "No schedule entries found."

    # Group by batch+section
    from collections import defaultdict
    groups: dict = defaultdict(list)
    for e in entries:
        groups[(e.batch, e.section)].append(e)

    lines = []
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    for (batch, section), group in sorted(groups.items()):
        lines.append(f"\n📅 *{batch} Year — Section {section}*")
        # Sort by day then hour
        group.sort(
            key=lambda e: (
                day_order.index(e.time_slot.day),
                e.time_slot.start_hour,
            )
        )
        for e in group:
            kind = "🔬" if e.course.is_lab else "📚"
            instructor = e.course.instructor or "TBA"
            lines.append(
                f"  {kind} `{e.time_slot.label:<28}` "
                f"{e.course.name}\n"
                f"       👤 {instructor} → 🏫 {e.room.name}"
            )

    return "\n".join(lines)


# ── Curriculum ────────────────────────────────────────────────────────────────

def get_curriculum_semesters(session: Session) -> List[CurriculumSemester]:
    """Return all curriculum semesters ordered by year and semester."""
    return (
        session.query(CurriculumSemester)
        .order_by(CurriculumSemester.year, CurriculumSemester.semester)
        .all()
    )


def get_curriculum_courses(
    session: Session,
    year: Optional[int] = None,
    semester: Optional[int] = None,
) -> List[CurriculumCourse]:
    """
    Return curriculum courses, optionally filtered by year and/or semester number.
    Joins to CurriculumSemester for filtering.
    """
    q = session.query(CurriculumCourse).join(CurriculumCourse.semester_obj)
    if year is not None:
        q = q.filter(CurriculumSemester.year == year)
    if semester is not None:
        q = q.filter(CurriculumSemester.semester == semester)
    return q.order_by(CurriculumSemester.year, CurriculumSemester.semester).all()


def search_curriculum(session: Session, query: str) -> List[CurriculumCourse]:
    """Case-insensitive search across course code, title, and full_name."""
    pattern = f"%{query.lower()}%"
    return (
        session.query(CurriculumCourse)
        .filter(
            CurriculumCourse.title.ilike(pattern)
            | CurriculumCourse.full_name.ilike(pattern)
            | CurriculumCourse.code.ilike(pattern)
        )
        .join(CurriculumCourse.semester_obj)
        .order_by(CurriculumSemester.year, CurriculumSemester.semester)
        .all()
    )


def format_curriculum_text(courses: List[CurriculumCourse]) -> str:
    """Format a list of curriculum courses for Telegram display."""
    if not courses:
        return "_No courses found._"

    lines = []
    current_sem = None
    for c in courses:
        sem_label = c.semester_obj.label if c.semester_obj else "Unknown"
        if sem_label != current_sem:
            current_sem = sem_label
            status = f" _(placeholder)_" if c.semester_obj and c.semester_obj.status else ""
            lines.append(f"\n📚 *{sem_label}*{status}")

        cr = f"{c.credits}({c.credit_hours})" if c.credits else "TBD"
        name = c.full_name or c.title
        note = f" _{c.note}_" if c.note else ""
        lines.append(f"  `{c.code:<12}` {name}  [{cr}]{note}")

    return "\n".join(lines)
