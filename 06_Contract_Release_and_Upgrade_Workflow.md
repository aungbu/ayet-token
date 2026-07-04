# 06 — Contract Release & Upgrade Workflow

*How tokens/contracts get deployed and upgraded safely on the FME L1. TrueAI guides the routine
parts and escalates deployment of value-bearing contracts. Items marked [FME to complete].*

## Principles
- No contract holding real value is deployed without an audit (Slither + FME centralization
  checker) AND human review.
- Deploy/test on the sandbox chain first (separate keys, separate chain ID) — never experiment
  on production.
- Upgradeable (UUPS) contracts: upgrades are gated by role, and (target pattern) routed through
  a TimelockController held by a multisig.

## Standard release flow
1. Draft the contract (OZ v5.x; UUPS if upgradeable). TrueAI can help draft, in safe patterns.
2. Audit: run through /audit/ (Slither auto-compile + centralization_check.py).
   - Preliminary report first; resolve findings; Final report when clean.
3. Human review by the FME team (required for anything holding value).
4. Deploy to sandbox; test.
5. [FME to complete: production deployment approval + procedure, who signs off.]

## UUPS upgrade flow (target safe pattern)
1. Prepare the new implementation; audit it (same as above).
2. Verify storage-layout compatibility with the current implementation.
3. Schedule the upgrade via the TimelockController (proposed by the multisig).
4. After the timelock delay, execute the upgrade (multisig).
5. Verify the new implementation and that state is intact.
- TrueAI never issues a production upgrade command on request — it escalates and provides the
  pre-check/impact/verification/rollback package.

## Audit tooling reference
- /audit/ web app: upload .sol → auto-solc compile → Slither → centralization check → report.
- Reports labeled "AI Automated Security Assessment — Assessed by FME, Inc. TrueL1" and are a
  review aid, NOT a certified third-party audit. Value-bearing contracts still need a
  professional audit.

## [FME to complete]
- The exact production deployment keys/process, verification on the explorer, and rollback
  policy for a bad deployment.
