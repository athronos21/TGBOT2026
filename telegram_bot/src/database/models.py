from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey, UniqueConstraint, CheckConstraint, BigInteger
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ── Admin Profile ─────────────────────────────────────────────────────────────

class AdminProfile(Base):
    """
    Stores the department chosen by each admin (keyed by Telegram user ID).
    One row per admin. Department can be changed at any time via /switch_department.
    """
    __tablename__ = "admin_profiles"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id    = Column(BigInteger, nullable=False, unique=True)
    department     = Column(String(120), nullable=False)
    full_name      = Column(String(120), nullable=True)   # Telegram display name, stored for reference

    def __repr__(self) -> str:
        return f"<AdminProfile tg={self.telegram_id} dept={self.department}>"


# ── Curriculum (seeded from curriculum.json) ──────────────────────────────────

class CurriculumSemester(Base):
    __tablename__ = "curriculum_semesters"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    year         = Column(Integer, nullable=False)       # 1, 2, 3, 4
    semester     = Column(Integer, nullable=False)       # 1 or 2
    label        = Column(String(50), nullable=False)    # "Year 1 Semester II"
    status       = Column(String(100), nullable=True)    # placeholder note if TBD

    __table_args__ = (
        UniqueConstraint("year", "semester", name="uq_curriculum_semester"),
    )

    courses = relationship(
        "CurriculumCourse", back_populates="semester_obj", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<CurriculumSemester {self.label}>"


class CurriculumCourse(Base):
    __tablename__ = "curriculum_courses"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    semester_id   = Column(Integer, ForeignKey("curriculum_semesters.id"), nullable=False)
    code          = Column(String(30), nullable=False)
    title         = Column(String(200), nullable=False)   # as listed in curriculum
    full_name     = Column(String(200), nullable=True)    # expanded full name
    credits       = Column(Integer, nullable=True)
    credit_hours  = Column(Integer, nullable=True)
    note          = Column(String(200), nullable=True)    # e.g. "elective (*)"

    semester_obj = relationship("CurriculumSemester", back_populates="courses")

    def __repr__(self) -> str:
        return f"<CurriculumCourse {self.code} — {self.title}>"


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    # Credit hours: min 1, max 4 — enforced at DB and application level
    credit_hours = Column(Integer, nullable=False)
    is_lab = Column(Boolean, default=False, nullable=False)
    batch = Column(String(10), nullable=False)        # "2nd" | "3rd" | "4th"
    semester = Column(Integer, nullable=False)        # 1 or 2
    # Instructor name — defaults to "TBA" until assigned
    instructor = Column(String(120), nullable=False, default="TBA", server_default="TBA")

    __table_args__ = (
        CheckConstraint("credit_hours >= 1 AND credit_hours <= 4", name="ck_credit_hours_range"),
    )

    schedule_entries = relationship(
        "ScheduleEntry", back_populates="course", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        kind = "Lab" if self.is_lab else "Class"
        return f"<Course {self.name} [{self.batch} yr | {self.credit_hours}cr | {kind} | {self.instructor}]>"


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(60), nullable=False, unique=True)
    room_type = Column(String(20), nullable=False)   # "classroom" | "lab"
    capacity = Column(Integer, nullable=True)

    schedule_entries = relationship(
        "ScheduleEntry", back_populates="room", cascade="all, delete-orphan"
    )
    batch_assignment = relationship(
        "LabBatchAssignment",
        back_populates="room",
        cascade="all, delete-orphan",
        uselist=False,   # one-to-one: each lab has at most one batch
    )

    def __repr__(self) -> str:
        return f"<Room {self.name} [{self.room_type}]>"


class LabBatchAssignment(Base):
    """
    One-to-one: each lab room is assigned to exactly ONE batch.
    Each batch can have exactly ONE lab.

    Enforced by:
      - UNIQUE(room_id)  → one lab cannot serve two batches
      - UNIQUE(batch)    → one batch cannot have two labs
    """
    __tablename__ = "lab_batch_assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    batch = Column(String(10), nullable=False)   # "2nd" | "3rd" | "4th"

    __table_args__ = (
        UniqueConstraint("room_id", name="uq_lab_one_batch"),   # lab → 1 batch
        UniqueConstraint("batch",   name="uq_batch_one_lab"),   # batch → 1 lab
    )

    room = relationship("Room", back_populates="batch_assignment")

    def __repr__(self) -> str:
        return f"<LabBatchAssignment lab={self.room_id} → batch={self.batch}>"


class TimeSlot(Base):
    __tablename__ = "time_slots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    day = Column(String(15), nullable=False)         # "Monday" … "Friday"
    start_hour = Column(Integer, nullable=False)     # 8 … 16
    end_hour = Column(Integer, nullable=False)       # 9 … 17

    __table_args__ = (
        UniqueConstraint("day", "start_hour", name="uq_timeslot"),
    )

    schedule_entries = relationship(
        "ScheduleEntry", back_populates="time_slot", cascade="all, delete-orphan"
    )

    @property
    def label(self) -> str:
        return f"{self.day} {self.start_hour:02d}:00–{self.end_hour:02d}:00"

    def __repr__(self) -> str:
        return f"<TimeSlot {self.label}>"


class ScheduleEntry(Base):
    __tablename__ = "schedule_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    time_slot_id = Column(Integer, ForeignKey("time_slots.id"), nullable=False)
    batch = Column(String(10), nullable=False)
    section = Column(String(5), nullable=False)      # "A" | "B"
    semester = Column(Integer, nullable=False)

    course = relationship("Course", back_populates="schedule_entries")
    room = relationship("Room", back_populates="schedule_entries")
    time_slot = relationship("TimeSlot", back_populates="schedule_entries")

    __table_args__ = (
        UniqueConstraint("room_id", "time_slot_id", name="uq_room_slot"),
        UniqueConstraint("batch", "section", "time_slot_id", name="uq_section_slot"),
    )

    def __repr__(self) -> str:
        return (
            f"<Entry {self.course.name if self.course else self.course_id} | "
            f"{self.batch}{self.section} | "
            f"{self.time_slot.label if self.time_slot else self.time_slot_id} | "
            f"{self.room.name if self.room else self.room_id}>"
        )
