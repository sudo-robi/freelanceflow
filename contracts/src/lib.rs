#![no_std]

use soroban_sdk::{
    contract, contracterror, contractimpl, contracttype,
    Address, BytesN, Env, Symbol, Vec,
    token,
};

#[contracterror]
#[derive(Copy, Clone, Debug, Eq, PartialEq, PartialOrd, Ord)]
#[repr(u32)]
pub enum EscrowError {
    AgreementExists = 1,
    AgreementMissing = 2,
    InvalidAmount = 3,
    InvalidMilestone = 4,
    MilestoneNotApproved = 5,
    AlreadyReleased = 6,
    Unauthorized = 7,
    InsufficientBalance = 8,
    AgreementNotAccepted = 9,
    Disputed = 10,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Agreement {
    pub client: Address,
    pub freelancer: Address,
    pub asset: Address,
    pub total_amount: i128,
    pub funded_amount: i128,
    pub released_amount: i128,
    pub accepted: bool,
    pub disputed: bool,
    pub cancelled: bool,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum DataKey {
    Agreement(BytesN<32>),
    Milestone(BytesN<32>, u32),
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Milestone {
    pub approved: bool,
    pub released: bool,
    pub amount: i128,
}

fn agreement_key(id: &BytesN<32>) -> DataKey {
    DataKey::Agreement(id.clone())
}

fn milestone_key(id: &BytesN<32>, milestone: u32) -> DataKey {
    DataKey::Milestone(id.clone(), milestone)
}

#[contract]
pub struct FreelanceFlowEscrow;

#[cfg(test)]
mod lib_test;

#[contractimpl]
impl FreelanceFlowEscrow {
    pub fn create_agreement(
        env: Env,
        agreement_id: BytesN<32>,
        client: Address,
        freelancer: Address,
        asset: Address,
        milestone_amounts: Vec<i128>,
    ) -> Result<(), EscrowError> {
        client.require_auth();

        if env.storage().instance().has(&agreement_key(&agreement_id)) {
            return Err(EscrowError::AgreementExists);
        }

        let mut total: i128 = 0;
        for amount in milestone_amounts.iter() {
            if amount <= 0 {
                return Err(EscrowError::InvalidAmount);
            }
            total = total.checked_add(amount).ok_or(EscrowError::InvalidAmount)?;
        }

        let agreement = Agreement {
            client: client.clone(),
            freelancer,
            asset,
            total_amount: total,
            funded_amount: 0,
            released_amount: 0,
            accepted: false,
            disputed: false,
            cancelled: false,
        };
        env.storage().instance().set(&agreement_key(&agreement_id), &agreement);

        for (index, amount) in milestone_amounts.iter().enumerate() {
            let milestone = Milestone { approved: false, released: false, amount };
            env.storage().instance().set(&milestone_key(&agreement_id, index as u32), &milestone);
        }

        env.events().publish((Symbol::new(&env, "created"), agreement_id), agreement.client);
        Ok(())
    }

    pub fn accept_agreement(env: Env, agreement_id: BytesN<32>, freelancer: Address) -> Result<(), EscrowError> {
        freelancer.require_auth();
        let key = agreement_key(&agreement_id);
        let mut agreement: Agreement = env.storage().instance().get(&key).ok_or(EscrowError::AgreementMissing)?;
        if agreement.cancelled || agreement.disputed {
            return Err(EscrowError::Disputed);
        }
        if agreement.freelancer != freelancer {
            return Err(EscrowError::Unauthorized);
        }
        agreement.accepted = true;
        env.storage().instance().set(&key, &agreement);
        env.events().publish((Symbol::new(&env, "accepted"), agreement_id), freelancer);
        Ok(())
    }

    pub fn fund(env: Env, agreement_id: BytesN<32>, client: Address, amount: i128) -> Result<(), EscrowError> {
        client.require_auth();
        if amount <= 0 {
            return Err(EscrowError::InvalidAmount);
        }
        let key = agreement_key(&agreement_id);
        let mut agreement: Agreement = env.storage().instance().get(&key).ok_or(EscrowError::AgreementMissing)?;
        if agreement.client != client {
            return Err(EscrowError::Unauthorized);
        }
        if !agreement.accepted {
            return Err(EscrowError::AgreementNotAccepted);
        }
        if agreement.cancelled || agreement.disputed {
            return Err(EscrowError::Disputed);
        }

        agreement.funded_amount = agreement.funded_amount.checked_add(amount).ok_or(EscrowError::InvalidAmount)?;
        if agreement.funded_amount > agreement.total_amount {
            return Err(EscrowError::InsufficientBalance);
        }

        token::Client::new(&env, &agreement.asset).transfer(&client, &env.current_contract_address(), &amount);
        env.storage().instance().set(&key, &agreement);
        env.events().publish((Symbol::new(&env, "funded"), agreement_id), amount);
        Ok(())
    }

    pub fn approve_milestone(
        env: Env,
        agreement_id: BytesN<32>,
        milestone_index: u32,
        client: Address,
    ) -> Result<(), EscrowError> {
        client.require_auth();
        let agreement_key = agreement_key(&agreement_id);
        let agreement: Agreement = env.storage().instance().get(&agreement_key).ok_or(EscrowError::AgreementMissing)?;
        if agreement.client != client {
            return Err(EscrowError::Unauthorized);
        }
        if agreement.cancelled || agreement.disputed {
            return Err(EscrowError::Disputed);
        }

        let key = milestone_key(&agreement_id, milestone_index);
        let mut milestone: Milestone = env.storage().instance().get(&key).ok_or(EscrowError::InvalidMilestone)?;
        if milestone.released {
            return Err(EscrowError::AlreadyReleased);
        }
        milestone.approved = true;
        env.storage().instance().set(&key, &milestone);
        env.events().publish((Symbol::new(&env, "approved"), agreement_id, milestone_index), client);
        Ok(())
    }

    pub fn release_milestone(
        env: Env,
        agreement_id: BytesN<32>,
        milestone_index: u32,
        client: Address,
    ) -> Result<(), EscrowError> {
        client.require_auth();
        let agreement_key = agreement_key(&agreement_id);
        let mut agreement: Agreement = env.storage().instance().get(&agreement_key).ok_or(EscrowError::AgreementMissing)?;
        if agreement.client != client {
            return Err(EscrowError::Unauthorized);
        }
        if agreement.cancelled || agreement.disputed {
            return Err(EscrowError::Disputed);
        }

        let milestone_key = milestone_key(&agreement_id, milestone_index);
        let mut milestone: Milestone = env.storage().instance().get(&milestone_key).ok_or(EscrowError::InvalidMilestone)?;
        if !milestone.approved {
            return Err(EscrowError::MilestoneNotApproved);
        }
        if milestone.released {
            return Err(EscrowError::AlreadyReleased);
        }

        let remaining = agreement.funded_amount.checked_sub(agreement.released_amount).ok_or(EscrowError::InsufficientBalance)?;
        if remaining < milestone.amount {
            return Err(EscrowError::InsufficientBalance);
        }

        milestone.released = true;
        agreement.released_amount = agreement.released_amount.checked_add(milestone.amount).ok_or(EscrowError::InvalidAmount)?;
        token::Client::new(&env, &agreement.asset).transfer(&env.current_contract_address(), &agreement.freelancer, &milestone.amount);

        env.storage().instance().set(&milestone_key, &milestone);
        env.storage().instance().set(&agreement_key, &agreement);
        env.events().publish((Symbol::new(&env, "released"), agreement_id, milestone_index), milestone.amount);
        Ok(())
    }

    pub fn cancel(env: Env, agreement_id: BytesN<32>, caller: Address) -> Result<i128, EscrowError> {
        caller.require_auth();
        let key = agreement_key(&agreement_id);
        let mut agreement: Agreement = env.storage().instance().get(&key).ok_or(EscrowError::AgreementMissing)?;
        if agreement.client != caller && agreement.freelancer != caller {
            return Err(EscrowError::Unauthorized);
        }
        if agreement.disputed {
            return Err(EscrowError::Disputed);
        }

        agreement.cancelled = true;
        let refundable = agreement.funded_amount.checked_sub(agreement.released_amount).ok_or(EscrowError::InvalidAmount)?;
        if refundable > 0 {
            token::Client::new(&env, &agreement.asset).transfer(&env.current_contract_address(), &agreement.client, &refundable);
        }
        // After refunding, no funds remain claimable under this agreement.
        agreement.funded_amount = agreement.released_amount;
        env.storage().instance().set(&key, &agreement);
        env.events().publish((Symbol::new(&env, "cancelled"), agreement_id), refundable);
        Ok(refundable)
    }

    pub fn open_dispute(env: Env, agreement_id: BytesN<32>, caller: Address) -> Result<(), EscrowError> {
        caller.require_auth();
        let key = agreement_key(&agreement_id);
        let mut agreement: Agreement = env.storage().instance().get(&key).ok_or(EscrowError::AgreementMissing)?;
        if agreement.client != caller && agreement.freelancer != caller {
            return Err(EscrowError::Unauthorized);
        }
        agreement.disputed = true;
        env.storage().instance().set(&key, &agreement);
        env.events().publish((Symbol::new(&env, "disputed"), agreement_id), caller);
        Ok(())
    }

    pub fn balance(env: Env, agreement_id: BytesN<32>) -> Result<i128, EscrowError> {
        let agreement: Agreement = env.storage().instance().get(&agreement_key(&agreement_id)).ok_or(EscrowError::AgreementMissing)?;
        agreement.funded_amount.checked_sub(agreement.released_amount).ok_or(EscrowError::InsufficientBalance)
    }
}
