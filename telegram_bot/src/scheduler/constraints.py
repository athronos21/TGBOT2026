"""
Constraint helpers used by the scheduling engine.
All checks operate on in-memory sets for speed during generation.
"""
from dataclasses import dataclass, field
from typing import Set, Tuple, Dict
from src.config import MORNING_CUTOFF


# (room_id, time_slot_id)
RoomSlotKey = Tuple[int, int]

# (batch, section, time_slot_id)
SectionSlotKey = Tuple[str, str, int]


@dataclass
class ConstraintTracker:
    """Tracks occupied slots during schedule generation."""

    # Rooms already booked: room_id → set of time_slot_ids
    room_bookings: Dict[int, Set[int]] = field(default_factory=dict)

    # Sections already booked: (batch, section) → set of time_slot_ids
    section_bookings: Dict[Tuple[str, str], Set[int]] = field(default_factory=dict)

    # Fairness counters: (batch, section) → {"morning": int, "afternoon": int}
    fairness: Dict[Tuple[str, str], Dict[str, int]] = field(default_factory=dict)

    def is_room_free(self, room_id: int, slot_id: int) -> bool:
        return slot_id not in self.room_bookings.get(room_id, set())

    def is_section_free(self, batch: str, section: str, slot_id: int) -> bool:
        return slot_id not in self.section_bookings.get((batch, section), set())

    def can_assign(self, room_id: int, batch: str, section: str, slot_id: int) -> bool:
        return self.is_room_free(room_id, slot_id) and self.is_section_free(
            batch, section, slot_id
        )

    def book(self, room_id: int, batch: str, section: str, slot_id: int, start_hour: int) -> None:
        self.room_bookings.setdefault(room_id, set()).add(slot_id)
        self.section_bookings.setdefault((batch, section), set()).add(slot_id)

        key = (batch, section)
        self.fairness.setdefault(key, {"morning": 0, "afternoon": 0})
        if start_hour < MORNING_CUTOFF:
            self.fairness[key]["morning"] += 1
        else:
            self.fairness[key]["afternoon"] += 1

    def morning_count(self, batch: str, section: str) -> int:
        return self.fairness.get((batch, section), {}).get("morning", 0)

    def afternoon_count(self, batch: str, section: str) -> int:
        return self.fairness.get((batch, section), {}).get("afternoon", 0)

    def prefers_morning(self, batch: str, section: str) -> bool:
        """Return True if this section needs more morning slots for fairness."""
        m = self.morning_count(batch, section)
        a = self.afternoon_count(batch, section)
        return m <= a  # give morning if mornings ≤ afternoons
