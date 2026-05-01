"""
Greedy scheduling engine for Haramaya University IT Department.

Priority order:
  1. Lab courses (4th → 3rd → 2nd year)
  2. Classroom courses (4th → 3rd → 2nd year)

Fairness: morning/afternoon slots are balanced per section.

Lab assignment rule (strict 1-to-1):
  - Each lab is assigned to exactly ONE batch.
  - Each batch has exactly ONE lab.
  - A lab with NO assignment is NOT used by the scheduler
    (the head must assign every lab before generating).
"""
from typing import List, Optional, Tuple, Dict
from sqlalchemy.orm import Session

from src.database.models import Course, Room, LabBatchAssignment, TimeSlot, ScheduleEntry
from src.scheduler.constraints import ConstraintTracker
from src.config import SECTIONS, MORNING_CUTOFF


BATCH_PRIORITY = ["4th", "3rd", "2nd"]


def _sorted_slots(slots: List[TimeSlot], prefer_morning: bool) -> List[TimeSlot]:
    morning   = [s for s in slots if s.start_hour < MORNING_CUTOFF]
    afternoon = [s for s in slots if s.start_hour >= MORNING_CUTOFF]
    return (morning + afternoon) if prefer_morning else (afternoon + morning)


def _lab_for_batch(
    all_labs: List[Room],
    assignments: Dict[int, str],   # room_id → batch  (1-to-1)
    batch: str,
) -> Optional[Room]:
    """Return the single lab assigned to this batch, or None if not assigned."""
    for lab in all_labs:
        if assignments.get(lab.id) == batch:
            return lab
    return None


def _try_assign(
    course: Course,
    section: str,
    rooms: List[Room],
    slots: List[TimeSlot],
    tracker: ConstraintTracker,
    session: Session,
) -> Optional[ScheduleEntry]:
    prefer_morning = tracker.prefers_morning(course.batch, section)
    ordered_slots  = _sorted_slots(slots, prefer_morning)

    for slot in ordered_slots:
        for room in rooms:
            if tracker.can_assign(room.id, course.batch, section, slot.id):
                entry = ScheduleEntry(
                    course_id=course.id,
                    room_id=room.id,
                    time_slot_id=slot.id,
                    batch=course.batch,
                    section=section,
                    semester=course.semester,
                )
                session.add(entry)
                tracker.book(room.id, course.batch, section, slot.id, slot.start_hour)
                return entry
    return None


def generate_schedule(session: Session) -> Tuple[int, List[str]]:
    """
    Generate a full schedule for all courses in the database.
    Returns (assigned_count, list_of_unassigned_descriptions).
    """
    all_courses: List[Course]   = session.query(Course).all()
    all_rooms:   List[Room]     = session.query(Room).all()
    all_slots:   List[TimeSlot] = (
        session.query(TimeSlot)
        .order_by(TimeSlot.day, TimeSlot.start_hour)
        .all()
    )

    all_labs   = [r for r in all_rooms if r.room_type == "lab"]
    classrooms = [r for r in all_rooms if r.room_type == "classroom"]

    # Build 1-to-1 map: room_id → batch
    assignment_rows = session.query(LabBatchAssignment).all()
    lab_assignments: Dict[int, str] = {row.room_id: row.batch for row in assignment_rows}

    lab_courses   = [c for c in all_courses if c.is_lab]
    class_courses = [c for c in all_courses if not c.is_lab]

    def batch_key(c: Course) -> int:
        try:
            return BATCH_PRIORITY.index(c.batch)
        except ValueError:
            return 99

    lab_courses.sort(key=batch_key)
    class_courses.sort(key=batch_key)

    tracker    = ConstraintTracker()
    assigned   = 0
    unassigned: List[str] = []

    # ── Schedule lab courses ──────────────────────────────────────────────────
    for course in lab_courses:
        lab = _lab_for_batch(all_labs, lab_assignments, course.batch)

        if lab is None:
            # No lab assigned to this batch — skip all sessions
            for section in SECTIONS:
                for session_num in range(1, course.credit_hours + 1):
                    unassigned.append(
                        f"{course.name} ({course.batch} yr, Sec {section},"
                        f" session {session_num}/{course.credit_hours})"
                        f" — ⚠️ no lab assigned to {course.batch} Year"
                    )
            continue

        for section in SECTIONS:
            for session_num in range(1, course.credit_hours + 1):
                entry = _try_assign(
                    course, section, [lab], all_slots, tracker, session
                )
                if entry:
                    assigned += 1
                else:
                    unassigned.append(
                        f"{course.name} ({course.batch} yr, Sec {section},"
                        f" session {session_num}/{course.credit_hours})"
                        f" — lab {lab.name} fully booked"
                    )

    # ── Schedule classroom courses ────────────────────────────────────────────
    for course in class_courses:
        for section in SECTIONS:
            for session_num in range(1, course.credit_hours + 1):
                entry = _try_assign(
                    course, section, classrooms, all_slots, tracker, session
                )
                if entry:
                    assigned += 1
                else:
                    unassigned.append(
                        f"{course.name} ({course.batch} yr, Sec {section},"
                        f" session {session_num}/{course.credit_hours})"
                    )

    return assigned, unassigned
