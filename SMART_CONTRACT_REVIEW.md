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

## Integration and deployment status

No contract ID, deployment transaction, or on-chain release is claimed. No FastAPI route invokes the contract. The contract contains `open_dispute` but no on-chain resolution function; application-level dispute resolution is stored in the database and never releases funds automatically. Independent third-party audit has not been performed.
