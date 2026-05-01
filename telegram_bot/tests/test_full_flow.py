"""
Full end-to-end flow test against in-memory SQLite.
Tests every major user journey in sequence.
"""
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, CurriculumSemester, CurriculumCourse
import src.database.db as _db_module
from src.bot.commands import (
    get_admin_profile, set_admin_department,
    add_course, list_courses, delete_course, update_instructor,
    add_room, list_rooms, list_labs, delete_room,
    assign_lab_to_batch, remove_lab_assignment, get_lab_batch_assignments,
    seed_time_slots, get_schedule, clear_schedule, format_schedule_text,
    get_curriculum_courses, search_curriculum, format_curriculum_text,
)
from src.scheduler.engine import generate_schedule


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:", echo=False)

    @event.listens_for(eng, "connect")
    def fk(dbapi_conn, _):
        dbapi_conn.cursor().execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(eng)
    _db_module.engine = eng
    _db_module.SessionLocal = sessionmaker(bind=eng, autocommit=False, autoflush=False)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()
    _db_module.engine = None
    _db_module.SessionLocal = None


@pytest.fixture(scope="module")
def sess(engine):
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


@pytest.fixture(scope="module", autouse=True)
def seed_curriculum(sess):
    """Seed curriculum data once for the module."""
    s1 = CurriculumSemester(year=1, semester=2, label="Year 1 Semester II")
    s2 = CurriculumSemester(year=2, semester=1, label="Year 2 Semester I")
    sess.add_all([s1, s2])
    sess.flush()
    sess.add(CurriculumCourse(
        semester_id=s1.id, code="ITec1012",
        title="Basic Computer Programming",
        full_name="Basic Computer Programming",
        credits=5, credit_hours=3,
    ))
    sess.add(CurriculumCourse(
        semester_id=s1.id, code="Math1012",
        title="Applied Mathematics",
        full_name="Applied Mathematics",
        credits=5, credit_hours=3,
    ))
    sess.add(CurriculumCourse(
        semester_id=s2.id, code="Stat2171",
        title="Introduction to Statistics",
        full_name="Introduction to Statistics",
        credits=5, credit_hours=3,
    ))
    sess.commit()


# ── Flow 1: Department setup ──────────────────────────────────────────────────

class TestDepartmentFlow:
    def test_no_profile_initially(self, sess):
        assert get_admin_profile(sess, 9999) is None

    def test_set_department(self, sess):
        p = set_admin_department(sess, 9999, "Information Technology", "Test User")
        sess.commit()
        assert p.department == "Information Technology"

    def test_get_profile_after_set(self, sess):
        p = get_admin_profile(sess, 9999)
        assert p is not None
        assert p.department == "Information Technology"
        assert p.full_name == "Test User"

    def test_switch_department(self, sess):
        set_admin_department(sess, 9999, "Computer Science")
        sess.commit()
        p = get_admin_profile(sess, 9999)
        assert p.department == "Computer Science"


# ── Flow 2: Add courses ───────────────────────────────────────────────────────

class TestAddCoursesFlow:
    def test_add_class_course(self, sess):
        c = add_course(sess, "Operating Systems", 3, False, "2nd", 1, "Dr. Smith")
        sess.commit()
        assert c.id is not None
        assert c.instructor == "Dr. Smith"

    def test_add_lab_course(self, sess):
        c = add_course(sess, "Internet Programming I", 3, True, "2nd", 1, "TBA")
        sess.commit()
        assert c.is_lab is True

    def test_add_multiple_batches(self, sess):
        add_course(sess, "Data Structures", 3, False, "3rd", 1)
        add_course(sess, "Advanced DB", 3, True, "4th", 2)
        sess.commit()
        courses = list_courses(sess)
        batches = {c.batch for c in courses}
        assert "2nd" in batches
        assert "3rd" in batches
        assert "4th" in batches

    def test_credit_hours_validation(self, sess):
        with pytest.raises(ValueError):
            add_course(sess, "Bad Course", 0, False, "2nd", 1)
        with pytest.raises(ValueError):
            add_course(sess, "Bad Course", 5, False, "2nd", 1)

    def test_update_instructor(self, sess):
        courses = list_courses(sess)
        c = courses[0]
        update_instructor(sess, c.id, "Prof. Updated")
        sess.commit()
        sess.refresh(c)
        assert c.instructor == "Prof. Updated"

    def test_list_courses_not_empty(self, sess):
        assert len(list_courses(sess)) >= 4


# ── Flow 3: Rooms and labs ────────────────────────────────────────────────────

class TestRoomsFlow:
    def test_add_classrooms(self, sess):
        add_room(sess, "Room-101", "classroom", 40)
        add_room(sess, "Room-102", "classroom", 35)
        sess.commit()
        rooms = [r for r in list_rooms(sess) if r.room_type == "classroom"]
        assert len(rooms) >= 2

    def test_add_labs(self, sess):
        add_room(sess, "Lab-1", "lab", 30)
        add_room(sess, "Lab-2", "lab", 30)
        add_room(sess, "Lab-3", "lab", 30)
        sess.commit()
        labs = list_labs(sess)
        assert len(labs) >= 3

    def test_list_labs_only(self, sess):
        labs = list_labs(sess)
        assert all(r.room_type == "lab" for r in labs)


# ── Flow 4: Lab assignments ───────────────────────────────────────────────────

class TestLabAssignmentFlow:
    def test_assign_each_batch_a_lab(self, sess):
        labs = list_labs(sess)
        assert len(labs) >= 3
        ok1, _ = assign_lab_to_batch(sess, labs[0].id, "2nd")
        ok2, _ = assign_lab_to_batch(sess, labs[1].id, "3rd")
        ok3, _ = assign_lab_to_batch(sess, labs[2].id, "4th")
        sess.commit()
        assert ok1 and ok2 and ok3

    def test_cannot_assign_same_lab_twice(self, sess):
        labs = list_labs(sess)
        ok, err = assign_lab_to_batch(sess, labs[0].id, "3rd")
        assert ok is False
        assert err is not None

    def test_cannot_assign_two_labs_to_same_batch(self, sess):
        labs = list_labs(sess)
        ok, err = assign_lab_to_batch(sess, labs[1].id, "2nd")
        assert ok is False

    def test_get_assignments_all_batches(self, sess):
        d = get_lab_batch_assignments(sess)
        assert "2nd" in d.values()
        assert "3rd" in d.values()
        assert "4th" in d.values()


# ── Flow 5: Time slots ────────────────────────────────────────────────────────

class TestTimeSlotsFlow:
    def test_seed_45_slots(self, sess):
        added = seed_time_slots(sess)
        sess.commit()
        assert added == 45

    def test_seed_idempotent(self, sess):
        added = seed_time_slots(sess)
        assert added == 0


# ── Flow 6: Schedule generation ──────────────────────────────────────────────

class TestScheduleFlow:
    def test_generate_schedule(self, sess):
        assigned, unassigned = generate_schedule(sess)
        sess.commit()
        assert assigned > 0

    def test_no_room_conflicts(self, sess):
        entries = get_schedule(sess)
        pairs = [(e.room_id, e.time_slot_id) for e in entries]
        assert len(pairs) == len(set(pairs)), "Room conflict detected!"

    def test_no_section_conflicts(self, sess):
        from collections import defaultdict
        entries = get_schedule(sess)
        by_section = defaultdict(list)
        for e in entries:
            by_section[(e.batch, e.section)].append(e.time_slot_id)
        for key, slots in by_section.items():
            assert len(slots) == len(set(slots)), f"Section conflict in {key}"

    def test_filter_by_batch(self, sess):
        entries = get_schedule(sess, batch="2nd")
        assert all(e.batch == "2nd" for e in entries)

    def test_filter_by_section(self, sess):
        entries = get_schedule(sess, section="A")
        assert all(e.section == "A" for e in entries)

    def test_format_schedule_text(self, sess):
        entries = get_schedule(sess)
        text = format_schedule_text(entries)
        assert "Year" in text or "2nd" in text

    def test_clear_and_regenerate(self, sess):
        count_before = len(get_schedule(sess))
        clear_schedule(sess)
        generate_schedule(sess)
        sess.commit()
        count_after = len(get_schedule(sess))
        assert count_before == count_after


# ── Flow 7: Curriculum ────────────────────────────────────────────────────────

class TestCurriculumFlow:
    def test_get_all(self, sess):
        courses = get_curriculum_courses(sess)
        assert len(courses) == 3

    def test_filter_year_1(self, sess):
        courses = get_curriculum_courses(sess, year=1)
        assert len(courses) == 2
        assert all(c.semester_obj.year == 1 for c in courses)

    def test_filter_year_2_sem_1(self, sess):
        courses = get_curriculum_courses(sess, year=2, semester=1)
        assert len(courses) == 1
        assert courses[0].code == "Stat2171"

    def test_search_by_title(self, sess):
        results = search_curriculum(sess, "programming")
        assert len(results) == 1
        assert results[0].code == "ITec1012"

    def test_search_case_insensitive(self, sess):
        results = search_curriculum(sess, "MATHEMATICS")
        assert len(results) == 1

    def test_search_no_results(self, sess):
        assert search_curriculum(sess, "xyznotfound") == []

    def test_format_text(self, sess):
        courses = get_curriculum_courses(sess)
        text = format_curriculum_text(courses)
        assert "ITec1012" in text
        assert "Year 1 Semester II" in text


# ── Flow 8: Delete operations ─────────────────────────────────────────────────

class TestDeleteFlow:
    def test_delete_course(self, sess):
        c = add_course(sess, "Temp Course", 2, False, "2nd", 1)
        sess.commit()
        cid = c.id
        assert delete_course(sess, cid) is True
        sess.commit()
        assert sess.get(type(c), cid) is None

    def test_delete_nonexistent_course(self, sess):
        assert delete_course(sess, 99999) is False

    def test_delete_room(self, sess):
        r = add_room(sess, "Temp-Room", "classroom", 20)
        sess.commit()
        rid = r.id
        assert delete_room(sess, rid) is True
        sess.commit()

    def test_delete_nonexistent_room(self, sess):
        assert delete_room(sess, 99999) is False

    def test_remove_lab_assignment(self, sess):
        labs = list_labs(sess)
        # Remove first lab's assignment
        ok = remove_lab_assignment(sess, labs[0].id)
        sess.commit()
        assert ok is True

    def test_remove_nonexistent_assignment(self, sess):
        labs = list_labs(sess)
        # labs[0] was just unassigned above
        assert remove_lab_assignment(sess, labs[0].id) is False
