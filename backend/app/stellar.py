import asyncio
import os
import time

from httpx import AsyncClient, HTTPError

TESTNET_PASSPHRASE = "Test SDF Network ; September 2015"
HORIZON_URL = os.getenv("STELLAR_HORIZON_URL", "https://horizon-testnet.stellar.org")
SOROBAN_RPC_URL = os.getenv("SOROBAN_RPC_URL", "https://soroban-testnet.stellar.org")
HORIZON_ATTEMPTS = max(1, int(os.getenv("HORIZON_VERIFY_ATTEMPTS", "2")))
HORIZON_RETRY_DELAY = float(os.getenv("HORIZON_RETRY_DELAY", "0.25"))
PASSPHRASE_CACHE_TTL = float(os.getenv("PASSPHRASE_CACHE_TTL", "300"))

_passphrase_cache: str | None = None
_passphrase_cached_at: float = 0.0


async def get_testnet_account(address: str) -> dict:
    async with AsyncClient(timeout=15) as client:
        response = await client.get(f"{HORIZON_URL}/accounts/{address}")
        response.raise_for_status()
        return response.json()


async def get_network_passphrase() -> str:
    """Read the live network passphrase from Soroban RPC, with a short cache."""
    global _passphrase_cache, _passphrase_cached_at
    now = time.monotonic()
    if _passphrase_cache and now - _passphrase_cached_at < PASSPHRASE_CACHE_TTL:
        return _passphrase_cache
    async with AsyncClient(timeout=10) as client:
        response = await client.post(
            SOROBAN_RPC_URL,
            json={"jsonrpc": "2.0", "id": 1, "method": "getNetwork"},
        )
        response.raise_for_status()
        payload = response.json()
    passphrase = payload.get("result", {}).get("passphrase")
    if not passphrase:
        raise RuntimeError("Soroban RPC did not return a network passphrase")
    _passphrase_cache = passphrase
    _passphrase_cached_at = now
    return passphrase


async def _fetch_transaction(transaction_hash: str) -> dict:
    async with AsyncClient(timeout=15) as client:
        response = await client.get(f"{HORIZON_URL}/transactions/{transaction_hash}")
        if response.status_code == 404:
            return {"found": False, "status": "not_found"}
        response.raise_for_status()
        data = response.json()
        operations_response = await client.get(
            f"{HORIZON_URL}/transactions/{transaction_hash}/operations",
            params={"limit": 200},
        )
        operations_response.raise_for_status()
        operations = operations_response.json().get("_embedded", {}).get("records", [])
        return {
            "found": True,
            "successful": data.get("successful") is True,
            "ledger": data.get("ledger_attr") or data.get("ledger"),
            "created_at": data.get("created_at"),
            "source_account": data.get("source_account"),
            "fee_account": data.get("fee_account"),
            "memo": data.get("memo"),
            "operations": [
                {
                    "type": item.get("type"),
                    "from": item.get("from"),
                    "to": item.get("to"),
                    "amount": item.get("amount"),
                    "asset_type": item.get("asset_type"),
                    "asset_code": item.get("asset_code"),
                    "asset_issuer": item.get("asset_issuer"),
                }
                for item in operations
            ],
        }


async def get_transaction(transaction_hash: str) -> dict:
    """Fetch a transaction with bounded retries for transient 'not found' results."""
    last: dict | None = None
    for attempt in range(HORIZON_ATTEMPTS):
        try:
            result = await _fetch_transaction(transaction_hash)
        except HTTPError:
            if attempt + 1 < HORIZON_ATTEMPTS:
                await asyncio.sleep(HORIZON_RETRY_DELAY)
                continue
            raise
        if result.get("found") or attempt + 1 >= HORIZON_ATTEMPTS:
            return result
        last = result
        await asyncio.sleep(HORIZON_RETRY_DELAY)
    return last or {"found": False, "status": "not_found"}
