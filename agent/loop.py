"""Bedrock Converse tool-use loop.

The loop is deliberately provider-shaped (the input to `client.converse` is the
Bedrock Converse request; the output shape is the Bedrock response) so a real
`boto3.client("bedrock-runtime")` can be dropped in unchanged. Tests inject a
scripted fake with the same `.converse(**kwargs)` surface.

Every step is captured as a structured JSON event on the `StepLogger`. The
frontend replays that event stream — do not add prose logs here."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from agent.handlers import handle_tool_call
from tools.schema import TOOLS_BY_NAME

SYSTEM_PROMPT = """You are a telecom customer-care voice agent.

Rules you must follow:
- Before offering any troubleshooting advice for a service problem, call
  get_site_health or lookup_outage. A caller on a degraded or maintenance
  site is not experiencing a device problem — do not suggest device fixes.
- Confirm the account with get_account_status before proposing any write.
- book_appointment is a write and may be rejected by policy. If rejected,
  tell the caller the reason verbatim; do not retry silently.
- Escalate to a human on any request outside these tools.
- Speak in short, clear sentences. The caller hears your reply as speech."""

MAX_ITERATIONS = 6
DEFAULT_MAX_TOKENS = 1024


class BedrockConverseClient(Protocol):
    def converse(self, **kwargs: Any) -> dict[str, Any]: ...


@dataclass
class StepLogger:
    """In-memory structured event log. Frontend consumes `.events` verbatim.

    Each event: {"ts": iso8601, "kind": str, "payload": dict}. Optional `emit`
    callable is invoked per event for real-time observability (stdout, SSE)."""

    emit: Callable[[dict[str, Any]], None] | None = None
    events: list[dict[str, Any]] = field(default_factory=list)

    def log(self, kind: str, payload: dict[str, Any]) -> None:
        event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "kind": kind,
            "payload": payload,
        }
        self.events.append(event)
        if self.emit is not None:
            self.emit(event)


def run_turn(
    *,
    client: BedrockConverseClient,
    model_id: str,
    user_utterance: str,
    conversation: list[dict[str, Any]],
    context: dict[str, Any],
    logger: StepLogger,
    max_iterations: int = MAX_ITERATIONS,
) -> str:
    """Run one caller turn to completion. Mutates `conversation` in place so
    the caller can persist history across turns. Returns the assistant's final
    text reply."""

    conversation.append({"role": "user", "content": [{"text": user_utterance}]})
    logger.log("transcript", {"role": "user", "text": user_utterance})

    tool_specs = list(TOOLS_BY_NAME.values())

    for _ in range(max_iterations):
        response = client.converse(
            modelId=model_id,
            messages=conversation,
            system=[{"text": SYSTEM_PROMPT}],
            toolConfig={"tools": tool_specs, "toolChoice": {"auto": {}}},
            inferenceConfig={"temperature": 0.0, "maxTokens": DEFAULT_MAX_TOKENS},
        )

        assistant_message = response["output"]["message"]
        conversation.append(assistant_message)

        if response.get("stopReason") != "tool_use":
            reply = _extract_text(assistant_message)
            cleaned_reply = _strip_thinking(reply)
            logger.log("transcript", {
                "role": "assistant",
                "text": cleaned_reply,
                "raw_text": reply,
            })
            return cleaned_reply

        tool_result_blocks = []
        for block in assistant_message.get("content", []):
            tool_use = block.get("toolUse")
            if tool_use is None:
                continue

            logger.log("tool_call", {
                "tool_use_id": tool_use["toolUseId"],
                "name": tool_use["name"],
                "input": tool_use.get("input", {}),
            })

            result = handle_tool_call(
                tool_name=tool_use["name"],
                tool_input=tool_use.get("input", {}),
                context=context,
                logger=logger,
            )

            logger.log("tool_result", {
                "tool_use_id": tool_use["toolUseId"],
                "name": tool_use["name"],
                "status": result["status"],
                "content": result["content"],
            })

            tool_result_blocks.append({
                "toolResult": {
                    "toolUseId": tool_use["toolUseId"],
                    "content": [{"json": result["content"]}],
                    "status": _bedrock_tool_status(result["status"]),
                }
            })

        conversation.append({"role": "user", "content": tool_result_blocks})

    raise RuntimeError(
        f"tool-use loop did not converge within {max_iterations} iterations"
    )


def _bedrock_tool_status(status: str) -> str:
    """Map an internal handler status onto a Bedrock Converse `toolResult.status`.

    The Converse API accepts only "success" or "error". Our handlers also emit
    "rejected" for policy-declined writes; that nuance is preserved in the SSE
    `tool_result` event the frontend renders, but the block sent back to the
    model must collapse to "error". The rejection reason stays in `content`, so
    the model can still read it and explain the denial to the caller."""
    return "success" if status == "success" else "error"


def _extract_text(assistant_message: dict[str, Any]) -> str:
    parts = [
        block["text"]
        for block in assistant_message.get("content", [])
        if "text" in block
    ]
    return "\n".join(parts).strip()


def _strip_thinking(text: str) -> str:
    """Remove <thinking>...</thinking> blocks (including unclosed ones) and collapse whitespace."""
    # Remove thinking blocks: handle both closed and unclosed tags
    # Use DOTALL to match across newlines
    cleaned = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL)
    # Also handle unclosed thinking tags at the end
    cleaned = re.sub(r"<thinking>.*$", "", cleaned, flags=re.DOTALL)
    # Collapse multiple whitespace into single spaces, preserving single newlines semantically
    cleaned = re.sub(r" +", " ", cleaned)
    # Strip leading/trailing whitespace
    cleaned = cleaned.strip()
    return cleaned
