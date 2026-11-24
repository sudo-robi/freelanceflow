# Stellar Integration

## Network

- Horizon: `https://horizon-testnet.stellar.org`
- Soroban RPC: `https://soroban-testnet.stellar.org`
- Network passphrase: `Test SDF Network ; September 2015`
- Asset: native XLM only

## Backend behavior

The backend retrieves account and transaction data from Horizon. Payment confirmation:

1. Rejects malformed transaction hashes.
2. Requires an approved milestone.
3. Requires client ownership.
4. Requires Stellar public addresses for both parties.
5. Retrieves the transaction and operations from Horizon.
6. Requires successful transaction status.
7. Requires a native payment operation from the client to the freelancer with the exact milestone amount.
8. Creates a confirmed, unique payment record and only then marks the milestone paid.

Horizon is an independent confirmation source; browser-side balance display is not considered payment evidence.

## Wallet behavior

Freighter is used to retrieve the public address and detect the network passphrase. The application does not request or store secret keys or recovery phrases.

## Status limitations

The UI reports connection, wrong-network, and Horizon balance states but does not yet implement a complete signing-submission-polling state machine. Live wallet signing and submission require a real Freighter installation and a funded Testnet account.
