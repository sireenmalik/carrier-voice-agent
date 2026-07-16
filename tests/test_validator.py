"""Every rule in the validator gets at least one accept and one reject.
Rejection reason strings are what the UI surfaces, so a couple of tests
assert substrings to catch silent wording drift."""

from __future__ import annotations

import pytest

from sim.accounts import all_accounts, get_account
from sim.network import get_site_health
from validator.policy import validate_write


def _account_on(status: str) -> str:
    for account_id, account in all_accounts().items():
        if get_site_health(account["cell_site_id"]) == status:
            return account_id
    raise AssertionError(f"no seeded account on a {status!r} site")


HEALTHY_ACCOUNT = _account_on("healthy")
MAINTENANCE_ACCOUNT = _account_on("maintenance")

VALID_SLOT = "2026-07-20T10:00:00"
BEFORE_HOURS = "2026-07-20T03:00:00"
AFTER_HOURS = "2026-07-20T18:30:00"


def test_book_appointment_happy_path():
    ok, reason = validate_write(
        "book_appointment",
        {"account_id": HEALTHY_ACCOUNT, "slot": VALID_SLOT},
        {},
    )
    assert ok, reason
    assert reason == "ok"


def test_book_appointment_rejects_unknown_account():
    ok, reason = validate_write(
        "book_appointment",
        {"account_id": "ACC-9999", "slot": VALID_SLOT},
        {},
    )
    assert not ok
    assert "not found" in reason


def test_book_appointment_rejects_missing_account_id():
    ok, reason = validate_write(
        "book_appointment",
        {"slot": VALID_SLOT},
        {},
    )
    assert not ok
    assert "account_id" in reason


@pytest.mark.parametrize("slot", [BEFORE_HOURS, AFTER_HOURS])
def test_book_appointment_rejects_outside_business_hours(slot):
    ok, reason = validate_write(
        "book_appointment",
        {"account_id": HEALTHY_ACCOUNT, "slot": slot},
        {},
    )
    assert not ok
    assert "business hours" in reason


def test_book_appointment_rejects_malformed_slot():
    ok, reason = validate_write(
        "book_appointment",
        {"account_id": HEALTHY_ACCOUNT, "slot": "next tuesday"},
        {},
    )
    assert not ok
    assert "ISO 8601" in reason


def test_book_appointment_rejects_caller_on_maintenance_site():
    account = get_account(MAINTENANCE_ACCOUNT)
    assert account is not None
    ok, reason = validate_write(
        "book_appointment",
        {"account_id": MAINTENANCE_ACCOUNT, "slot": VALID_SLOT},
        {},
    )
    assert not ok
    assert "maintenance" in reason
    assert account["cell_site_id"] in reason


def test_book_appointment_context_cell_site_overrides_account_home():
    ok, reason = validate_write(
        "book_appointment",
        {"account_id": HEALTHY_ACCOUNT, "slot": VALID_SLOT},
        {"cell_site_id": get_account(MAINTENANCE_ACCOUNT)["cell_site_id"]},
    )
    assert not ok
    assert "maintenance" in reason


def test_read_only_tools_always_pass():
    for tool in ("get_site_health", "get_account_status", "lookup_outage"):
        ok, _ = validate_write(tool, {}, {})
        assert ok


def test_escalate_to_human_always_passes():
    ok, _ = validate_write("escalate_to_human", {"reason": "caller distressed"}, {})
    assert ok


def test_unknown_tool_rejected():
    ok, reason = validate_write("delete_account", {"account_id": HEALTHY_ACCOUNT}, {})
    assert not ok
    assert "unknown tool" in reason
