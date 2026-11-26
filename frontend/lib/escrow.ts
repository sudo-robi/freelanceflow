import {
  Account,
  Address,
  Asset,
  Contract,
  Memo,
  Networks,
  Transaction,
  TransactionBuilder,
  nativeToScVal,
  rpc,
  xdr,
} from "@stellar/stellar-sdk";
import { connectFreighter } from "./stellar";

export type EscrowAction = "create" | "accept" | "fund" | "approve" | "release" | "cancel" | "dispute";

const CONTRACT_ID = process.env.NEXT_PUBLIC_ESCROW_CONTRACT_ID ||
  "CA5FBQ4VEJ4ZXGVDVMAGRP6JKEB7AGUUG5ZR3NYSNG3A6XFUUVCL37CI";
const RPC_URL = process.env.NEXT_PUBLIC_SOROBAN_RPC_URL || "https://soroban-testnet.stellar.org";
const PASSPHRASE = Networks.TESTNET;

export function escrowConfig() {
  return {
    contractId: CONTRACT_ID,
    rpcUrl: RPC_URL,
    passphrase: PASSPHRASE,
    nativeAssetContractId: Asset.native().contractId(PASSPHRASE).toString(),
  };
}

export function agreementIdHex(agreementUuid: string): string {
  // Mirrors backend/app/escrow.py: SHA-256 of a domain-separated agreement ID.
  const bytes = new TextEncoder().encode(`freelanceflow:agreement:${agreementUuid}`);
  // SubtleCrypto is async in browsers; use a synchronous FNV-style fallback is unsafe.
  // Instead the backend supplies this value; callers must pass the hex explicitly.
  void bytes;
  throw new Error("agreementIdHex must be supplied by the backend");
}

const bytesArg = (hex: string) => nativeToScVal(Buffer.from(hex, "hex"), { type: "bytes" });
const addressArg = (address: string) => nativeToScVal(Address.fromString(address), { type: "address" });
const i128Arg = (stroops: bigint | number) => nativeToScVal(stroops, { type: "i128" });
const u32Arg = (index: number) => nativeToScVal(index, { type: "u32" });

export function buildEscrowXdr(params: {
  action: EscrowAction;
  agreementId: string;
  source: string;
  client: string;
  freelancer: string;
  milestoneIndex?: number;
  amountStroops?: bigint | number;
  fundedAmounts?: (bigint | number)[];
}): string {
  const contract = new Contract(CONTRACT_ID);
  const id = bytesArg(params.agreementId);
  let operation;
  switch (params.action) {
    case "create": {
      const amounts = (params.fundedAmounts || []).map(i128Arg);
      operation = contract.call(
        "create_agreement", id, addressArg(params.client), addressArg(params.freelancer),
        addressArg(escrowConfig().nativeAssetContractId),
        xdr.ScVal.scvVec(amounts),
      );
      break;
    }
    case "accept":
      operation = contract.call("accept_agreement", id, addressArg(params.freelancer));
      break;
    case "fund":
      operation = contract.call("fund", id, addressArg(params.client), i128Arg(params.amountStroops || 0));
      break;
    case "approve":
      operation = contract.call("approve_milestone", id, u32Arg(params.milestoneIndex || 0), addressArg(params.client));
      break;
    case "release":
      operation = contract.call("release_milestone", id, u32Arg(params.milestoneIndex || 0), addressArg(params.client));
      break;
    case "cancel":
      operation = contract.call("cancel", id, addressArg(params.source));
      break;
    case "dispute":
      operation = contract.call("open_dispute", id, addressArg(params.source));
      break;
  }
  const account = new Account(params.source, "0");
  return new TransactionBuilder(account, { fee: "1000", networkPassphrase: PASSPHRASE })
    .addOperation(operation)
    .addMemo(Memo.text("FF-ESCROW"))
    .setTimeout(120)
    .build()
    .toXDR();
}

export async function signSubmitEscrow(params: {
  action: EscrowAction;
  agreementId: string;
  source: string;
  client: string;
  freelancer: string;
  milestoneIndex?: number;
  amountStroops?: bigint | number;
  fundedAmounts?: (bigint | number)[];
}): Promise<string> {
  const connection = await connectFreighter();
  if (connection.address !== params.source) throw new Error(`Connect Freighter with ${params.source}`);
  const server = new rpc.Server(RPC_URL);
  const account = await server.getAccount(params.source);
  const xdrUnsigned = buildEscrowXdr({ ...params, source: params.source });
  // Rebuild with the real sequence number from RPC.
  const contract = new Contract(CONTRACT_ID);
  const id = bytesArg(params.agreementId);
  let operation;
  switch (params.action) {
    case "create":
      operation = contract.call("create_agreement", id, addressArg(params.client), addressArg(params.freelancer), addressArg(escrowConfig().nativeAssetContractId), xdr.ScVal.scvVec((params.fundedAmounts || []).map(i128Arg)));
      break;
    case "accept": operation = contract.call("accept_agreement", id, addressArg(params.freelancer)); break;
    case "fund": operation = contract.call("fund", id, addressArg(params.client), i128Arg(params.amountStroops || 0)); break;
    case "approve": operation = contract.call("approve_milestone", id, u32Arg(params.milestoneIndex || 0), addressArg(params.client)); break;
    case "release": operation = contract.call("release_milestone", id, u32Arg(params.milestoneIndex || 0), addressArg(params.client)); break;
    case "cancel": operation = contract.call("cancel", id, addressArg(params.source)); break;
    case "dispute": operation = contract.call("open_dispute", id, addressArg(params.source)); break;
  }
  let tx = new TransactionBuilder(account, { fee: "1000", networkPassphrase: PASSPHRASE })
    .addOperation(operation).addMemo(Memo.text("FF-ESCROW")).setTimeout(120).build();
  tx = await server.prepareTransaction(tx);
  const freighter = await import("@stellar/freighter-api");
  const signed = await freighter.signTransaction(tx.toXDR(), { networkPassphrase: PASSPHRASE, address: connection.address });
  if (signed.error || !signed.signedTxXdr) throw new Error(signed.error || "Escrow transaction was not signed");
  const finalTx = TransactionBuilder.fromXDR(signed.signedTxXdr, PASSPHRASE);
  const result = await server.sendTransaction(finalTx);
  if (result.status !== "PENDING") throw new Error("Escrow transaction was not accepted by the network");
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const onChain = await server.getTransaction(result.hash);
    if (onChain.status === "SUCCESS") return result.hash;
    if (onChain.status === "FAILED") throw new Error("Escrow transaction failed on Testnet");
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error("Escrow transaction was submitted but not confirmed in time");
}
