"""In-memory appointment store. Confirmation IDs are opaque, non-guessable,
and printable — the model will read them aloud to the caller."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Mapping, TypedDict


class Appointment(TypedDict):
    confirmation: str
    account_id: str
    slot: str
    booked_at: str


_APPOINTMENTS: dict[str, Appointment] = {}


def book(account_id: str, slot: str) -> Appointment:
    confirmation = "APT-" + uuid.uuid4().hex[:8].upper()
    appointment: Appointment = {
        "confirmation": confirmation,
        "account_id": account_id,
        "slot": slot,
        "booked_at": datetime.now(timezone.utc).isoformat(),
    }
    _APPOINTMENTS[confirmation] = appointment
    return appointment


def get(confirmation: str) -> Appointment | None:
    return _APPOINTMENTS.get(confirmation)


def all_appointments() -> Mapping[str, Appointment]:
    return MappingProxyType(_APPOINTMENTS)


def clear() -> None:
    """Reset the in-memory store. Test helper only."""
    _APPOINTMENTS.clear()
