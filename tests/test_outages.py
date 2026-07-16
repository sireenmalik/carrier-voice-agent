"""Outage sim is fixed data — five ZIPs, one incident each. Assertions match
the demo narrative; if a ZIP disappears, a scripted demo breaks silently."""

from __future__ import annotations

from sim.outages import all_incidents, get_incidents


def test_exactly_five_zips_seeded():
    assert len(all_incidents()) == 5


def test_get_incidents_known_zip_returns_seeded_incident():
    incidents = get_incidents("94103")
    assert len(incidents) == 1
    incident = incidents[0]
    assert incident["zip_code"] == "94103"
    assert incident["severity"] == "major"
    assert "voice" in incident["affected_services"]
    assert incident["incident_id"] == "INC-1001"


def test_get_incidents_unknown_zip_returns_empty_list():
    assert get_incidents("00000") == []


def test_get_incidents_is_deterministic_across_calls():
    assert get_incidents("60614") == get_incidents("60614")


def test_get_incidents_returns_a_fresh_list_that_is_safe_to_mutate():
    first = get_incidents("10001")
    first.append({"incident_id": "TAMPER"})  # type: ignore[arg-type]
    first[0]["description"] = "tampered"
    second = get_incidents("10001")
    assert len(second) == 1
    assert second[0]["description"] != "tampered"


def test_every_incident_has_required_fields():
    required = {
        "incident_id",
        "zip_code",
        "started_at",
        "estimated_restore",
        "affected_services",
        "severity",
        "description",
    }
    for zip_code, incidents in all_incidents().items():
        for incident in incidents:
            assert required <= set(incident), f"{zip_code}: missing {required - set(incident)}"


def test_incident_ids_are_unique():
    ids = [
        incident["incident_id"]
        for incidents in all_incidents().values()
        for incident in incidents
    ]
    assert len(ids) == len(set(ids))
