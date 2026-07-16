"""Simulator is the ground truth for network state in the demo — if it drifts
between runs, every downstream test drifts with it."""

from __future__ import annotations

import importlib
from collections import Counter

import pytest

from sim import network


def test_exactly_twenty_sites():
    assert len(network.all_sites()) == 20


def test_site_ids_are_padded_and_sequential():
    expected = {f"SITE-{i:03d}" for i in range(1, 21)}
    assert set(network.all_sites()) == expected


def test_status_distribution_is_fifteen_three_two():
    counts = Counter(network.all_sites().values())
    assert counts == {"healthy": 15, "degraded": 3, "maintenance": 2}


def test_get_site_health_returns_expected_status():
    for site_id, status in network.all_sites().items():
        assert network.get_site_health(site_id) == status


def test_get_site_health_unknown_raises_key_error():
    with pytest.raises(KeyError):
        network.get_site_health("SITE-999")


def test_deterministic_across_reimport():
    before = dict(network.all_sites())
    reloaded = importlib.reload(network)
    after = dict(reloaded.all_sites())
    assert before == after


def test_all_sites_is_read_only():
    with pytest.raises(TypeError):
        network.all_sites()["SITE-001"] = "maintenance"  # type: ignore[index]
