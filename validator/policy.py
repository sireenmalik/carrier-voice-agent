"""Deterministic write-path validator. Called before any tool result that
would mutate state is returned to the model. Rejection reasons are surfaced
verbatim in the UI, so keep them short and specific."""

from __future__ import annotations

from datetime import datetime, time
from typing import Any, Final

from sim.accounts import get_account
from sim.network import get_site_health

BUSINESS_START: Final = time(9, 0)
BUSINESS_END: Final = time(17, 0)

_READ_ONLY_TOOLS: Final = frozenset({"get_site_health", "get_account_status", "lookup_outage"})


def validate_write(
    tool_name: str,
    args: dict[str, Any],
    context: dict[str, Any],
) -> tuple[bool, str]:
    if tool_name in _READ_ONLY_TOOLS:
        return (True, "read-only tool; no write to validate")
    if tool_name == "escalate_to_human":
        return (True, "escalation is always permitted")
    if tool_name == "book_appointment":
        return _validate_book_appointment(args, context)
    return (False, f"unknown tool: {tool_name!r}")


def _validate_book_appointment(
    args: dict[str, Any],
    context: dict[str, Any],
) -> tuple[bool, str]:
    account_id = args.get("account_id")
    if not account_id:
        return (False, "account_id is required")

    account = get_account(account_id)
    if account is None:
        return (False, f"account {account_id} not found")

    slot = args.get("slot")
    if not slot:
        return (False, "slot is required")
    try:
        slot_dt = datetime.fromisoformat(str(slot))
    except ValueError:
        return (False, f"slot {slot!r} is not a valid ISO 8601 datetime")

    slot_time = slot_dt.time()
    if not (BUSINESS_START <= slot_time < BUSINESS_END):
        return (
            False,
            f"slot {slot_time.strftime('%H:%M')} is outside business hours "
            f"({BUSINESS_START.strftime('%H:%M')}–{BUSINESS_END.strftime('%H:%M')})",
        )

    caller_site = context.get("cell_site_id") or account["cell_site_id"]
    try:
        site_status = get_site_health(caller_site)
    except KeyError:
        return (False, f"caller cell site {caller_site} is not in the network inventory")

    if site_status == "maintenance":
        return (False, f"cell site {caller_site} is in maintenance; cannot book appointment")

    return (True, "ok")
