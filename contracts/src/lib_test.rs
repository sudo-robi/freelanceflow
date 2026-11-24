#[cfg(test)]
mod test {
    use soroban_sdk::{testutils::Address as _, Address, BytesN, Env, Vec};

    use crate::{FreelanceFlowEscrow, FreelanceFlowEscrowClient};

    #[test]
    fn rejects_release_before_approval() {
        let env = Env::default();
        env.mock_all_auths();
        let contract_id = env.register(FreelanceFlowEscrow, ());
        let client = FreelanceFlowEscrowClient::new(&env, &contract_id);
        let creator = Address::generate(&env);
        let freelancer = Address::generate(&env);
        let asset = Address::generate(&env);
        let id = BytesN::from_array(&env, &[7; 32]);
        let amounts = Vec::from_array(&env, [100_i128]);

        client.create_agreement(&id, &creator, &freelancer, &asset, &amounts);

        let result = client.try_release_milestone(&id, &0, &creator);
        assert!(result.is_err());
    }
}
