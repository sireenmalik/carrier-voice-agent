"""Tool-name → simulator/validator dispatch.

Each handler returns {"status": "success" | "error", "content": <json-dict>}.
The loop wraps this into a Bedrock `toolResult` block and feeds it back.

Policy rejections on writes return status="success" with `booked: False` and a
reason string — the call to the tool succeeded, the write was declined. The
model reads the payload and relays the reason to the caller."""

from __future__ import annotations

from typing import Any, Callable

from sim import appointments
from sim.accounts import get_account
from sim.network import get_site_health
from sim.outages import get_incidents
from validator.policy import validate_write


def _handle_get_site_health(args: dict[str, Any], context: dict[str, Any], logger) -> dict[str, Any]:
    cell_site_id = args.get("cell_site_id")
    if not cell_site_id:
        return {"status": "error", "content": {"error": "cell_site_id is required"}}
    try:
        health = get_site_health(cell_site_id)
    except KeyError:
        return {"status": "error", "content": {"error": f"unknown cell site: {cell_site_id}"}}
    return {"status": "success", "content": {"cell_site_id": cell_site_id, "health": health}}


def _handle_get_account_status(args: dict[str, Any], context: dict[str, Any], logger) -> dict[str, Any]:
    account_id = args.get("account_id")
    if not account_id:
        return {"status": "error", "content": {"error": "account_id is required"}}
    account = get_account(account_id)
    if account is None:
        return {"status": "error", "content": {"error": f"account not found: {account_id}"}}
    return {
        "status": "success",
        "content": {
            "account_id": account_id,
            "plan": account["plan"],
            "balance": account["balance"],
        },
    }


def _handle_lookup_outage(args: dict[str, Any], context: dict[str, Any], logger) -> dict[str, Any]:
    zip_code = args.get("zip_code")
    if not zip_code:
        return {"status": "error", "content": {"error": "zip_code is required"}}
    incidents = get_incidents(zip_code)
    return {
        "status": "success",
        "content": {"zip_code": zip_code, "incidents": incidents},
    }


def _handle_book_appointment(args: dict[str, Any], context: dict[str, Any], logger) -> dict[str, Any]:
    ok, reason = validate_write("book_appointment", args, context)
    logger.log("validator_decision", {
        "tool": "book_appointment",
        "input": args,
        "ok": ok,
        "reason": reason,
    })
    if not ok:
        return {"status": "success", "content": {"booked": False, "reason": reason}}
    appointment = appointments.book(args["account_id"], args["slot"])
    return {
        "status": "success",
        "content": {
            "booked": True,
            "confirmation": appointment["confirmation"],
            "account_id": appointment["account_id"],
            "slot": appointment["slot"],
        },
    }


def _handle_escalate_to_human(args: dict[str, Any], context: dict[str, Any], logger) -> dict[str, Any]:
    return {
        "status": "success",
        "content": {"escalated": True, "reason": args.get("reason", "")},
    }


_Handler = Callable[[dict[str, Any], dict[str, Any], Any], dict[str, Any]]

_HANDLERS: dict[str, _Handler] = {
    "get_site_health": _handle_get_site_health,
    "get_account_status": _handle_get_account_status,
    "lookup_outage": _handle_lookup_outage,
    "book_appointment": _handle_book_appointment,
    "escalate_to_human": _handle_escalate_to_human,
}


def handle_tool_call(
    *,
    tool_name: str,
    tool_input: dict[str, Any],
    context: dict[str, Any],
    logger,
) -> dict[str, Any]:
    handler = _HANDLERS.get(tool_name)
    if handler is None:
        return {"status": "error", "content": {"error": f"unknown tool: {tool_name}"}}
    return handler(tool_input, context, logger)
