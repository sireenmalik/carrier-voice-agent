"""Unit tests for tool handlers."""

from __future__ import annotations

from agent.handlers import _handle_get_account_status
from sim.accounts import all_accounts
from sim.network import all_sites


def test_get_account_status_returns_cell_site_id_for_all_accounts():
    """Verify that get_account_status returns a valid cell_site_id for every synthetic account."""
    valid_sites = set(all_sites().keys())
    
    for account_id, account_data in all_accounts().items():
        result = _handle_get_account_status(
            {"account_id": account_id},
            context={},
            logger=None,
        )
        
        # Verify the call succeeded
        assert result["status"] == "success", f"Failed for {account_id}: {result}"
        
        content = result["content"]
        
        # Verify all expected fields are present
        assert "account_id" in content, f"{account_id}: missing account_id"
        assert "plan" in content, f"{account_id}: missing plan"
        assert "balance" in content, f"{account_id}: missing balance"
        assert "cell_site_id" in content, f"{account_id}: missing cell_site_id"
        
        # Verify the cell_site_id is valid
        cell_site_id = content["cell_site_id"]
        assert cell_site_id in valid_sites, (
            f"{account_id}: cell_site_id={cell_site_id} not in simulator site list"
        )
        
        # Verify it matches the original account data
        assert content["cell_site_id"] == account_data["cell_site_id"]
