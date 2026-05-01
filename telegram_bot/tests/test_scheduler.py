"""
Tests for src/scheduler/engine.py — generate_schedule integration tests.
All run against in-memory SQLite via the shared `session` fixture.
"""
import pytest

from src.bot.commands import (
    add_course, add_room, assign_lab_to_batch, seed_time_slots,
    get_schedule, clear_schedule,
)
from src.scheduler.engine import generate_schedule, _sorted_slots, _lab_for_batch
from src.database.models import TimeSlot, Room


# ── Helpers ───────────────────────────────────────────────────────────────────

def _setup_slots(session):
    return seed_time_slots(session)


def _classroom(session, name="Room-101"):
    return add_room(session, name=name, room_type="classroom", capacity=40)


def _lab(session, name="Lab-1"):
    return add_room(session, name=name, room_type="lab", capacity=30)


def _course(session, name="OS", credit_hours=2, is_lab=False,
            batch="2nd", semester=1):
    return add_course(session, name=name, credit_hours=credit_hours,
                      is_lab=is_lab, batch=batch, semester=semester)


# ── _sorted_slots ─────────────────────────────────────────────────────────────

class TestSortedSlots:
    def _make_slots(self, hours):
        return [TimeSlot(id=h, day="Monday", start_hour=h, end_hour=h+1) for h in hours]

    def test_prefer_morning_puts_morning_first(self):
        slots = self._make_slots([8, 9, 12, 13])
        result = _sorted_slots(slots, prefer_morning=True)
        assert result[0].start_hour == 8
        assert result[1].start_hour == 9

    def test_prefer_afternoon_puts_afternoon_first(self):
        slots = self._make_slots([8, 9, 12, 13])
        result = _sorted_slots(slots, prefer_morning=False)
        assert result[0].start_hour == 12
        assert result[1].start_hour == 13

    def test_all_morning(self):
        slots = self._make_slots([8, 9, 10])
        result = _sorted_slots(slots, prefer_morning=False)
        # No afternoon slots — morning slots still returned
        assert len(result) == 3

    def test_all_afternoon(self):
        slots = self._make_slots([12, 13, 14])
        result = _sorted_slots(slots, prefer_morning=True)
        assert len(result) == 3


# ── _lab_for_batch ────────────────────────────────────────────────────────────

class TestLabForBatch:
    def test_finds_assigned_lab(self):
        lab = Room(id=1, name="Lab-A", room_type="lab")
        assignments = {1: "2nd"}
        result = _lab_for_batch([lab], assignments, "2nd")
        assert result is lab

    def test_returns_none_when_not_assigned(self):
        lab = Room(id=1, name="Lab-A", room_type="lab")
        assignments = {1: "3rd"}
        result = _lab_for_batch([lab], assignments, "2nd")
        assert result is None

    def test_returns_none_empty_assignments(self):
        lab = Room(id=1, name="Lab-A", room_type="lab")
        result = _lab_for_batch([lab], {}, "2nd")
        assert result is None

    def test_returns_none_empty_labs(self):
        result = _lab_for_batch([], {1: "2nd"}, "2nd")
        assert result is None


# ── generate_schedule — integration ──────────────────────────────────────────

class TestGenerateSchedule:
    def test_empty_db_returns_zero(self, session):
        _setup_slots(session)
        assigned, unassigned = generate_schedule(session)
        assert assigned == 0
        assert unassigned == []

    def test_single_classroom_course(self, session):
        _setup_slots(session)
        _classroom(session)
        _course(session, credit_hours=2)
        session.flush()
        # 1 course × 2 credit_hours × 2 sections = 4 sessions
        assigned, unassigned = generate_schedule(session)
        assert assigned == 4
        assert unassigned == []

    def test_lab_course_without_assignment_is_unassigned(self, session):
        _setup_slots(session)
        _lab(session)
        _course(session, name="Lab Course", credit_hours=2, is_lab=True, batch="2nd")
        session.flush()
        assigned, unassigned = generate_schedule(session)
        assert assigned == 0
        assert len(unassigned) == 4  # 2 credit_hours × 2 sections
        assert all("no lab assigned" in u for u in unassigned)

    def test_lab_course_with_assignment(self, session):
        _setup_slots(session)
        lab = _lab(session)
        assign_lab_to_batch(session, lab.id, "2nd")
        _course(session, name="Lab Course", credit_hours=2, is_lab=True, batch="2nd")
        session.flush()
        assigned, unassigned = generate_schedule(session)
        assert assigned == 4
        assert unassigned == []

    def test_no_rooms_all_unassigned(self, session):
        _setup_slots(session)
        _course(session, credit_hours=1)
        session.flush()
        assigned, unassigned = generate_schedule(session)
        assert assigned == 0
        assert len(unassigned) == 2  # 1 credit_hour × 2 sections

    def test_no_slots_all_unassigned(self, session):
        _classroom(session)
        _course(session, credit_hours=1)
        session.flush()
        assigned, unassigned = generate_schedule(session)
        assert assigned == 0
        assert len(unassigned) == 2

    def test_multiple_batches(self, session):
        _setup_slots(session)
        _classroom(session)
        for batch in ("2nd", "3rd", "4th"):
            _course(session, name=f"OS-{batch}", credit_hours=1, batch=batch)
        session.flush()
        # 3 batches × 1 credit_hour × 2 sections = 6 sessions
        assigned, unassigned = generate_schedule(session)
        assert assigned == 6
        assert unassigned == []

    def test_no_room_conflicts(self, session):
        """Two sections of the same course must not share a room+slot."""
        _setup_slots(session)
        _classroom(session)
        _course(session, credit_hours=3)
        session.flush()
        generate_schedule(session)
        entries = get_schedule(session)
        # Check no (room_id, time_slot_id) pair appears twice
        pairs = [(e.room_id, e.time_slot_id) for e in entries]
        assert len(pairs) == len(set(pairs))

    def test_no_section_conflicts(self, session):
        """A section must not have two classes at the same time."""
        _setup_slots(session)
        _classroom(session, "R1")
        _classroom(session, "R2")
        _course(session, name="C1", credit_hours=2)
        _course(session, name="C2", credit_hours=2)
        session.flush()
        generate_schedule(session)
        entries = get_schedule(session)
        # For each (batch, section), no time_slot_id should repeat
        from collections import defaultdict
        by_section = defaultdict(list)
        for e in entries:
            by_section[(e.batch, e.section)].append(e.time_slot_id)
        for key, slots in by_section.items():
            assert len(slots) == len(set(slots)), f"Conflict in {key}"

    def test_clear_before_regenerate(self, session):
        _setup_slots(session)
        _classroom(session)
        _course(session, credit_hours=1)
        session.flush()
        generate_schedule(session)
        first = len(get_schedule(session))
        clear_schedule(session)
        generate_schedule(session)
        second = len(get_schedule(session))
        assert first == second

    def test_lab_priority_over_classroom(self, session):
        """Lab courses are scheduled before classroom courses."""
        _setup_slots(session)
        lab = _lab(session)
        assign_lab_to_batch(session, lab.id, "2nd")
        _classroom(session)
        _course(session, name="Lab C", credit_hours=1, is_lab=True, batch="2nd")
        _course(session, name="Class C", credit_hours=1, is_lab=False, batch="2nd")
        session.flush()
        assigned, unassigned = generate_schedule(session)
        # Both should be assigned (enough slots)
        assert assigned == 4  # 2 courses × 1 credit × 2 sections
        assert unassigned == []

    def test_credit_hours_respected(self, session):
        """A course with credit_hours=3 should produce 3 entries per section."""
        _setup_slots(session)
        _classroom(session)
        _course(session, credit_hours=3)
        session.flush()
        generate_schedule(session)
        session.flush()
        entries = get_schedule(session, batch="2nd", section="A")
        assert len(entries) == 3
