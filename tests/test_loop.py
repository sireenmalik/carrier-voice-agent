"""End-to-end loop tests with a scripted fake Bedrock client.

The fake mirrors `boto3.client('bedrock-runtime').converse(**kwargs)` — same
call surface, same response shape — so the loop code has no test-only branches."""

from __future__ import annotations

import copy
import json
from typing import Any

from agent.loop import run_turn, StepLogger
from sim.accounts import all_accounts
from sim.network import get_site_health


def _account_and_site_on(status: str) -> tuple[str, str]:
    for account_id, account in all_accounts().items():
        if get_site_health(account["cell_site_id"]) == status:
            return account_id, account["cell_site_id"]
    raise AssertionError(f"no seeded account on a {status!r} site")


class FakeBedrock:
    """Scripted stand-in for boto3 bedrock-runtime.

    Records every `.converse(**kwargs)` call and pops responses off a queue in
    order. Tests inspect `.calls` to assert what was sent to the model."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(copy.deepcopy(kwargs))
        if not self.responses:
            raise AssertionError("FakeBedrock ran out of scripted responses")
        return self.responses.pop(0)


def _tool_use_response(tool_use_id: str, name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {"toolUse": {"toolUseId": tool_use_id, "name": name, "input": tool_input}}
                ],
            }
        },
        "stopReason": "tool_use",
    }


def _text_response(text: str) -> dict[str, Any]:
    return {
        "output": {"message": {"role": "assistant", "content": [{"text": text}]}},
        "stopReason": "end_turn",
    }


def test_agent_consults_site_health_before_answering_outage():
    _, maintenance_site = _account_and_site_on("maintenance")

    client = FakeBedrock([
        _tool_use_response("tu-1", "get_site_health", {"cell_site_id": maintenance_site}),
        _text_response(
            f"Your tower {maintenance_site} is in scheduled maintenance. "
            "Estimated restore at 4pm. This is not a device problem."
        ),
    ])
    logger = StepLogger()
    reply = run_turn(
        client=client,
        model_id="test-model",
        user_utterance="my service is out",
        conversation=[],
        context={"cell_site_id": maintenance_site},
        logger=logger,
    )

    assert "maintenance" in reply.lower()

    kinds = [event["kind"] for event in logger.events]
    assert "tool_call" in kinds, f"expected a tool_call event, got kinds={kinds}"
    tool_call_index = kinds.index("tool_call")

    tool_call_event = logger.events[tool_call_index]
    assert tool_call_event["payload"]["name"] == "get_site_health"
    assert tool_call_event["payload"]["input"]["cell_site_id"] == maintenance_site

    assistant_transcript_before_tool = [
        event
        for event in logger.events[:tool_call_index]
        if event["kind"] == "transcript" and event["payload"]["role"] == "assistant"
    ]
    assert not assistant_transcript_before_tool, (
        "agent produced an assistant transcript before consulting site health"
    )

    tool_result_event = next(e for e in logger.events if e["kind"] == "tool_result")
    assert tool_result_event["payload"]["content"]["health"] == "maintenance"


def test_booking_on_maintenance_site_is_rejected_with_reason_surfaced_back():
    maintenance_account, maintenance_site = _account_and_site_on("maintenance")

    client = FakeBedrock([
        _tool_use_response("tu-1", "book_appointment", {
            "account_id": maintenance_account,
            "slot": "2026-07-20T10:00:00",
        }),
        _text_response(
            "I'm sorry — I can't book that right now because your local "
            "cell site is in maintenance. Would you like me to escalate?"
        ),
    ])
    logger = StepLogger()
    reply = run_turn(
        client=client,
        model_id="test-model",
        user_utterance="book me a repair tomorrow at 10am",
        conversation=[],
        context={},
        logger=logger,
    )

    validator_events = [e for e in logger.events if e["kind"] == "validator_decision"]
    assert len(validator_events) == 1
    decision = validator_events[0]["payload"]
    assert decision["ok"] is False
    assert "maintenance" in decision["reason"].lower()
    assert maintenance_site in decision["reason"]

    tool_result_events = [e for e in logger.events if e["kind"] == "tool_result"]
    assert len(tool_result_events) == 1
    result_content = tool_result_events[0]["payload"]["content"]
    assert result_content["booked"] is False
    assert "maintenance" in result_content["reason"].lower()

    assert len(client.calls) == 2, "loop should have called converse twice"
    second_call_messages = client.calls[1]["messages"]
    tool_result_msg = second_call_messages[-1]
    assert tool_result_msg["role"] == "user"
    tool_result_block = tool_result_msg["content"][0]["toolResult"]
    fed_back = tool_result_block["content"][0]["json"]
    assert fed_back["booked"] is False
    assert "maintenance" in fed_back["reason"].lower()

    assert reply
    assert any(word in reply.lower() for word in ("sorry", "can't", "cannot", "maintenance"))


def test_every_logged_event_is_json_serializable():
    account_id, site_id = _account_and_site_on("healthy")

    client = FakeBedrock([
        _tool_use_response("tu-1", "get_site_health", {"cell_site_id": site_id}),
        _text_response("Your site is healthy. What can I help you with?"),
    ])
    logger = StepLogger()
    run_turn(
        client=client,
        model_id="test-model",
        user_utterance="is my area up?",
        conversation=[],
        context={"cell_site_id": site_id, "account_id": account_id},
        logger=logger,
    )

    for event in logger.events:
        json.dumps(event)
