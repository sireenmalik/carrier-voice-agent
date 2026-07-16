"""Synthetic network incidents keyed by ZIP. Five fixed incidents so the demo
narrative — "your area has an outage, ETA X" — is reproducible."""

from __future__ import annotations

from types import MappingProxyType
from typing import Final, Literal, Mapping, TypedDict

Severity = Literal["minor", "major", "critical"]


class Incident(TypedDict):
    incident_id: str
    zip_code: str
    started_at: str
    estimated_restore: str
    affected_services: list[str]
    severity: Severity
    description: str


_INCIDENTS_RAW: dict[str, list[Incident]] = {
    "94103": [{
        "incident_id": "INC-1001",
        "zip_code": "94103",
        "started_at": "2026-07-16T04:12:00Z",
        "estimated_restore": "2026-07-16T18:00:00Z",
        "affected_services": ["voice", "data"],
        "severity": "major",
        "description": "Fiber cut near SoMa impacting SITE-004.",
    }],
    "10001": [{
        "incident_id": "INC-1002",
        "zip_code": "10001",
        "started_at": "2026-07-16T09:30:00Z",
        "estimated_restore": "2026-07-16T13:00:00Z",
        "affected_services": ["data"],
        "severity": "minor",
        "description": "Backhaul congestion on Chelsea sector.",
    }],
    "60614": [{
        "incident_id": "INC-1003",
        "zip_code": "60614",
        "started_at": "2026-07-16T02:05:00Z",
        "estimated_restore": "2026-07-16T20:00:00Z",
        "affected_services": ["voice", "data", "sms"],
        "severity": "critical",
        "description": "Power failure at Lincoln Park macro; on generator.",
    }],
    "77002": [{
        "incident_id": "INC-1004",
        "zip_code": "77002",
        "started_at": "2026-07-15T22:40:00Z",
        "estimated_restore": "2026-07-16T09:00:00Z",
        "affected_services": ["voice"],
        "severity": "minor",
        "description": "Scheduled downtown maintenance window.",
    }],
    "98101": [{
        "incident_id": "INC-1005",
        "zip_code": "98101",
        "started_at": "2026-07-16T11:15:00Z",
        "estimated_restore": "2026-07-16T15:30:00Z",
        "affected_services": ["data"],
        "severity": "major",
        "description": "Transport ring degradation affecting downtown Seattle.",
    }],
}

_INCIDENTS: Final[Mapping[str, tuple[Incident, ...]]] = MappingProxyType(
    {zip_code: tuple(incidents) for zip_code, incidents in _INCIDENTS_RAW.items()}
)


def get_incidents(zip_code: str) -> list[Incident]:
    """Return a fresh list of active incidents for a ZIP (empty if none).

    Returns a new list per call so callers can freely mutate the result."""
    return [dict(inc) for inc in _INCIDENTS.get(zip_code, ())]


def all_incidents() -> Mapping[str, tuple[Incident, ...]]:
    return _INCIDENTS
