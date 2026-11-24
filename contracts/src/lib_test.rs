#[cfg(test)]
mod test {
    use soroban_sdk::{testutils::Address as _, token::StellarAssetClient, Address, BytesN, Env, Vec};

    use crate::{EscrowError, FreelanceFlowEscrow, FreelanceFlowEscrowClient};

    struct Fixture {
        env: Env,
        client: FreelanceFlowEscrowClient<'static>,
        id: BytesN<32>,
        owner: Address,
        freelancer: Address,
        asset: Address,
    }

    fn fixture(amounts: &[i128]) -> Fixture {
        let env = Env::default();
        env.mock_all_auths();
        let contract_id = env.register(FreelanceFlowEscrow, ());
        let client = FreelanceFlowEscrowClient::new(&env, &contract_id);
        let owner = Address::generate(&env);
        let freelancer = Address::generate(&env);
        let asset = env.register_stellar_asset_contract_v2(owner.clone()).address();
        let id = BytesN::from_array(&env, &[7; 32]);
        let amounts = Vec::from_slice(&env, amounts);
        client.create_agreement(&id, &owner, &freelancer, &asset, &amounts);
        Fixture { env, client, id, owner, freelancer, asset }
    }

    #[test]
    fn rejects_release_before_approval() {
        let setup = fixture(&[100]);
        let result = setup.client.try_release_milestone(&setup.id, &0, &setup.owner);
        assert_eq!(result, Err(Ok(EscrowError::MilestoneNotApproved)));
    }

    #[test]
    fn rejects_zero_and_negative_milestone_amounts() {
        let env = Env::default();
        env.mock_all_auths();
        let id = env.register(FreelanceFlowEscrow, ());
        let client = FreelanceFlowEscrowClient::new(&env, &id);
        let bad = Vec::from_slice(&env, &[0_i128]);
        assert_eq!(
            client.try_create_agreement(
                &BytesN::from_array(&env, &[1; 32]),
                &Address::generate(&env),
                &Address::generate(&env),
                &env.register_stellar_asset_contract_v2(Address::generate(&env)).address(),
                &bad,
            ),
            Err(Ok(EscrowError::InvalidAmount)),
        );
    }

    #[test]
    fn only_assigned_freelancer_can_accept() {
        let setup = fixture(&[100]);
        let stranger = Address::generate(&setup.env);
        assert_eq!(
            setup.client.try_accept_agreement(&setup.id, &stranger),
            Err(Ok(EscrowError::Unauthorized)),
        );
        setup.client.accept_agreement(&setup.id, &setup.freelancer);
    }

    #[test]
    fn funding_requires_acceptance_and_transfers_tokens() {
        let setup = fixture(&[100]);
        StellarAssetClient::new(&setup.env, &setup.asset).mint(&setup.owner, &200);

        assert_eq!(
            setup.client.try_fund(&setup.id, &setup.owner, &100),
            Err(Ok(EscrowError::AgreementNotAccepted)),
        );
        setup.client.accept_agreement(&setup.id, &setup.freelancer);
        setup.client.fund(&setup.id, &setup.owner, &100);
        assert_eq!(setup.client.balance(&setup.id), 100);
        assert_eq!(
            setup.client.try_fund(&setup.id, &setup.owner, &101),
            Err(Ok(EscrowError::InsufficientBalance)),
        );
    }

    #[test]
    fn approved_milestone_release_pays_freelancer_once() {
        let setup = fixture(&[100, 50]);
        StellarAssetClient::new(&setup.env, &setup.asset).mint(&setup.owner, &200);
        setup.client.accept_agreement(&setup.id, &setup.freelancer);
        setup.client.fund(&setup.id, &setup.owner, &150);
        setup.client.approve_milestone(&setup.id, &0, &setup.owner);
        assert_eq!(
            setup.client.try_release_milestone(&setup.id, &0, &setup.freelancer),
            Err(Ok(EscrowError::Unauthorized)),
        );
        setup.client.release_milestone(&setup.id, &0, &setup.owner);
        assert_eq!(setup.client.balance(&setup.id), 50);
        assert_eq!(
            setup.client.try_release_milestone(&setup.id, &0, &setup.owner),
            Err(Ok(EscrowError::AlreadyReleased)),
        );
    }

    #[test]
    fn dispute_blocks_approval_release_funding_and_preserves_balance() {
        let setup = fixture(&[100]);
        StellarAssetClient::new(&setup.env, &setup.asset).mint(&setup.owner, &200);
        setup.client.accept_agreement(&setup.id, &setup.freelancer);
        setup.client.fund(&setup.id, &setup.owner, &100);
        setup.client.approve_milestone(&setup.id, &0, &setup.owner);

        setup.client.open_dispute(&setup.id, &setup.freelancer);
        assert_eq!(
            setup.client.try_release_milestone(&setup.id, &0, &setup.owner),
            Err(Ok(EscrowError::Disputed)),
        );
        assert_eq!(
            setup.client.try_approve_milestone(&setup.id, &0, &setup.owner),
            Err(Ok(EscrowError::Disputed)),
        );
        assert_eq!(
            setup.client.try_fund(&setup.id, &setup.owner, &1),
            Err(Ok(EscrowError::Disputed)),
        );
        assert_eq!(setup.client.balance(&setup.id), 100);
    }

    #[test]
    fn cancellation_refunds_unreleased_funds() {
        let setup = fixture(&[100]);
        StellarAssetClient::new(&setup.env, &setup.asset).mint(&setup.owner, &200);
        setup.client.accept_agreement(&setup.id, &setup.freelancer);
        setup.client.fund(&setup.id, &setup.owner, &100);
        let refund = setup.client.cancel(&setup.id, &setup.owner);
        assert_eq!(refund, 100);
        assert_eq!(setup.client.balance(&setup.id), 0);
        assert_eq!(
            setup.client.try_release_milestone(&setup.id, &0, &setup.owner),
            Err(Ok(EscrowError::Disputed)),
        );
    }

    #[test]
    fn unauthorized_party_cannot_open_dispute() {
        let setup = fixture(&[100]);
        let stranger = Address::generate(&setup.env);
        assert_eq!(
            setup.client.try_open_dispute(&setup.id, &stranger),
            Err(Ok(EscrowError::Unauthorized)),
        );
    }
}
