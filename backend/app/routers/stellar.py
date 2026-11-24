"""Read-only Stellar Testnet network metadata and independent verification."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User
from ..stellar import HORIZON_URL, SOROBAN_RPC_URL, TESTNET_PASSPHRASE, get_transaction

router = APIRouter(prefix="/api", tags=["stellar"])


@router.get("/stellar/network")
def network_info():
    return {
        "network": "testnet",
        "network_passphrase": TESTNET_PASSPHRASE,
        "horizon_url": HORIZON_URL,
        "soroban_rpc_url": SOROBAN_RPC_URL,
        "native_asset": "XLM",
    }


@router.get("/stellar/transaction/{transaction_hash}")
async def verify_stellar_transaction(
    transaction_hash: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if len(transaction_hash) != 64 or any(character not in "0123456789abcdef" for character in transaction_hash.lower()):
        raise HTTPException(status_code=422, detail="Invalid Stellar transaction hash")
    try:
        result = await get_transaction(transaction_hash)
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Horizon verification failed: {error}") from error
    if not result.get("found") or not result.get("successful"):
        raise HTTPException(status_code=404, detail="Transaction not found on Testnet or not successful")
    return {
        "hash": transaction_hash,
        "network": "testnet",
        "network_passphrase": TESTNET_PASSPHRASE,
        "verified_against": HORIZON_URL,
        **result,
    }
