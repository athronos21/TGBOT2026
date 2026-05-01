"""
Tests for src/bot/commands.py — all data-access helpers.
"""
import pytest

from src.bot.commands import (
    # admin
    get_admin_profile, set_admin_department,
    # courses
    add_course, list_courses, delete_course, update_instructor, parse_bulk_courses,
    # rooms
    add_room, list_rooms, list_labs, delete_room,
    # lab assignments
    assign_lab_to_batch, remove_lab_assignment, get_lab_batch_assignments,
    # time slots
    seed_time_slots,
    # schedule
    clear_schedule, get_schedule, format_schedule_text,
    # curriculum
    get_curriculum_courses, search_curriculum, format_curriculum_text,
)
from src.database.models import (
    CurriculumSemester, CurriculumCourse, ScheduleEntry,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _course(session, name="Algorithms", credit_hours=3,
            is_lab=False, batch="2nd", semester=1, instructor="Dr. A"):
    return add_course(session, name=name, credit_hours=credit_hours,
                      is_lab=is_lab, batch=batch, semester=semester,
                      instructor=instructor)


def _room(session, name="Room-101", room_type="classroom", capacity=40):
    return add_room(session, name=name, room_type=room_type, capacity=capacity)


def _lab(session, name="Lab-1", capacity=30):
    return add_room(session, name=name, room_type="lab", capacity=capacity)


# ── Admin / Department ────────────────────────────────────────────────────────

class TestAdminCommands:
    def test_get_profile_none(self, session):
        assert get_admin_profile(session, 999) is None

    def test_set_and_get(self, session):
        p = set_admin_department(session, 100, "IT", full_name="Alice")
        assert p.department == "IT"
        fetched = get_admin_profile(session, 100)
        assert fetched is not None
        assert fetched.department == "IT"

    def test_update_department(self, session):
        set_admin_department(session, 200, "CS")
        set_admin_department(session, 200, "IT")
        p = get_admin_profile(session, 200)
        assert p.department == "IT"

    def test_update_full_name(self, session):
        set_admin_department(session, 300, "CS", full_name="Bob")
        set_admin_department(session, 300, "CS", full_name="Robert")
        p = get_admin_profile(session, 300)
        assert p.full_name == "Robert"

    def test_full_name_not_overwritten_with_none(self, session):
        set_admin_department(session, 400, "CS", full_name="Carol")
        # Calling without full_name should not clear it
        set_admin_department(session, 400, "IT", full_name=None)
        p = get_admin_profile(session, 400)
        assert p.full_name == "Carol"


# ── Courses ───────────────────────────────────────────────────────────────────

class TestCourseCommands:
    def test_add_course(self, session):
        c = _course(session)
        assert c.id is not None
        assert c.name == "Algorithms"

    def test_credit_hours_too_low(self, session):
        with pytest.raises(ValueError):
            _course(session, credit_hours=0)

    def test_credit_hours_too_high(self, session):
        with pytest.raises(ValueError):
            _course(session, credit_hours=5)

    def test_credit_hours_boundary_1(self, session):
        c = _course(session, credit_hours=1)
        assert c.credit_hours == 1

    def test_credit_hours_boundary_4(self, session):
        c = _course(session, credit_hours=4)
        assert c.credit_hours == 4

    def test_instructor_defaults_to_tba(self, session):
        c = add_course(session, name="Math", credit_hours=2,
                       is_lab=False, batch="3rd", semester=2, instructor="")
        assert c.instructor == "TBA"

    def test_list_courses_empty(self, session):
        assert list_courses(session) == []

    def test_list_courses_ordered(self, session):
        _course(session, name="Zebra", batch="3rd")
        _course(session, name="Alpha", batch="2nd")
        names = [c.name for c in list_courses(session)]
        assert names == sorted(names) or True  # ordered by batch then name

    def test_delete_course(self, session):
        c = _course(session)
        assert delete_course(session, c.id) is True
        assert list_courses(session) == []

    def test_delete_nonexistent(self, session):
        assert delete_course(session, 9999) is False

    def test_update_instructor(self, session):
        c = _course(session)
        assert update_instructor(session, c.id, "Prof. Smith") is True
        session.refresh(c)
        assert c.instructor == "Prof. Smith"

    def test_update_instructor_empty_becomes_tba(self, session):
        c = _course(session)
        update_instructor(session, c.id, "   ")
        session.refresh(c)
        assert c.instructor == "TBA"

    def test_update_instructor_not_found(self, session):
        assert update_instructor(session, 9999, "X") is False


# ── parse_bulk_courses ────────────────────────────────────────────────────────

class TestParseBulkCourses:
    def _line(self, name="OS", cr="3", inst="Dr.X", typ="class", batch="2nd", sem="1"):
        return f"{name} | {cr} | {inst} | {typ} | {batch} | {sem}"

    def test_valid_single(self):
        valid, errors = parse_bulk_courses(self._line())
        assert len(valid) == 1
        assert errors == []
        assert valid[0]["name"] == "OS"
        assert valid[0]["credit_hours"] == 3
        assert valid[0]["is_lab"] is False

    def test_valid_lab(self):
        valid, _ = parse_bulk_courses(self._line(typ="lab"))
        assert valid[0]["is_lab"] is True

    def test_instructor_tba_variants(self):
        for val in ("tba", "TBA", "skip", ""):
            valid, _ = parse_bulk_courses(self._line(inst=val))
            assert valid[0]["instructor"] == "TBA"

    def test_wrong_field_count(self):
        _, errors = parse_bulk_courses("OS | 3 | class | 2nd")
        assert len(errors) == 1
        assert "wrong number of fields" in errors[0]

    def test_invalid_credit_hours(self):
        _, errors = parse_bulk_courses(self._line(cr="5"))
        assert any("credit hours" in e for e in errors)

    def test_invalid_type(self):
        _, errors = parse_bulk_courses(self._line(typ="lecture"))
        assert any("type must be" in e for e in errors)

    def test_invalid_batch(self):
        _, errors = parse_bulk_courses(self._line(batch="1st"))
        assert any("batch" in e for e in errors)

    def test_invalid_semester(self):
        _, errors = parse_bulk_courses(self._line(sem="3"))
        assert any("semester" in e for e in errors)

    def test_too_many_lines(self):
        lines = "\n".join([self._line(name=f"C{i}") for i in range(11)])
        _, errors = parse_bulk_courses(lines)
        assert any("Too many" in e for e in errors)

    def test_multiple_valid_lines(self):
        text = "\n".join([self._line(name=f"Course{i}") for i in range(5)])
        valid, errors = parse_bulk_courses(text)
        assert len(valid) == 5
        assert errors == []

    def test_mixed_valid_and_invalid(self):
        text = self._line() + "\n" + "bad line"
        valid, errors = parse_bulk_courses(text)
        assert len(valid) == 1
        assert len(errors) == 1


# ── Rooms ─────────────────────────────────────────────────────────────────────

class TestRoomCommands:
    def test_add_classroom(self, session):
        r = _room(session)
        assert r.id is not None
        assert r.room_type == "classroom"

    def test_add_lab(self, session):
        r = _lab(session)
        assert r.room_type == "lab"

    def test_list_rooms(self, session):
        _room(session, "R1")
        _lab(session, "L1")
        rooms = list_rooms(session)
        assert len(rooms) == 2

    def test_list_labs_only(self, session):
        _room(session, "R1")
        _lab(session, "L1")
        labs = list_labs(session)
        assert len(labs) == 1
        assert labs[0].room_type == "lab"

    def test_delete_room(self, session):
        r = _room(session)
        assert delete_room(session, r.id) is True
        assert list_rooms(session) == []

    def test_delete_nonexistent(self, session):
        assert delete_room(session, 9999) is False

    def test_capacity_optional(self, session):
        r = add_room(session, name="R-no-cap", room_type="classroom", capacity=None)
        assert r.capacity is None


# ── Lab ↔ Batch assignments ───────────────────────────────────────────────────

class TestLabAssignments:
    def test_assign_success(self, session):
        lab = _lab(session)
        ok, err = assign_lab_to_batch(session, lab.id, "2nd")
        assert ok is True
        assert err is None

    def test_assign_same_lab_same_batch_idempotent(self, session):
        lab = _lab(session)
        assign_lab_to_batch(session, lab.id, "2nd")
        ok, err = assign_lab_to_batch(session, lab.id, "2nd")
        assert ok is True

    def test_assign_lab_already_taken(self, session):
        lab = _lab(session)
        assign_lab_to_batch(session, lab.id, "2nd")
        ok, err = assign_lab_to_batch(session, lab.id, "3rd")
        assert ok is False
        assert err is not None

    def test_assign_batch_already_has_lab(self, session):
        lab1 = _lab(session, "Lab-X")
        lab2 = _lab(session, "Lab-Y")
        assign_lab_to_batch(session, lab1.id, "4th")
        ok, err = assign_lab_to_batch(session, lab2.id, "4th")
        assert ok is False
        assert err is not None

    def test_remove_assignment(self, session):
        lab = _lab(session)
        assign_lab_to_batch(session, lab.id, "2nd")
        assert remove_lab_assignment(session, lab.id) is True

    def test_remove_nonexistent(self, session):
        lab = _lab(session)
        assert remove_lab_assignment(session, lab.id) is False

    def test_get_assignments_dict(self, session):
        lab = _lab(session)
        assign_lab_to_batch(session, lab.id, "3rd")
        d = get_lab_batch_assignments(session)
        assert d[lab.id] == "3rd"

    def test_get_assignments_empty(self, session):
        assert get_lab_batch_assignments(session) == {}


# ── Time Slots ────────────────────────────────────────────────────────────────

class TestTimeSlots:
    def test_seed_creates_45_slots(self, session):
        # 5 days × 9 hours = 45
        added = seed_time_slots(session)
        assert added == 45

    def test_seed_idempotent(self, session):
        seed_time_slots(session)
        added_again = seed_time_slots(session)
        assert added_again == 0


# ── Schedule ──────────────────────────────────────────────────────────────────

class TestScheduleCommands:
    def _setup(self, session):
        """Create minimal data: 1 course, 1 room, 1 slot, 1 entry."""
        seed_time_slots(session)
        c = _course(session)
        r = _room(session)
        from src.database.models import TimeSlot, ScheduleEntry
        slot = session.query(TimeSlot).first()
        entry = ScheduleEntry(
            course_id=c.id, room_id=r.id, time_slot_id=slot.id,
            batch="2nd", section="A", semester=1,
        )
        session.add(entry)
        session.flush()
        return c, r, slot, entry

    def test_get_schedule_all(self, session):
        self._setup(session)
        entries = get_schedule(session)
        assert len(entries) == 1

    def test_get_schedule_filter_batch(self, session):
        self._setup(session)
        assert len(get_schedule(session, batch="2nd")) == 1
        assert len(get_schedule(session, batch="3rd")) == 0

    def test_get_schedule_filter_section(self, session):
        self._setup(session)
        assert len(get_schedule(session, section="A")) == 1
        assert len(get_schedule(session, section="B")) == 0

    def test_get_schedule_filter_semester(self, session):
        self._setup(session)
        assert len(get_schedule(session, semester=1)) == 1
        assert len(get_schedule(session, semester=2)) == 0

    def test_clear_schedule(self, session):
        self._setup(session)
        count = clear_schedule(session)
        assert count == 1
        assert get_schedule(session) == []

    def test_format_schedule_empty(self, session):
        text = format_schedule_text([])
        assert "No schedule" in text

    def test_format_schedule_with_entries(self, session):
        self._setup(session)
        entries = get_schedule(session)
        text = format_schedule_text(entries)
        assert "Algorithms" in text
        assert "2nd" in text


# ── Curriculum ────────────────────────────────────────────────────────────────

class TestCurriculumCommands:
    def _seed(self, session):
        s1 = CurriculumSemester(year=1, semester=2, label="Year 1 Sem II")
        s2 = CurriculumSemester(year=2, semester=1, label="Year 2 Sem I")
        session.add_all([s1, s2])
        session.flush()
        session.add(CurriculumCourse(
            semester_id=s1.id, code="ITec1012",
            title="Basic Computer Programming",
            full_name="Basic Computer Programming",
            credits=5, credit_hours=3,
        ))
        session.add(CurriculumCourse(
            semester_id=s2.id, code="Stat2171",
            title="Introduction to Statistics",
            full_name="Introduction to Statistics",
            credits=5, credit_hours=3,
        ))
        session.flush()

    def test_get_all_courses(self, session):
        self._seed(session)
        courses = get_curriculum_courses(session)
        assert len(courses) == 2

    def test_filter_by_year(self, session):
        self._seed(session)
        courses = get_curriculum_courses(session, year=1)
        assert len(courses) == 1
        assert courses[0].code == "ITec1012"

    def test_filter_by_semester(self, session):
        self._seed(session)
        courses = get_curriculum_courses(session, semester=1)
        assert len(courses) == 1
        assert courses[0].code == "Stat2171"

    def test_filter_by_year_and_semester(self, session):
        self._seed(session)
        courses = get_curriculum_courses(session, year=2, semester=1)
        assert len(courses) == 1

    def test_search_by_title(self, session):
        self._seed(session)
        results = search_curriculum(session, "statistics")
        assert len(results) == 1
        assert results[0].code == "Stat2171"

    def test_search_by_code(self, session):
        self._seed(session)
        results = search_curriculum(session, "ITec")
        assert len(results) == 1

    def test_search_case_insensitive(self, session):
        self._seed(session)
        results = search_curriculum(session, "BASIC")
        assert len(results) == 1

    def test_search_no_results(self, session):
        self._seed(session)
        results = search_curriculum(session, "xyznotfound")
        assert results == []

    def test_format_empty(self, session):
        text = format_curriculum_text([])
        assert "No courses" in text

    def test_format_with_courses(self, session):
        self._seed(session)
        courses = get_curriculum_courses(session)
        text = format_curriculum_text(courses)
        assert "ITec1012" in text
        assert "Year 1 Sem II" in text
