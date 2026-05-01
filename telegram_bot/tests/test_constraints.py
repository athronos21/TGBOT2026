"""
Tests for src/scheduler/constraints.py — ConstraintTracker.
"""
import pytest
from src.scheduler.constraints import ConstraintTracker


class TestConstraintTracker:
    def setup_method(self):
        self.tracker = ConstraintTracker()

    # ── is_room_free ──────────────────────────────────────────────────────────

    def test_room_free_initially(self):
        assert self.tracker.is_room_free(room_id=1, slot_id=10) is True

    def test_room_not_free_after_booking(self):
        self.tracker.book(room_id=1, batch="2nd", section="A", slot_id=10, start_hour=8)
        assert self.tracker.is_room_free(room_id=1, slot_id=10) is False

    def test_room_free_different_slot(self):
        self.tracker.book(room_id=1, batch="2nd", section="A", slot_id=10, start_hour=8)
        assert self.tracker.is_room_free(room_id=1, slot_id=11) is True

    def test_room_free_different_room(self):
        self.tracker.book(room_id=1, batch="2nd", section="A", slot_id=10, start_hour=8)
        assert self.tracker.is_room_free(room_id=2, slot_id=10) is True

    # ── is_section_free ───────────────────────────────────────────────────────

    def test_section_free_initially(self):
        assert self.tracker.is_section_free("2nd", "A", slot_id=5) is True

    def test_section_not_free_after_booking(self):
        self.tracker.book(room_id=1, batch="2nd", section="A", slot_id=5, start_hour=9)
        assert self.tracker.is_section_free("2nd", "A", slot_id=5) is False

    def test_section_free_different_section(self):
        self.tracker.book(room_id=1, batch="2nd", section="A", slot_id=5, start_hour=9)
        assert self.tracker.is_section_free("2nd", "B", slot_id=5) is True

    def test_section_free_different_batch(self):
        self.tracker.book(room_id=1, batch="2nd", section="A", slot_id=5, start_hour=9)
        assert self.tracker.is_section_free("3rd", "A", slot_id=5) is True

    # ── can_assign ────────────────────────────────────────────────────────────

    def test_can_assign_initially(self):
        assert self.tracker.can_assign(1, "2nd", "A", 10) is True

    def test_cannot_assign_room_taken(self):
        self.tracker.book(1, "3rd", "B", 10, 8)
        assert self.tracker.can_assign(1, "2nd", "A", 10) is False

    def test_cannot_assign_section_taken(self):
        self.tracker.book(1, "2nd", "A", 10, 8)
        assert self.tracker.can_assign(2, "2nd", "A", 10) is False

    def test_can_assign_different_slot(self):
        self.tracker.book(1, "2nd", "A", 10, 8)
        assert self.tracker.can_assign(1, "2nd", "A", 11) is True

    # ── fairness / prefers_morning ────────────────────────────────────────────

    def test_prefers_morning_initially(self):
        # 0 morning, 0 afternoon → 0 <= 0 → True (prefer morning)
        assert self.tracker.prefers_morning("2nd", "A") is True

    def test_prefers_afternoon_after_morning_heavy(self):
        # Book 3 morning slots
        for slot_id in range(3):
            self.tracker.book(1 + slot_id, "2nd", "A", slot_id, start_hour=8)
        # Now morning=3, afternoon=0 → 3 > 0 → prefer afternoon
        assert self.tracker.prefers_morning("2nd", "A") is False

    def test_morning_count(self):
        self.tracker.book(1, "2nd", "A", 1, start_hour=8)   # morning
        self.tracker.book(2, "2nd", "A", 2, start_hour=9)   # morning
        assert self.tracker.morning_count("2nd", "A") == 2

    def test_afternoon_count(self):
        self.tracker.book(1, "2nd", "A", 1, start_hour=12)  # afternoon
        assert self.tracker.afternoon_count("2nd", "A") == 1

    def test_morning_cutoff_boundary(self):
        # start_hour=11 → morning (< 12)
        self.tracker.book(1, "2nd", "A", 1, start_hour=11)
        assert self.tracker.morning_count("2nd", "A") == 1
        assert self.tracker.afternoon_count("2nd", "A") == 0

    def test_afternoon_cutoff_boundary(self):
        # start_hour=12 → afternoon (>= 12)
        self.tracker.book(1, "2nd", "A", 1, start_hour=12)
        assert self.tracker.morning_count("2nd", "A") == 0
        assert self.tracker.afternoon_count("2nd", "A") == 1

    def test_independent_sections(self):
        self.tracker.book(1, "2nd", "A", 1, start_hour=8)
        assert self.tracker.morning_count("2nd", "B") == 0

    def test_independent_batches(self):
        self.tracker.book(1, "2nd", "A", 1, start_hour=8)
        assert self.tracker.morning_count("3rd", "A") == 0
