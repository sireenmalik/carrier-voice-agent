"""Stdin-driven REPL for the carrier voice agent.

Reads AWS_REGION and BEDROCK_MODEL_ID_TEXT from the environment, opens one
`bedrock-runtime` client, and drives `run_turn` on each line of stdin. The
StepLogger emit callback prints each event as a one-line coloured summary so
an operator watching the terminal sees the same replay stream the frontend
will render.

Every arg on `main(...)` is injectable so the test suite can wire in a fake
Bedrock client, in-memory stdin/stdout, and a list-capturing emit."""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Callable, TextIO

from agent.loop import StepLogger, run_turn

_ANSI: dict[str, str] = {
    "reset":  "\x1b[0m",
    "cyan":   "\x1b[36m",
    "green":  "\x1b[32m",
    "yellow": "\x1b[33m",
    "gray":   "\x1b[90m",
    "blue":   "\x1b[34m",
    "red":    "\x1b[31m",
}

_ANSI_STRIP = re.compile(r"\x1b\[[0-9;]*m")

_CONTENT_TRUNCATE = 160


def _color(color: str, text: str, use_color: bool) -> str:
    if not use_color:
        return text
    return f"{_ANSI[color]}{text}{_ANSI['reset']}"


def _fmt_content(obj: Any) -> str:
    dumped = json.dumps(obj, default=str, sort_keys=True)
    if len(dumped) <= _CONTENT_TRUNCATE:
        return dumped
    return dumped[: _CONTENT_TRUNCATE - 3] + "..."


def format_event(event: dict[str, Any], *, use_color: bool = True) -> str:
    """One-line human summary of a StepLogger event."""
    kind = event["kind"]
    payload = event["payload"]

    if kind == "transcript":
        role = payload["role"]
        color = "cyan" if role == "user" else "green"
        return _color(color, f"[{role}] {payload['text']}", use_color)

    if kind == "tool_call":
        args = payload.get("input", {})
        args_str = ", ".join(f"{k}={v}" for k, v in args.items())
        return _color(
            "yellow",
            f"[tool_call] {payload['name']}({args_str})",
            use_color,
        )

    if kind == "tool_result":
        return _color(
            "gray",
            f"[tool_result] {payload['name']} status={payload['status']} "
            f"content={_fmt_content(payload.get('content', {}))}",
            use_color,
        )

    if kind == "validator_decision":
        ok = payload.get("ok")
        color = "blue" if ok else "red"
        return _color(
            color,
            f"[validator] ok={ok} reason={payload.get('reason', '')!r}",
            use_color,
        )

    return f"[{kind}] {_fmt_content(payload)}"


def _make_stdout_emit(stream: TextIO, use_color: bool) -> Callable[[dict[str, Any]], None]:
    def emit(event: dict[str, Any]) -> None:
        line = format_event(event, use_color=use_color)
        if not use_color:
            line = _ANSI_STRIP.sub("", line)
        stream.write(line + "\n")
        stream.flush()
    return emit


_BANNER = "carrier-voice-agent REPL — type 'quit' or Ctrl-D to exit."
_PROMPT = "> "


def main(
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    client: Any | None = None,
    model_id: str | None = None,
    region: str | None = None,
    emit: Callable[[dict[str, Any]], None] | None = None,
) -> int:
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout
    stderr = stderr if stderr is not None else sys.stderr

    region = region or os.environ.get("AWS_REGION", "us-east-1")
    model_id = model_id or os.environ.get("BEDROCK_MODEL_ID_TEXT")
    if not model_id:
        stderr.write("[fatal] BEDROCK_MODEL_ID_TEXT is not set\n")
        return 2

    if client is None:
        import boto3  # local import so tests never require boto3 to be installed
        client = boto3.client("bedrock-runtime", region_name=region)

    if emit is None:
        emit = _make_stdout_emit(stdout, use_color=stdout.isatty())

    conversation: list[dict[str, Any]] = []

    stdout.write(_BANNER + "\n")
    stdout.write(_PROMPT)
    stdout.flush()

    for line in stdin:
        utterance = line.strip()
        if not utterance:
            stdout.write(_PROMPT)
            stdout.flush()
            continue
        if utterance.lower() in ("quit", "exit"):
            break

        logger = StepLogger(emit=emit)
        try:
            run_turn(
                client=client,
                model_id=model_id,
                user_utterance=utterance,
                conversation=conversation,
                context={},
                logger=logger,
            )
        except Exception as exc:  # noqa: BLE001 — REPL must survive per-turn errors
            stderr.write(f"[error] {type(exc).__name__}: {exc}\n")
            stderr.flush()

        stdout.write(_PROMPT)
        stdout.flush()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
