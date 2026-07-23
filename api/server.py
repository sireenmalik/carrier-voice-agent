from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any, Iterator

import boto3
from botocore.exceptions import AccessDeniedException, ValidationException, ThrottlingException
from fastapi import FastAPI, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.loop import StepLogger, run_turn


class TurnRequest(BaseModel):
    utterance: str
    session_id: str


def _fresh_session_id() -> str:
    return uuid.uuid4().hex[:8]


def _sanitize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


class FakeBedrock:
    def __init__(self) -> None:
        self.counter = 0

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        self.counter += 1
        messages = kwargs.get("messages", [])
        last_user = None
        for message in reversed(messages):
            if message.get("role") == "user":
                last_user = message
                break

        if last_user is None:
            return self._text_response("I didn't receive a user message.")

        if any("toolResult" in block for block in last_user.get("content", [])):
            return self._follow_up_response(last_user)

        utterance = " ".join(
            block.get("text", "")
            for block in last_user.get("content", [])
            if "text" in block
        )
        tool_name, tool_input = self._choose_tool(utterance)
        return self._tool_use_response(tool_name, tool_input)

    def _choose_tool(self, utterance: str) -> tuple[str, dict[str, Any]]:
        # Normalize intent tokens
        normalized = utterance.lower()

        # Prefer real synthetic IDs used by the simulator so handlers succeed.
        # Pick a healthy site deterministically from sim.network.all_sites().
        try:
            from sim.network import all_sites
            import random
            healthy_sites = [s for s, status in all_sites().items() if status == "healthy"]
            if healthy_sites:
                cell_site = random.Random(42).choice(healthy_sites)
            else:
                cell_site = "SITE-001"
        except Exception:
            cell_site = "SITE-001"

        # Use a valid account id present in sim.accounts
        account_id = "ACC-1003"

        # Use a ZIP that exists in sim/outages
        zip_code = "94103"

        if any(token in normalized for token in ("book", "appointment", "schedule")):
            return "book_appointment", {
                "account_id": account_id,
                "slot": "2026-07-20T10:00:00",
            }
        if any(token in normalized for token in ("account", "balance", "plan")):
            return "get_account_status", {"account_id": account_id}
        if any(token in normalized for token in ("outage", "incident", "zip")):
            return "lookup_outage", {"zip_code": zip_code}
        if any(token in normalized for token in ("human", "agent", "escalate")):
            return "escalate_to_human", {"reason": utterance or "The caller requested a human."}
        return "get_site_health", {"cell_site_id": cell_site}

    def _follow_up_response(self, user_message: dict[str, Any]) -> dict[str, Any]:
        tool_result = None
        for block in user_message.get("content", []):
            if "toolResult" in block:
                tool_result = block["toolResult"]
                break

        if tool_result is None:
            return self._text_response("I have an update for you.")

        payload = tool_result.get("content", [])
        details = payload[0].get("json") if payload else {}
        if tool_result.get("status") == "success":
            return self._text_response(self._compose_tool_reply(details))
        return self._text_response("I couldn't complete that action.")

    def _compose_tool_reply(self, details: dict[str, Any]) -> str:
        if details.get("health"):
            return f"Your tower {details['cell_site_id']} is {details['health']}."
        if details.get("balance") is not None:
            return f"Your account {details['account_id']} has a balance of ${details['balance']:.2f}."
        if details.get("incidents") is not None:
            incidents = details["incidents"]
            if not incidents:
                return f"There are no active incidents for {details['zip_code']}."
            return f"Found {len(incidents)} active incident(s) for {details['zip_code']}."
        if details.get("booked") is True:
            return f"Appointment booked for {details['slot']} with confirmation {details['confirmation']}."
        if details.get("booked") is False:
            return f"I couldn't book that appointment: {details['reason']}"
        if details.get("escalated"):
            return "I am escalating you to a human now."
        return "Okay, I have an update for you."

    def _tool_use_response(self, name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        return {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": f"tu-{self.counter}",
                                "name": name,
                                "input": tool_input,
                            }
                        }
                    ],
                }
            },
            "stopReason": "tool_use",
        }

    def _text_response(self, text: str) -> dict[str, Any]:
        return {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": _sanitize_text(text)}],
                }
            },
            "stopReason": "end_turn",
        }


class RealBedrockClient:
    """Wraps real boto3 Bedrock client with the same interface as FakeBedrock."""

    def __init__(self, boto_client: Any, model_id: str) -> None:
        self.boto_client = boto_client
        self.model_id = model_id

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        """Call Bedrock Converse API and return response in standard format."""
        try:
            # Extract only the parameters Converse API expects
            converse_params = {
                "modelId": kwargs.get("modelId"),
                "messages": kwargs.get("messages", []),
                "system": kwargs.get("system", []),
                "toolConfig": kwargs.get("toolConfig"),
                "inferenceConfig": {
                    "temperature": 0.0,
                    "topP": 1.0,
                    "maxTokens": kwargs.get("inferenceConfig", {}).get("maxTokens", 1024),
                },
            }
            response = self.boto_client.converse(**converse_params)
            return response
        except AccessDeniedException as e:
            return self._error_response(f"Access denied: {str(e)}")
        except ValidationException as e:
            return self._error_response(f"Validation error: {str(e)}")
        except ThrottlingException as e:
            return self._error_response(f"Request throttled: {str(e)}")
        except Exception as e:
            return self._error_response(f"Bedrock error: {str(e)}")

    def _error_response(self, error_message: str) -> dict[str, Any]:
        """Return an error response in standard format."""
        return {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": error_message}],
                }
            },
            "stopReason": "end_turn",
        }


BEDROCK_MODEL_ID_TEXT = os.environ.get("BEDROCK_MODEL_ID_TEXT")
AWS_REGION = os.environ.get("AWS_REGION")
MODEL_ID = BEDROCK_MODEL_ID_TEXT or "fake-model"

if BEDROCK_MODEL_ID_TEXT and BEDROCK_MODEL_ID_TEXT.strip():
    boto_client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
    bedrock_client = RealBedrockClient(boto_client, BEDROCK_MODEL_ID_TEXT)
else:
    bedrock_client = FakeBedrock()

SESSION_STATE: dict[str, dict[str, Any]] = {}

app = FastAPI(title="Carrier Voice Agent Dev API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def _get_session(session_id: str) -> dict[str, Any]:
    return SESSION_STATE.setdefault(session_id, {"conversation": [], "context": {}})


def _event_generator(session_id: str, utterance: str) -> Iterator[str]:
    session = _get_session(session_id)
    logger = StepLogger()
    events: list[dict[str, Any]] = []

    def collect(event: dict[str, Any]) -> None:
        events.append(event)

    logger.emit = collect

    run_turn(
        client=bedrock_client,
        model_id=MODEL_ID,
        user_utterance=utterance,
        conversation=session["conversation"],
        context=session["context"],
        logger=logger,
    )

    for event in events:
        yield f"data: {json.dumps(event)}\n\n"


@app.post("/turn")
async def post_turn(body: TurnRequest = Body(...)) -> StreamingResponse:
    if not body.session_id or not body.utterance:
        raise ValueError("session_id and utterance are required")
    return StreamingResponse(
        _event_generator(body.session_id, body.utterance),
        media_type="text/event-stream",
    )


@app.get("/turn")
async def get_turn(session_id: str = Query(...), utterance: str = Query(...)) -> StreamingResponse:
    return StreamingResponse(
        _event_generator(session_id, utterance),
        media_type="text/event-stream",
    )


@app.get("/session")
async def session() -> dict[str, str]:
    return {"session_id": _fresh_session_id()}
