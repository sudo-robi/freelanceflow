import {
  Asset,
  Horizon,
  Memo,
  Operation,
  TransactionBuilder,
} from "@stellar/stellar-sdk";
import { apiRequest } from "./api";

export const TESTNET_PASSPHRASE = "Test SDF Network ; September 2015";
export const HORIZON_URL = "https://horizon-testnet.stellar.org";

export interface PaymentIntentDetails {
  id: string;
  milestone_id: string;
  amount: number;
  asset: string;
  network: string;
  network_passphrase: string;
  source_account: string;
  destination_account: string;
  memo: string;
  horizon_url: string;
}

export interface FreighterConnection {
  address: string;
  networkPassphrase: string;
}

export async function connectFreighter(): Promise<FreighterConnection> {
  const freighter = await import("@stellar/freighter-api");
  const status = await freighter.isConnected();
  if (status.error || !status.isConnected) {
    throw new Error("Freighter is not installed or unavailable");
  }
  const access = await freighter.requestAccess();
  if (access.error || !access.address) {
    throw new Error(access.error || "Wallet access was not granted");
  }
  const network = await freighter.getNetwork();
  if (network.error) throw new Error(network.error);
  if (network.networkPassphrase !== TESTNET_PASSPHRASE) {
    throw new Error("Switch Freighter to Stellar Testnet before continuing");
  }
  return { address: access.address, networkPassphrase: network.networkPassphrase };
}

export async function loadTestnetBalances(address: string): Promise<string[]> {
  const account = await apiRequest<{ balances?: { balance: string; asset_type: string }[] }>(
    `/api/stellar/account/${address}`,
  );
  return (account.balances || []).map((item) =>
    `${item.balance} ${item.asset_type === "native" ? "XLM" : item.asset_type}`,
  );
}

export async function buildFundedPaymentXdr(intent: PaymentIntentDetails): Promise<string> {
  if (intent.network !== "testnet" || intent.network_passphrase !== TESTNET_PASSPHRASE) {
    throw new Error("Payment intent is not for Stellar Testnet");
  }
  if (intent.asset !== "XLM") {
    throw new Error("Only native XLM payments are supported");
  }
  const server = new Horizon.Server(intent.horizon_url || HORIZON_URL);
  const account = await server.loadAccount(intent.source_account);
  const fee = await server.fetchBaseFee();
  const transaction = new TransactionBuilder(account, {
    fee: String(fee),
    networkPassphrase: TESTNET_PASSPHRASE,
    memo: Memo.text(intent.memo),
  })
    .addOperation(
      Operation.payment({
        destination: intent.destination_account,
        amount: intent.amount.toFixed(7),
        asset: Asset.native(),
      }),
    )
    .setTimeout(120)
    .build();
  return transaction.toXDR();
}

export interface SubmittedPayment {
  hash: string;
  ledger: number | null;
  successful: boolean;
}

export async function signAndSubmitPayment(intent: PaymentIntentDetails): Promise<SubmittedPayment> {
  const connection = await connectFreighter();
  if (connection.address !== intent.source_account) {
    throw new Error(`Connect Freighter with ${intent.source_account} to sign this payment`);
  }
  const xdr = await buildFundedPaymentXdr(intent);
  const freighter = await import("@stellar/freighter-api");
  const signed = await freighter.signTransaction(xdr, {
    networkPassphrase: TESTNET_PASSPHRASE,
    address: connection.address,
  });
  if (signed.error || !signed.signedTxXdr) {
    throw new Error(signed.error || "Transaction was not signed");
  }
  const signedTransaction = TransactionBuilder.fromXDR(signed.signedTxXdr, TESTNET_PASSPHRASE);
  const server = new Horizon.Server(intent.horizon_url || HORIZON_URL);
  const result = await server.submitTransaction(signedTransaction);
  return {
    hash: result.hash,
    ledger: result.ledger ?? null,
    successful: result.successful !== false,
  };
}
