"""Synthetic accounts table. Assignments are derived from the deterministic
network mapping so at least one account lives on each site status."""

from __future__ import annotations

from types import MappingProxyType
from typing import Final, Literal, Mapping, TypedDict

from sim.network import SiteHealth, all_sites


class Account(TypedDict):
    plan: Literal["postpaid", "prepaid"]
    balance: float
    cell_site_id: str


def _sites_by_status() -> dict[SiteHealth, list[str]]:
    buckets: dict[SiteHealth, list[str]] = {"healthy": [], "degraded": [], "maintenance": []}
    for site_id, status in all_sites().items():
        buckets[status].append(site_id)
    for bucket in buckets.values():
        bucket.sort()
    return buckets


def _build_accounts() -> dict[str, Account]:
    by_status = _sites_by_status()
    healthy = by_status["healthy"]
    degraded = by_status["degraded"]
    maintenance = by_status["maintenance"]
    return {
        "ACC-1001": {"plan": "postpaid", "balance": 42.50,  "cell_site_id": healthy[0]},
        "ACC-1002": {"plan": "postpaid", "balance": 128.00, "cell_site_id": healthy[1]},
        "ACC-1003": {"plan": "prepaid",  "balance": 0.00,   "cell_site_id": healthy[2]},
        "ACC-1004": {"plan": "postpaid", "balance": 15.75,  "cell_site_id": healthy[3]},
        "ACC-1005": {"plan": "prepaid",  "balance": 25.00,  "cell_site_id": healthy[4]},
        "ACC-1006": {"plan": "postpaid", "balance": 60.00,  "cell_site_id": healthy[5]},
        "ACC-1007": {"plan": "postpaid", "balance": 90.00,  "cell_site_id": degraded[0]},
        "ACC-1008": {"plan": "prepaid",  "balance": 5.00,   "cell_site_id": degraded[1]},
        "ACC-1009": {"plan": "postpaid", "balance": 33.00,  "cell_site_id": maintenance[0]},
        "ACC-1010": {"plan": "postpaid", "balance": 12.50,  "cell_site_id": maintenance[1]},
    }


_ACCOUNTS: Final[Mapping[str, Account]] = MappingProxyType(_build_accounts())


def get_account(account_id: str) -> Account | None:
    return _ACCOUNTS.get(account_id)


def all_accounts() -> Mapping[str, Account]:
    return _ACCOUNTS
