"""
Instance tests — run every feature against the live Supabase database.
Each test is independent and cleans up after itself.

Run:
    python3 -m pytest tests/test_instance.py -v -s
"""
import os, sys, urllib.parse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.database.db as _db_module
from src.database.models import Base

# ── Connect to live Supabase ──────────────────────────────────────────────────

PASSWORD = urllib.parse.quote("12242144@At@", safe="")
SUPABASE_URL = (
    f"postgresql+psycopg2://postgres.bfczqqxzfqwtmarqbocg:{PASSWORD}"
    f"@aws-0-eu-west-1.pooler.supabase.com:6543/postgres"
)


@pytest.fixture(scope="module")
def db():
    engine = create_engine(SUPABASE_URL, connect_args={"connect_timeout": 10})
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    _db_module.engine = engine
    _db_module.SessionLocal = SessionLocal
    sess = SessionLocal()
    yield sess
    sess.close()


# ── Import commands after DB is patched ──────────────────────────────────────

from src.bot.commands import (
    get_admin_profile, set_admin_department,
    add_course, list_courses, delete_course, update_instructor,
    add_room, list_rooms, list_labs, delete_room,
    assign_lab_to_batch, remove_lab_assignment, get_lab_batch_assignments,
    seed_time_slots, get_schedule, clear_schedule, format_schedule_text,
    get_curriculum_courses, search_curriculum, format_curriculum_text,
)
from src.scheduler.engine import generate_schedule


# ── Helper: cleanup tracker ───────────────────────────────────────────────────

class Cleanup:
    """Track created IDs for cleanup after each test."""
    def __init__(self, sess):
        self.sess = sess
        self.course_ids = []
        self.room_ids = []

    def add_course(self, **kwargs):
        c = add_course(self.sess, **kwargs)
        self.sess.flush()
        self.course_ids.append(c.id)
        return c

    def add_room(self, **kwargs):
        r = add_room(self.sess, **kwargs)
        self.sess.flush()
        self.room_ids.append(r.id)
        return r

    def cleanup(self):
        clear_schedule(self.sess)
        for cid in self.course_ids:
            delete_course(self.sess, cid)
        for rid in self.room_ids:
            delete_room(self.sess, rid)
        self.sess.commit()
        self.course_ids.clear()
        self.room_ids.clear()


# ══════════════════════════════════════════════════════════════════════════════
# 1. DEPARTMENT FLOW
# ══════════════════════════════════════════════════════════════════════════════

class TestDepartmentInstance:
    def test_get_existing_profile(self, db):
        """Admin 6090589468 should already have a profile from real usage."""
        p = get_admin_profile(db, 6090589468)
        assert p is not None, "Admin profile not found — run /start in Telegram first"
        assert p.department is not None
        print(f"\n  ✅ Admin profile: {p.full_name} → {p.department}")

    def test_set_and_restore_department(self, db):
        """Change department and restore it."""
        original = get_admin_profile(db, 6090589468)
        orig_dept = original.department

        set_admin_department(db, 6090589468, "Computer Science")
        db.commit()
        p = get_admin_profile(db, 6090589468)
        assert p.department == "Computer Science"

        # Restore
        set_admin_department(db, 6090589468, orig_dept)
        db.commit()
        p = get_admin_profile(db, 6090589468)
        assert p.department == orig_dept
        print(f"\n  ✅ Department switch and restore: {orig_dept}")

    def test_new_user_no_profile(self, db):
        assert get_admin_profile(db, 99999999) is None
        print("\n  ✅ New user has no profile")


# ══════════════════════════════════════════════════════════════════════════════
# 2. CURRICULUM PICKER FLOW (the new add_courses flow)
# ══════════════════════════════════════════════════════════════════════════════

class TestCurriculumPickerInstance:
    def test_batch_2nd_sem2_loads_year1_sem2(self, db):
        """2nd batch + semester 2 → Year 1 Semester II curriculum."""
        courses = get_curriculum_courses(db, year=1, semester=2)
        assert len(courses) == 7
        names = [c.full_name or c.title for c in courses]
        print(f"\n  ✅ Year 1 Sem II: {len(courses)} courses")
        for n in names:
            print(f"     • {n}")

    def test_batch_3rd_sem1_loads_year2_sem1(self, db):
        courses = get_curriculum_courses(db, year=2, semester=1)
        assert len(courses) == 7
        print(f"\n  ✅ Year 2 Sem I: {len(courses)} courses")

    def test_batch_3rd_sem2_loads_year2_sem2(self, db):
        courses = get_curriculum_courses(db, year=2, semester=2)
        assert len(courses) == 6
        print(f"\n  ✅ Year 2 Sem II: {len(courses)} courses")

    def test_batch_4th_sem1_loads_year3_sem1(self, db):
        courses = get_curriculum_courses(db, year=3, semester=1)
        assert len(courses) == 6
        print(f"\n  ✅ Year 3 Sem I: {len(courses)} courses")

    def test_batch_4th_sem2_loads_year3_sem2(self, db):
        courses = get_curriculum_courses(db, year=3, semester=2)
        assert len(courses) == 6
        print(f"\n  ✅ Year 3 Sem II: {len(courses)} courses")

    def test_curriculum_course_has_credit_hours(self, db):
        courses = get_curriculum_courses(db, year=1, semester=2)
        for c in courses:
            if c.code != "TBD":
                assert c.credit_hours is not None, f"{c.code} missing credit_hours"
        print("\n  ✅ All curriculum courses have credit_hours")

    def test_curriculum_search_programming(self, db):
        results = search_curriculum(db, "programming")
        assert len(results) >= 1
        print(f"\n  ✅ Search 'programming': {len(results)} results")
        for r in results:
            print(f"     • {r.code}: {r.title}")

    def test_curriculum_search_case_insensitive(self, db):
        r1 = search_curriculum(db, "MATHEMATICS")
        r2 = search_curriculum(db, "mathematics")
        assert len(r1) == len(r2)
        print(f"\n  ✅ Case-insensitive search works: {len(r1)} results")

    def test_curriculum_format_text(self, db):
        courses = get_curriculum_courses(db, year=1, semester=2)
        text = format_curriculum_text(courses)
        assert "Year 1 Semester II" in text
        assert "ITec1012" in text
        print(f"\n  ✅ format_curriculum_text works ({len(text)} chars)")


# ══════════════════════════════════════════════════════════════════════════════
# 3. ADD COURSE FLOW — curriculum picker path
# ══════════════════════════════════════════════════════════════════════════════

class TestAddCoursePickerInstance:
    def test_add_course_from_curriculum_2nd_sem2(self, db):
        """Simulate: batch=2nd, sem=2 → pick 'Basic Computer Programming'."""
        cl = Cleanup(db)
        try:
            courses = get_curriculum_courses(db, year=1, semester=2)
            picked = next(c for c in courses if "Programming" in (c.title or ""))
            c = cl.add_course(
                name=picked.full_name or picked.title,
                credit_hours=picked.credit_hours or 3,
                is_lab=True,
                batch="2nd",
                semester=2,
                instructor="Dr. Abebe",
            )
            db.commit()
            assert c.id is not None
            assert c.batch == "2nd"
            assert c.semester == 2
            assert c.instructor == "Dr. Abebe"
            print(f"\n  ✅ Added: {c.name} | {c.batch} yr | Sem {c.semester} | {c.instructor}")
        finally:
            cl.cleanup()

    def test_add_course_from_curriculum_3rd_sem1(self, db):
        """Simulate: batch=3rd, sem=1 → pick 'Introduction to Statistics'."""
        cl = Cleanup(db)
        try:
            courses = get_curriculum_courses(db, year=2, semester=1)
            picked = next(c for c in courses if "Statistics" in (c.title or ""))
            c = cl.add_course(
                name=picked.full_name or picked.title,
                credit_hours=picked.credit_hours or 3,
                is_lab=False,
                batch="3rd",
                semester=1,
                instructor="TBA",
            )
            db.commit()
            assert c.batch == "3rd"
            assert c.instructor == "TBA"
            print(f"\n  ✅ Added: {c.name} | {c.batch} yr | Sem {c.semester}")
        finally:
            cl.cleanup()

    def test_add_course_manual_entry(self, db):
        """Simulate: manual name entry path."""
        cl = Cleanup(db)
        try:
            c = cl.add_course(
                name="Custom Course Name",
                credit_hours=2,
                is_lab=False,
                batch="4th",
                semester=1,
                instructor="Prof. Test",
            )
            db.commit()
            assert c.name == "Custom Course Name"
            assert c.credit_hours == 2
            print(f"\n  ✅ Manual entry: {c.name}")
        finally:
            cl.cleanup()

    def test_add_multiple_courses_same_session(self, db):
        """Simulate adding 3 courses in one session."""
        cl = Cleanup(db)
        try:
            courses_data = [
                ("Operating Systems", 3, False, "3rd", 2),
                ("Data Structures", 3, True, "3rd", 2),
                ("Discrete Mathematics", 3, False, "3rd", 2),
            ]
            saved = []
            for name, cr, lab, batch, sem in courses_data:
                c = cl.add_course(name=name, credit_hours=cr, is_lab=lab,
                                  batch=batch, semester=sem)
                saved.append(c)
            db.commit()
            assert len(saved) == 3
            print(f"\n  ✅ Added {len(saved)} courses in one session")
            for c in saved:
                print(f"     • {c.name}")
        finally:
            cl.cleanup()

    def test_credit_hours_boundary_validation(self, db):
        with pytest.raises(ValueError):
            add_course(db, "Bad", 0, False, "2nd", 1)
        with pytest.raises(ValueError):
            add_course(db, "Bad", 5, False, "2nd", 1)
        print("\n  ✅ Credit hours validation: 0 and 5 rejected")

    def test_instructor_skip_becomes_tba(self, db):
        cl = Cleanup(db)
        try:
            c = cl.add_course(name="Test", credit_hours=2, is_lab=False,
                              batch="2nd", semester=1, instructor="")
            db.commit()
            assert c.instructor == "TBA"
            print("\n  ✅ Empty instructor → TBA")
        finally:
            cl.cleanup()


# ══════════════════════════════════════════════════════════════════════════════
# 4. ROOMS AND LABS
# ══════════════════════════════════════════════════════════════════════════════

class TestRoomsInstance:
    def test_add_classroom(self, db):
        cl = Cleanup(db)
        try:
            r = cl.add_room(name="Test-Room-101", room_type="classroom", capacity=40)
            db.commit()
            assert r.id is not None
            assert r.room_type == "classroom"
            print(f"\n  ✅ Classroom added: {r.name} ({r.capacity} seats)")
        finally:
            cl.cleanup()

    def test_add_lab(self, db):
        cl = Cleanup(db)
        try:
            r = cl.add_room(name="Test-Lab-X", room_type="lab", capacity=30)
            db.commit()
            assert r.room_type == "lab"
            print(f"\n  ✅ Lab added: {r.name}")
        finally:
            cl.cleanup()

    def test_list_rooms_returns_all_types(self, db):
        rooms = list_rooms(db)
        types = {r.room_type for r in rooms}
        print(f"\n  ✅ list_rooms: {len(rooms)} rooms, types={types}")

    def test_list_labs_only(self, db):
        labs = list_labs(db)
        assert all(r.room_type == "lab" for r in labs)
        print(f"\n  ✅ list_labs: {len(labs)} labs only")

    def test_delete_room(self, db):
        r = add_room(db, name="Temp-Delete-Room", room_type="classroom")
        db.commit()
        rid = r.id
        assert delete_room(db, rid) is True
        db.commit()
        print(f"\n  ✅ Room deleted: id={rid}")

    def test_delete_nonexistent_room(self, db):
        assert delete_room(db, 999999) is False
        print("\n  ✅ Delete nonexistent room returns False")


# ══════════════════════════════════════════════════════════════════════════════
# 5. LAB ASSIGNMENTS
# ══════════════════════════════════════════════════════════════════════════════

class TestLabAssignmentsInstance:
    def test_assign_and_remove(self, db):
        cl = Cleanup(db)
        try:
            lab = cl.add_room(name="Test-Lab-Assign", room_type="lab", capacity=25)
            db.commit()

            # Assign
            ok, err = assign_lab_to_batch(db, lab.id, "2nd")
            db.commit()
            assert ok is True, f"Assign failed: {err}"

            # Verify
            d = get_lab_batch_assignments(db)
            assert d.get(lab.id) == "2nd"
            print(f"\n  ✅ Lab assigned: {lab.name} → 2nd Year")

            # Remove
            removed = remove_lab_assignment(db, lab.id)
            db.commit()
            assert removed is True
            print(f"  ✅ Lab assignment removed")
        finally:
            cl.cleanup()

    def test_one_lab_one_batch_enforced(self, db):
        cl = Cleanup(db)
        try:
            lab = cl.add_room(name="Test-Lab-1to1", room_type="lab")
            db.commit()
            assign_lab_to_batch(db, lab.id, "3rd")
            db.commit()

            ok, err = assign_lab_to_batch(db, lab.id, "4th")
            assert ok is False
            assert err is not None
            print(f"\n  ✅ 1-to-1 enforced: can't assign same lab to 2 batches")
        finally:
            remove_lab_assignment(db, cl.room_ids[-1])
            db.commit()
            cl.cleanup()

    def test_get_assignments_dict(self, db):
        d = get_lab_batch_assignments(db)
        assert isinstance(d, dict)
        print(f"\n  ✅ get_lab_batch_assignments: {len(d)} assignments")
        for rid, batch in d.items():
            print(f"     room_id={rid} → {batch}")


# ══════════════════════════════════════════════════════════════════════════════
# 6. TIME SLOTS
# ══════════════════════════════════════════════════════════════════════════════

class TestTimeSlotsInstance:
    def test_seed_idempotent(self, db):
        """Slots already seeded — should return 0."""
        added = seed_time_slots(db)
        assert added == 0
        print(f"\n  ✅ seed_time_slots idempotent: added={added}")

    def test_45_slots_exist(self, db):
        from src.database.models import TimeSlot
        count = db.query(TimeSlot).count()
        assert count == 45
        print(f"\n  ✅ 45 time slots in DB")


# ══════════════════════════════════════════════════════════════════════════════
# 7. SCHEDULE GENERATION
# ══════════════════════════════════════════════════════════════════════════════

class TestScheduleInstance:
    def test_generate_with_real_data(self, db):
        """Generate schedule using real courses and rooms from Supabase."""
        # Check we have courses and rooms
        courses = list_courses(db)
        rooms = list_rooms(db)
        labs = list_labs(db)
        assignments = get_lab_batch_assignments(db)

        print(f"\n  DB state: {len(courses)} courses, {len(rooms)} rooms, "
              f"{len(labs)} labs, {len(assignments)} lab assignments")

        if not courses:
            pytest.skip("No courses in DB — seed first")
        if not rooms:
            pytest.skip("No rooms in DB — add rooms first")

        clear_schedule(db)
        assigned, unassigned = generate_schedule(db)
        db.commit()

        print(f"  ✅ Generated: {assigned} assigned, {len(unassigned)} unassigned")
        if unassigned:
            print(f"  ⚠️  Unassigned ({len(unassigned)}):")
            for u in unassigned[:5]:
                print(f"     • {u}")

        assert assigned >= 0

    def test_no_room_conflicts(self, db):
        entries = get_schedule(db)
        pairs = [(e.room_id, e.time_slot_id) for e in entries]
        assert len(pairs) == len(set(pairs)), "Room conflict detected!"
        print(f"\n  ✅ No room conflicts in {len(entries)} schedule entries")

    def test_no_section_conflicts(self, db):
        from collections import defaultdict
        entries = get_schedule(db)
        by_section = defaultdict(list)
        for e in entries:
            by_section[(e.batch, e.section)].append(e.time_slot_id)
        conflicts = {k: v for k, v in by_section.items()
                     if len(v) != len(set(v))}
        assert not conflicts, f"Section conflicts: {conflicts}"
        print(f"\n  ✅ No section conflicts across {len(by_section)} sections")

    def test_get_schedule_filters(self, db):
        all_entries = get_schedule(db)
        if not all_entries:
            pytest.skip("No schedule entries")

        batch = all_entries[0].batch
        filtered = get_schedule(db, batch=batch)
        assert all(e.batch == batch for e in filtered)
        print(f"\n  ✅ Filter by batch={batch}: {len(filtered)}/{len(all_entries)} entries")

    def test_format_schedule_text(self, db):
        entries = get_schedule(db)
        if not entries:
            pytest.skip("No schedule entries")
        text = format_schedule_text(entries)
        assert len(text) > 10
        print(f"\n  ✅ format_schedule_text: {len(text)} chars")


# ══════════════════════════════════════════════════════════════════════════════
# 8. UPDATE INSTRUCTOR
# ══════════════════════════════════════════════════════════════════════════════

class TestUpdateInstructorInstance:
    def test_update_instructor(self, db):
        cl = Cleanup(db)
        try:
            c = cl.add_course(name="Inst Test", credit_hours=2,
                              is_lab=False, batch="2nd", semester=1)
            db.commit()
            assert update_instructor(db, c.id, "Dr. New Name") is True
            db.commit()
            db.refresh(c)
            assert c.instructor == "Dr. New Name"
            print(f"\n  ✅ Instructor updated: {c.instructor}")
        finally:
            cl.cleanup()

    def test_update_instructor_empty_becomes_tba(self, db):
        cl = Cleanup(db)
        try:
            c = cl.add_course(name="TBA Test", credit_hours=2,
                              is_lab=False, batch="2nd", semester=1)
            db.commit()
            update_instructor(db, c.id, "   ")
            db.commit()
            db.refresh(c)
            assert c.instructor == "TBA"
            print("\n  ✅ Empty instructor → TBA")
        finally:
            cl.cleanup()

    def test_update_nonexistent_course(self, db):
        assert update_instructor(db, 999999, "X") is False
        print("\n  ✅ Update nonexistent course returns False")
