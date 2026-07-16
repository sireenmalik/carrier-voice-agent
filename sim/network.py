"""Synthetic network simulator: 20 cell sites, deterministic health mix."""

from __future__ import annotations

import random
from types import MappingProxyType
from typing import Final, Literal, Mapping

SiteHealth = Literal["healthy", "degraded", "maintenance"]

_SEED: Final = 42
_SITE_COUNT: Final = 20
_HEALTHY_COUNT: Final = 15
_DEGRADED_COUNT: Final = 3
_MAINTENANCE_COUNT: Final = 2

assert _HEALTHY_COUNT + _DEGRADED_COUNT + _MAINTENANCE_COUNT == _SITE_COUNT


def _build_site_health() -> dict[str, SiteHealth]:
    site_ids = [f"SITE-{i:03d}" for i in range(1, _SITE_COUNT + 1)]
    statuses: list[SiteHealth] = (
        ["healthy"] * _HEALTHY_COUNT
        + ["degraded"] * _DEGRADED_COUNT
        + ["maintenance"] * _MAINTENANCE_COUNT
    )
    random.Random(_SEED).shuffle(statuses)
    return dict(zip(site_ids, statuses))


_SITE_HEALTH: Final[Mapping[str, SiteHealth]] = MappingProxyType(_build_site_health())


def get_site_health(cell_site_id: str) -> SiteHealth:
    try:
        return _SITE_HEALTH[cell_site_id]
    except KeyError:
        raise KeyError(f"unknown cell site: {cell_site_id!r}") from None


def all_sites() -> Mapping[str, SiteHealth]:
    return _SITE_HEALTH
