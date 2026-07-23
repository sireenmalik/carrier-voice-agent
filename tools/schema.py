"""Bedrock Converse API tool-use schemas. Pass `TOOLS` as the `tools` field
of a `toolConfig` on `bedrock-runtime.converse` / `converse_stream`."""

from __future__ import annotations

from typing import Any, Final

TOOLS: Final[list[dict[str, Any]]] = [
    {
        "toolSpec": {
            "name": "get_site_health",
            "description": (
                "Return the current health status of a cell site: healthy, "
                "degraded, or maintenance. Call this before promising any "
                "troubleshooting or device advice — a caller on a maintenance "
                "site is not experiencing a device problem. The cell_site_id comes "
                "from get_account_status; callers do not know their own site ID."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "cell_site_id": {
                            "type": "string",
                            "description": "Cell site identifier, e.g. SITE-001.",
                        }
                    },
                    "required": ["cell_site_id"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_account_status",
            "description": "Return plan, current balance, and the cell site currently serving a customer account. Use this to obtain the cell_site_id needed for get_site_health.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "account_id": {
                            "type": "string",
                            "description": "Customer account identifier, e.g. ACC-1001.",
                        }
                    },
                    "required": ["account_id"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "lookup_outage",
            "description": "Return any active network incidents affecting a ZIP code.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "zip_code": {
                            "type": "string",
                            "pattern": "^[0-9]{5}$",
                            "description": "5-digit US ZIP code.",
                        }
                    },
                    "required": ["zip_code"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "book_appointment",
            "description": (
                "Book a service appointment for an account at a specific slot. "
                "This is a write; the validator may reject it, in which case "
                "surface the rejection reason to the caller verbatim."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "account_id": {
                            "type": "string",
                            "description": "Customer account identifier.",
                        },
                        "slot": {
                            "type": "string",
                            "format": "date-time",
                            "description": (
                                "ISO 8601 datetime for the appointment slot, "
                                "e.g. 2026-07-20T10:00:00."
                            ),
                        },
                    },
                    "required": ["account_id", "slot"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "escalate_to_human",
            "description": (
                "Route the call to a human agent. Use when confidence is low, "
                "the caller is distressed, or the request is outside scope."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "reason": {
                            "type": "string",
                            "description": "One-sentence reason for the escalation.",
                        }
                    },
                    "required": ["reason"],
                }
            },
        }
    },
]

TOOLS_BY_NAME: Final[dict[str, dict[str, Any]]] = {
    tool["toolSpec"]["name"]: tool for tool in TOOLS
}
