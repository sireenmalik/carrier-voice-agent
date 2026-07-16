"""Appointment store is process-local mutable state — reset between tests so
one test's booking cannot leak into another's assertions."""

from __future__ import annotations

import pytest

from sim import appointments


@pytest.fixture(autouse=True)
def _clear_store():
    appointments.clear()
    yield
    appointments.clear()


def test_book_returns_appointment_with_expected_fields():
    appt = appointments.book("ACC-1001", "2026-07-20T10:00:00")
    assert appt["account_id"] == "ACC-1001"
    assert appt["slot"] == "2026-07-20T10:00:00"
    assert appt["confirmation"].startswith("APT-")
    assert len(appt["confirmation"]) == 12  # "APT-" + 8 hex
    assert appt["booked_at"]


def test_book_persists_appointment_in_store():
    appt = appointments.book("ACC-1001", "2026-07-20T10:00:00")
    assert appointments.get(appt["confirmation"]) == appt


def test_multiple_bookings_produce_unique_confirmations():
    a = appointments.book("ACC-1001", "2026-07-20T10:00:00")
    b = appointments.book("ACC-1001", "2026-07-20T11:00:00")
    c = appointments.book("ACC-1002", "2026-07-20T10:00:00")
    assert len({a["confirmation"], b["confirmation"], c["confirmation"]}) == 3
    assert len(appointments.all_appointments()) == 3


def test_all_appointments_view_is_read_only():
    appointments.book("ACC-1001", "2026-07-20T10:00:00")
    with pytest.raises(TypeError):
        appointments.all_appointments()["APT-HACK"] = {}  # type: ignore[index]


def test_clear_resets_store():
    appointments.book("ACC-1001", "2026-07-20T10:00:00")
    appointments.clear()
    assert appointments.all_appointments() == {}


def test_get_unknown_confirmation_returns_none():
    assert appointments.get("APT-DEADBEEF") is None
