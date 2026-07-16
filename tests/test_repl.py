"""REPL smoke test — one utterance in, scripted Bedrock responses, capture
emit events, assert the ordered event stream matches the expected replay."""

from __future__ import annotations

import io

from agent.repl import format_event, main
from sim.accounts import all_accounts
from sim.network import get_site_health
from tests.test_loop import FakeBedrock, _text_response, _tool_use_response


def _account_and_site_on(status: str) -> tuple[str, str]:
    for account_id, account in all_accounts().items():
        if get_site_health(account["cell_site_id"]) == status:
            return account_id, account["cell_site_id"]
    raise AssertionError(f"no seeded account on a {status!r} site")


def test_repl_smoke_emits_events_in_expected_order():
    """A booking on a maintenance site exercises all four event kinds —
    transcript → tool_call → validator_decision → tool_result → transcript.
    That ordering is the contract with the frontend replayer."""

    maintenance_account, _ = _account_and_site_on("maintenance")

    client = FakeBedrock([
        _tool_use_response("tu-1", "book_appointment", {
            "account_id": maintenance_account,
            "slot": "2026-07-20T10:00:00",
        }),
        _text_response(
            "I'm sorry — I can't book that. Your cell site is in maintenance."
        ),
    ])

    captured: list[dict] = []
    stdin = io.StringIO("book me tomorrow at 10\nquit\n")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = main(
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        client=client,
        model_id="test-model",
        emit=captured.append,
    )

    assert exit_code == 0

    kinds = [event["kind"] for event in captured]
    assert kinds == [
        "transcript",          # user utterance
        "tool_call",           # book_appointment proposed
        "validator_decision",  # rejected: maintenance site
        "tool_result",         # rejection fed back to model
        "transcript",          # assistant final reply
    ]

    assert captured[0]["payload"]["role"] == "user"
    assert captured[0]["payload"]["text"] == "book me tomorrow at 10"

    assert captured[1]["payload"]["name"] == "book_appointment"
    assert captured[1]["payload"]["input"]["account_id"] == maintenance_account

    assert captured[2]["payload"]["ok"] is False
    assert "maintenance" in captured[2]["payload"]["reason"].lower()

    assert captured[3]["payload"]["content"]["booked"] is False

    assert captured[-1]["payload"]["role"] == "assistant"

    assert stderr.getvalue() == ""


def test_repl_persists_conversation_across_turns():
    """Second turn must ship the first turn's messages back to the model —
    that is how the model remembers what the caller already said."""

    _, site_id = _account_and_site_on("healthy")

    client = FakeBedrock([
        _tool_use_response("tu-1", "get_site_health", {"cell_site_id": site_id}),
        _text_response("Your site is healthy."),
        _text_response("Nothing else on my end. Have a good one."),
    ])

    stdin = io.StringIO("is my area up?\nthanks, that's it\nquit\n")
    stdout = io.StringIO()
    stderr = io.StringIO()

    main(
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        client=client,
        model_id="test-model",
        emit=lambda _event: None,
    )

    assert len(client.calls) == 3

    third_call_messages = client.calls[2]["messages"]
    roles = [m["role"] for m in third_call_messages]
    assert roles.count("user") >= 2, (
        f"third call should carry both user utterances; got roles={roles}"
    )


def test_repl_prints_missing_model_id_and_returns_nonzero(monkeypatch):
    monkeypatch.delenv("BEDROCK_MODEL_ID_TEXT", raising=False)
    stderr = io.StringIO()
    stdout = io.StringIO()
    stdin = io.StringIO("")
    exit_code = main(stdin=stdin, stdout=stdout, stderr=stderr, client=object())
    assert exit_code == 2
    assert "BEDROCK_MODEL_ID_TEXT" in stderr.getvalue()


def test_format_event_tool_call_matches_spec_shape():
    line = format_event(
        {"kind": "tool_call", "payload": {
            "tool_use_id": "tu-1",
            "name": "get_site_health",
            "input": {"cell_site_id": "SITE-07"},
        }},
        use_color=False,
    )
    assert line == "[tool_call] get_site_health(cell_site_id=SITE-07)"


def test_format_event_validator_matches_spec_shape():
    line = format_event(
        {"kind": "validator_decision", "payload": {
            "tool": "book_appointment",
            "input": {},
            "ok": False,
            "reason": "site in maintenance",
        }},
        use_color=False,
    )
    assert line == "[validator] ok=False reason='site in maintenance'"
