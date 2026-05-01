"""
Tests for ORM models — table creation, constraints, relationships, repr.
"""
import pytest
from sqlalchemy.exc import IntegrityError

from src.database.models import (
    AdminProfile, Course, Room, LabBatchAssignment,
    TimeSlot, ScheduleEntry, CurriculumSemester, CurriculumCourse,
)


# ── AdminProfile ──────────────────────────────────────────────────────────────

class TestAdminProfile:
    def test_create(self, session):
        p = AdminProfile(telegram_id=111, department="IT", full_name="Alice")
        session.add(p)
        session.flush()
        assert p.id is not None
        assert p.department == "IT"

    def test_repr(self, session):
        p = AdminProfile(telegram_id=222, department="CS")
        session.add(p)
        session.flush()
        assert "222" in repr(p)
        assert "CS" in repr(p)

    def test_unique_telegram_id(self, session):
        session.add(AdminProfile(telegram_id=333, department="IT"))
        session.flush()
        session.add(AdminProfile(telegram_id=333, department="CS"))
        with pytest.raises(IntegrityError):
            session.flush()

    def test_department_required(self, session):
        session.add(AdminProfile(telegram_id=444, department=None))
        with pytest.raises(IntegrityError):
            session.flush()


# ── Course ────────────────────────────────────────────────────────────────────

class TestCourse:
    def _make(self, **kwargs):
        defaults = dict(
            name="Algorithms", credit_hours=3,
            is_lab=False, batch="2nd", semester=1, instructor="Dr. A"
        )
        defaults.update(kwargs)
        return Course(**defaults)

    def test_create(self, session):
        c = self._make()
        session.add(c)
        session.flush()
        assert c.id is not None

    def test_repr_class(self, session):
        c = self._make(is_lab=False)
        session.add(c)
        session.flush()
        assert "Class" in repr(c)

    def test_repr_lab(self, session):
        c = self._make(is_lab=True)
        session.add(c)
        session.flush()
        assert "Lab" in repr(c)

    def test_default_instructor(self, session):
        c = Course(name="Math", credit_hours=2, is_lab=False,
                   batch="3rd", semester=2)
        session.add(c)
        session.flush()
        # Python-level default applies
        assert c.instructor == "TBA"


# ── Room ──────────────────────────────────────────────────────────────────────

class TestRoom:
    def test_create_classroom(self, session):
        r = Room(name="Room-101", room_type="classroom", capacity=40)
        session.add(r)
        session.flush()
        assert r.id is not None

    def test_create_lab(self, session):
        r = Room(name="Lab-1", room_type="lab", capacity=30)
        session.add(r)
        session.flush()
        assert r.room_type == "lab"

    def test_unique_name(self, session):
        session.add(Room(name="Room-X", room_type="classroom"))
        session.flush()
        session.add(Room(name="Room-X", room_type="lab"))
        with pytest.raises(IntegrityError):
            session.flush()

    def test_repr(self, session):
        r = Room(name="Lab-2", room_type="lab")
        session.add(r)
        session.flush()
        assert "Lab-2" in repr(r)


# ── LabBatchAssignment ────────────────────────────────────────────────────────

class TestLabBatchAssignment:
    def _lab(self, session, name="Lab-A"):
        r = Room(name=name, room_type="lab")
        session.add(r)
        session.flush()
        return r

    def test_assign(self, session):
        lab = self._lab(session)
        a = LabBatchAssignment(room_id=lab.id, batch="2nd")
        session.add(a)
        session.flush()
        assert a.id is not None

    def test_one_lab_one_batch(self, session):
        """Same lab cannot be assigned to two different batches."""
        lab = self._lab(session)
        session.add(LabBatchAssignment(room_id=lab.id, batch="2nd"))
        session.flush()
        session.add(LabBatchAssignment(room_id=lab.id, batch="3rd"))
        with pytest.raises(IntegrityError):
            session.flush()

    def test_one_batch_one_lab(self, session):
        """Same batch cannot have two labs."""
        lab1 = self._lab(session, "Lab-B1")
        lab2 = self._lab(session, "Lab-B2")
        session.add(LabBatchAssignment(room_id=lab1.id, batch="4th"))
        session.flush()
        session.add(LabBatchAssignment(room_id=lab2.id, batch="4th"))
        with pytest.raises(IntegrityError):
            session.flush()

    def test_repr(self, session):
        lab = self._lab(session)
        a = LabBatchAssignment(room_id=lab.id, batch="3rd")
        session.add(a)
        session.flush()
        assert "3rd" in repr(a)


# ── TimeSlot ──────────────────────────────────────────────────────────────────

class TestTimeSlot:
    def test_create(self, session):
        ts = TimeSlot(day="Monday", start_hour=8, end_hour=9)
        session.add(ts)
        session.flush()
        assert ts.id is not None

    def test_label_property(self, session):
        ts = TimeSlot(day="Tuesday", start_hour=10, end_hour=11)
        session.add(ts)
        session.flush()
        assert ts.label == "Tuesday 10:00–11:00"

    def test_unique_day_hour(self, session):
        session.add(TimeSlot(day="Monday", start_hour=9, end_hour=10))
        session.flush()
        session.add(TimeSlot(day="Monday", start_hour=9, end_hour=10))
        with pytest.raises(IntegrityError):
            session.flush()


# ── CurriculumSemester / CurriculumCourse ─────────────────────────────────────

class TestCurriculum:
    def _sem(self, session, year=1, semester=2, label="Year 1 Sem II"):
        s = CurriculumSemester(year=year, semester=semester, label=label)
        session.add(s)
        session.flush()
        return s

    def test_create_semester(self, session):
        s = self._sem(session)
        assert s.id is not None

    def test_unique_year_semester(self, session):
        self._sem(session, year=2, semester=1, label="Y2S1")
        session.add(CurriculumSemester(year=2, semester=1, label="Y2S1-dup"))
        with pytest.raises(IntegrityError):
            session.flush()

    def test_create_course(self, session):
        s = self._sem(session)
        c = CurriculumCourse(
            semester_id=s.id, code="ITec1012",
            title="Basic Programming", full_name="Basic Computer Programming",
            credits=5, credit_hours=3,
        )
        session.add(c)
        session.flush()
        assert c.id is not None

    def test_course_repr(self, session):
        s = self._sem(session)
        c = CurriculumCourse(semester_id=s.id, code="CS101", title="Intro CS")
        session.add(c)
        session.flush()
        assert "CS101" in repr(c)

    def test_cascade_delete(self, session):
        s = self._sem(session)
        c = CurriculumCourse(semester_id=s.id, code="X", title="X")
        session.add(c)
        session.flush()
        cid = c.id
        session.delete(s)
        session.flush()
        assert session.get(CurriculumCourse, cid) is None
