"""Soroban escrow verification client.

This module never signs transactions or handles secrets. It reads the live
contract state and parses submitted transaction envelopes to verify that an
application state change corresponds to a real Testnet contract invocation.
"""

import hashlib
import os

from stellar_sdk import SorobanServerAsync, xdr
from stellar_sdk.exceptions import SorobanRpcErrorResponse

from .stellar import TESTNET_PASSPHRASE

CONTRACT_ID = os.getenv(
    "SOROBAN_ESCROW_CONTRACT_ID",
    "CA5FBQ4VEJ4ZXGVDVMAGRP6JKEB7AGUUG5ZR3NYSNG3A6XFUUVCL37CI",
)
RPC_URL = os.getenv("SOROBAN_RPC_URL", "https://soroban-testnet.stellar.org")

FUNCTION_FOR_ACTION = {
    "create": "create_agreement",
    "accept": "accept_agreement",
    "fund": "fund",
    "approve": "approve_milestone",
    "release": "release_milestone",
    "cancel": "cancel",
    "dispute": "open_dispute",
}


class EscrowVerificationError(Exception):
    pass


def agreement_id(agreement_uuid: str) -> bytes:
    return hashlib.sha256(f"freelanceflow:agreement:{agreement_uuid}".encode()).digest()


def _contract_address() -> xdr.SCAddress:
    from stellar_sdk import Address

    contract_hash = xdr.Hash(Address(CONTRACT_ID).to_xdr_sc_address().contract_id.contract_id.hash)
    return xdr.SCAddress(
        type=xdr.SCAddressType.SC_ADDRESS_TYPE_CONTRACT,
        contract_id=xdr.ContractID(contract_hash),
    )


async def verify_network() -> None:
    async with SorobanServerAsync(RPC_URL) as server:
        network = await server.get_network()
    if network.passphrase != TESTNET_PASSPHRASE:
        raise EscrowVerificationError("Escrow RPC is not configured for Stellar Testnet")


def verify_invoke_transaction(envelope_xdr: str, action: str, expected_agreement_id: bytes) -> dict:
    """Verify that a submitted transaction invoked the expected escrow function."""
    expected_function = FUNCTION_FOR_ACTION.get(action)
    if not expected_function:
        raise EscrowVerificationError("Unsupported escrow action")
    try:
        envelope = xdr.TransactionEnvelope.from_xdr(envelope_xdr)
    except Exception as error:
        raise EscrowVerificationError("Transaction envelope could not be parsed") from error

    operations = []
    try:
        operations = envelope.v1.tx.operations
    except AttributeError:
        pass
    for operation in operations:
        body = operation.body
        if body.type != xdr.OperationType.INVOKE_HOST_FUNCTION:
            continue
        host = body.invoke_host_function_op.host_function
        if host.type != xdr.HostFunctionType.HOST_FUNCTION_TYPE_INVOKE_CONTRACT:
            continue
        invoke = host.invoke_contract
        try:
            contract_id = invoke.contract_address.contract_id.contract_id.hash.hex()
            raw_name = invoke.function_name.sc_symbol
            function_name = raw_name.decode() if isinstance(raw_name, bytes) else str(raw_name)
        except AttributeError:
            continue
        if contract_id != _contract_hash_hex() or function_name != expected_function:
            continue
        if invoke.args and expected_agreement_id not in _scval_bytes(invoke.args[0]):
            continue
        return {"contract_id": CONTRACT_ID, "function": function_name, "agreement_id": expected_agreement_id.hex()}
    raise EscrowVerificationError("Transaction does not invoke the expected escrow function")


def _contract_hash_hex() -> str:
    from stellar_sdk import Address

    return Address(CONTRACT_ID).to_xdr_sc_address().contract_id.contract_id.hash.hex()


def _scval_bytes(value: xdr.SCVal) -> list[bytes]:
    found: list[bytes] = []
    if getattr(value, "type", None) == xdr.SCValType.SCV_BYTES and value.bytes:
        found.append(bytes(value.bytes.sc_bytes))
    if getattr(value, "type", None) == xdr.SCValType.SCV_VEC and value.vec:
        for item in value.vec.sc_vec:
            found.extend(_scval_bytes(item))
    return found


async def verify_transaction(transaction_hash: str, action: str, agreement_uuid: str) -> dict:
    await verify_network()
    async with SorobanServerAsync(RPC_URL) as server:
        try:
            result = await server.get_transaction(transaction_hash)
        except SorobanRpcErrorResponse as error:
            raise EscrowVerificationError("Escrow transaction lookup failed") from error
    if str(getattr(result, "status", "")).upper() != "SUCCESS":
        raise EscrowVerificationError("Escrow transaction was not successful on Testnet")
    envelope_xdr = getattr(result, "envelope_xdr", None)
    if not envelope_xdr:
        raise EscrowVerificationError("Escrow transaction envelope is unavailable")
    verified = verify_invoke_transaction(envelope_xdr, action, agreement_id(agreement_uuid))
    verified.update({"transaction_hash": transaction_hash, "ledger": getattr(result, "ledger", None)})
    return verified


async def read_agreement_state(agreement_uuid: str) -> dict | None:
    """Read the stored Agreement struct from the deployed contract."""
    await verify_network()
    key = xdr.SCVal(
        type=xdr.SCValType.SCV_VEC,
        vec=xdr.SCVec([
            xdr.SCVal(type=xdr.SCValType.SCV_SYMBOL, sym=xdr.SCSymbol(b"Agreement")),
            xdr.SCVal(type=xdr.SCValType.SCV_BYTES, bytes=xdr.SCBytes(agreement_id(agreement_uuid))),
        ]),
    )
    ledger_key = xdr.LedgerKey(
        type=xdr.LedgerEntryType.CONTRACT_DATA,
        contract_data=xdr.LedgerKeyContractData(
            contract=_contract_address(),
            key=key,
            durability=xdr.ContractDataDurability.PERSISTENT,
        ),
    )
    async with SorobanServerAsync(RPC_URL) as server:
        result = await server.get_ledger_entries([ledger_key])
    entries = getattr(result, "entries", None) or []
    if not entries:
        return None
    return _decode_agreement_entry(entries[0])


def _decode_agreement_entry(entry) -> dict:
    data = getattr(entry, "data", None) or entry
    val = getattr(data, "val", None)
    if val is None:
        return {"raw": str(entry)}
    result = {}
    if getattr(val, "type", None) == xdr.SCValType.SCV_MAP and val.map:
        for item in val.map.entries:
            name = getattr(item.key, "sym", None)
            if name is None:
                continue
            result[str(name).replace("_v0", "")] = _decode_scval(item.val)
    return result


def _decode_scval(value: xdr.SCVal):
    kind = getattr(value, "type", None)
    if kind == xdr.SCValType.SCV_BOOL:
        return bool(value.b)
    if kind == xdr.SCValType.SCV_I64:
        return int(value.i64)
    if kind == xdr.SCValType.SCV_ADDRESS:
        return str(value.address)
    return value.to_xdr()
