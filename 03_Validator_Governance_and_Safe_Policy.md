# 03 — Validator Governance & Safe (Multisig) Policy

*Key custody, validator governance, and the multisig/timelock policy for the FME L1 and its
tokens. This is core security policy. TrueAI teaches these patterns and escalates any change.
Items marked [FME to complete] need FME input.*

## Validator key custody (critical)
- The validator private key (/opt/FME/core/node1/key) must exist on EXACTLY ONE running node.
- NEVER copy it to a second running node — this causes double-signing / consensus faults.
- For a second node or a sandbox, generate FRESH keys and use a separate chain ID.
- Recommended: store the validator key with hardware/HSM protection where feasible.
- [FME to complete: exact key custody procedure, who has access, backup of the key material.]

## Validator membership changes (QBFT)
- Adding/removing a validator changes consensus and can halt the chain if done wrong.
- Validator changes are GOVERNANCE actions: require quorum of existing validators AND
  Gnosis Safe (multisig) approval before execution.
- Procedure: [FME to complete: the exact proposeValidatorVote / discardValidatorVote steps,
  who approves, and the verification after.]
- TrueAI never issues validator-change commands on request — it escalates to the FME team.

## Token admin governance — the SAFE pattern (what FME recommends and should adopt)
The current tokens concentrate all roles in one treasury key (see doc 01). The target safe
pattern for new tokens (and, when feasible, migration of existing ones):
1. Admin/owner and upgrader roles held by a Gnosis Safe MULTISIG (e.g. 2-of-3 or 3-of-5).
2. Privileged operations (upgrade, mint, pause) routed through an OpenZeppelin
   TimelockController with a delay (e.g. 24-72 hours).
3. Role SEPARATION via AccessControl — minter, pauser, upgrader, admin are distinct keys.
4. A minting policy (cap or rate limit) for value-bearing / pegged tokens.

## Migration note (existing tokens)
Moving existing tokens' roles to a multisig + timelock is a sensitive operation that must be
planned, tested on the sandbox, and reviewed. [FME to complete: decision + plan on whether/when
to migrate existing token roles to multisig+timelock.]

## Safe (multisig) operational policy
- [FME to complete: which Safe address(es) hold which roles, the signer set, the required
  threshold, and how transactions are proposed/approved.]
