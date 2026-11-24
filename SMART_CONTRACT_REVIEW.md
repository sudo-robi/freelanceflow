# Smart Contract Review

## Scope

`contracts/src/lib.rs` is a Soroban escrow contract reviewed statically and executed with the Soroban test environment (`soroban-sdk` 30.0.0, `testutils`, registered Stellar asset contract).

## Implemented contract behavior

- Agreement creation with duplicate-ID protection and positive amount validation.
- Freelancer-only acceptance; client-only funding after acceptance.
- Milestone approval and single release with balance checks.
- Cancellation refund of all unreleased funds to the client.
- Dispute state that blocks approval, release, funding, and release after cancellation.
- Balance tracking of funded minus released amounts.

## Defect found and repaired

The original `cancel()` refunded funds but left `funded_amount` unchanged, so `balance()` still reported locked funds after cancellation. The contract now sets `funded_amount = released_amount` after refunding. The regression is covered by `cancellation_refunds_unreleased_funds`.

## Test results

`cd contracts && cargo test` — **8 passed, 0 failed**:

1. `rejects_release_before_approval`
2. `rejects_zero_and_negative_milestone_amounts`
3. `only_assigned_freelancer_can_accept`
4. `funding_requires_acceptance_and_transfers_tokens`
5. `approved_milestone_release_pays_freelancer_once`
6. `dispute_blocks_approval_release_funding_and_preserves_balance`
7. `cancellation_refunds_unreleased_funds`
8. `unauthorized_party_cannot_open_dispute`

## Deployment evidence (executed 2026-11-25)

The contract was built and deployed with Stellar CLI 30.0.1 (release checksum `48c70074020e09af0a3ebbd2bf62d53c9aec47935e49a112d3cd90fb4e37658f`, matching the published release digest).

| Artifact | Value |
|---|---|
| Contract ID | `CA5FBQ4VEJ4ZXGVDVMAGRP6JKEB7AGUUG5ZR3NYSNG3A6XFUUVCL37CI` |
| WASM hash (local and on-chain) | `906f98af2a1ae3bb8a816ea65bab35b130c3f4ab02d1ba40335a8ca1eb9b527a` |
| WASM upload transaction | `9c2d00688e0bfe2da7f928b62c0232db917d1f35cbbf53dcb6301540771e91e5` (Horizon: successful, ledger 5907860) |
| Deployment transaction | `b2f65b6fa9a948261c4861d70f3db92f52046fff86a1c89320581ea042e6f69f` (Soroban RPC `getTransaction`: `status: SUCCESS`) |
| Explorer | https://stellar.expert/explorer/testnet/tx/b2f65b6fa9a948261c4861d70f3db92f52046fff86a1c89320581ea042e6f69f |

Verification commands executed after deployment:

- `stellar contract info hash --contract-id CA5F...CL37CI --network testnet` → `906f98af...b527a`, matching the local WASM checksum.
- `stellar contract info interface --contract-id CA5F...CL37CI --network testnet` → exposed `create_agreement`, `accept_agreement`, `fund`, `approve_milestone`, `release_milestone`, `cancel`, `open_dispute`, `balance`.

The deployer key was generated solely for this deployment, funded by friendbot, and removed from the CLI identity store afterward. No secret key or seed phrase is stored in the repository or configuration.

## Integration status

The contract is live but no FastAPI route invokes it. Verified application payments still use direct Stellar transactions checked against Horizon. The contract contains `open_dispute` but no on-chain resolution function; application-level dispute resolution is stored in the database and never releases funds automatically. Independent third-party audit has not been performed.
