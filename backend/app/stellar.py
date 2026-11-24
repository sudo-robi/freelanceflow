import os

from httpx import AsyncClient, HTTPError

TESTNET_PASSPHRASE = "Test SDF Network ; September 2015"
HORIZON_URL = os.getenv("STELLAR_HORIZON_URL", "https://horizon-testnet.stellar.org")
SOROBAN_RPC_URL = os.getenv("SOROBAN_RPC_URL", "https://soroban-testnet.stellar.org")


async def get_testnet_account(address: str) -> dict:
    async with AsyncClient(timeout=15) as client:
        response = await client.get(f"{HORIZON_URL}/accounts/{address}")
        response.raise_for_status()
        return response.json()


async def get_transaction(transaction_hash: str) -> dict:
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
