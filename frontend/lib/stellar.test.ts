import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PaymentIntentDetails } from "./stellar";

const freighter = vi.hoisted(() => ({
  isConnected: vi.fn(),
  requestAccess: vi.fn(),
  getNetwork: vi.fn(),
  signTransaction: vi.fn(),
}));

const stellar = vi.hoisted(() => ({
  loadAccount: vi.fn(),
  fetchBaseFee: vi.fn(),
  submitTransaction: vi.fn(),
  fromXDR: vi.fn(),
  text: vi.fn(),
  payment: vi.fn(),
  native: vi.fn(),
}));

vi.mock("@stellar/freighter-api", () => freighter);
vi.mock("@stellar/stellar-sdk", () => {
  class Server {
    loadAccount = stellar.loadAccount;
    fetchBaseFee = stellar.fetchBaseFee;
    submitTransaction = stellar.submitTransaction;
  }
  class Builder {
    constructor(_account: unknown, _opts: unknown) {}
    addOperation() { return this; }
    setTimeout() { return this; }
    build() { return { toXDR: () => "unsigned-xdr" }; }
  }
  return {
    Horizon: { Server },
    TransactionBuilder: Object.assign(Builder, { fromXDR: stellar.fromXDR }),
    Memo: { text: stellar.text },
    Operation: { payment: stellar.payment },
    Asset: { native: stellar.native },
  };
});

import {
  TESTNET_PASSPHRASE,
  buildFundedPaymentXdr,
  connectFreighter,
  signAndSubmitPayment,
} from "./stellar";

const source = "G" + "A".repeat(55);
const destination = "G" + "B".repeat(55);
const intent: PaymentIntentDetails = {
  id: "intent-1",
  milestone_id: "milestone-1",
  amount: 25,
  asset: "XLM",
  network: "testnet",
  network_passphrase: TESTNET_PASSPHRASE,
  source_account: source,
  destination_account: destination,
  memo: "FF-TEST-0001",
  horizon_url: "https://horizon-testnet.stellar.org",
};

describe("Freighter connection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    freighter.isConnected.mockResolvedValue({ isConnected: false });
    freighter.requestAccess.mockResolvedValue({ address: source });
    freighter.getNetwork.mockResolvedValue({ network: "testnet", networkPassphrase: TESTNET_PASSPHRASE });
  });

  it("rejects when Freighter is not connected", async () => {
    await expect(connectFreighter()).rejects.toThrow("Freighter is not installed");
  });

  it("rejects when the wallet is on a different network", async () => {
    freighter.isConnected.mockResolvedValue({ isConnected: true });
    freighter.getNetwork.mockResolvedValue({ network: "public", networkPassphrase: "Public Global Stellar Network ; September 2015" });
    await expect(connectFreighter()).rejects.toThrow("Switch Freighter to Stellar Testnet");
  });

  it("returns the granted address on Testnet", async () => {
    freighter.isConnected.mockResolvedValue({ isConnected: true });
    await expect(connectFreighter()).resolves.toEqual({ address: source, networkPassphrase: TESTNET_PASSPHRASE });
  });
});

describe("payment transaction building and submission", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    stellar.loadAccount.mockResolvedValue({ id: source });
    stellar.fetchBaseFee.mockResolvedValue(100);
    stellar.submitTransaction.mockResolvedValue({ hash: "c".repeat(64), successful: true, ledger: 99 });
    stellar.fromXDR.mockReturnValue({ signed: true });
    stellar.text.mockImplementation((value: string) => ({ text: value }));
    stellar.payment.mockImplementation((value: object) => ({ payment: value }));
    stellar.native.mockReturnValue({ native: true });
    freighter.isConnected.mockResolvedValue({ isConnected: true });
    freighter.requestAccess.mockResolvedValue({ address: source });
    freighter.getNetwork.mockResolvedValue({ network: "testnet", networkPassphrase: TESTNET_PASSPHRASE });
    freighter.signTransaction.mockResolvedValue({ signedTxXdr: "signed-xdr", signerAddress: source });
  });

  it("refuses to build a transaction for a non-testnet intent", async () => {
    await expect(buildFundedPaymentXdr({ ...intent, network: "public" })).rejects.toThrow("not for Stellar Testnet");
  });

  it("binds memo, destination and exact amount in the transaction", async () => {
    await expect(buildFundedPaymentXdr(intent)).resolves.toBe("unsigned-xdr");
    expect(stellar.text).toHaveBeenCalledWith("FF-TEST-0001");
    expect(stellar.payment).toHaveBeenCalledWith({
      destination,
      amount: "25.0000000",
      asset: { native: true },
    });
    expect(stellar.fetchBaseFee).toHaveBeenCalledOnce();
  });

  it("requires the connected wallet to be the intent source", async () => {
    freighter.requestAccess.mockResolvedValue({ address: destination });
    await expect(signAndSubmitPayment(intent)).rejects.toThrow("Connect Freighter with");
    expect(freighter.signTransaction).not.toHaveBeenCalled();
  });

  it("reports a rejected signature without submitting anything", async () => {
    freighter.signTransaction.mockResolvedValue({ error: "User rejected the request" });
    await expect(signAndSubmitPayment(intent)).rejects.toThrow("User rejected");
    expect(stellar.submitTransaction).not.toHaveBeenCalled();
  });

  it("submits the signed transaction and returns the real hash", async () => {
    const result = await signAndSubmitPayment(intent);
    expect(result).toEqual({ hash: "c".repeat(64), ledger: 99, successful: true });
    expect(freighter.signTransaction).toHaveBeenCalledWith("unsigned-xdr", {
      networkPassphrase: TESTNET_PASSPHRASE,
      address: source,
    });
    expect(stellar.submitTransaction).toHaveBeenCalledWith({ signed: true });
  });
});
