# FME Contract Registry (INTERNAL — Engineering only)

*Internal record of FME's deployed contracts. For the Engineering Copilot only — NEVER in
customer TrueAI. This teaches TrueAI about FME's real deployed contracts. Fill in from your
actual deployment records.*

## How to use
- One entry per deployed contract/token.
- Record proxy vs. implementation addresses (UUPS), the admin/owner, and the audit status.
- Keep this accurate — it's the source of truth for what's actually deployed.

---

## Token: [SYMBOL] — [Full Name]
- Network: FME L1 (chain ID 77777)
- Standard: UUPS-upgradeable ERC-20
- Proxy address: [FME to complete]
- Implementation address: [FME to complete]
- Admin/owner: [FME to complete — current key/multisig holding admin]
- Roles: [FME to complete — who holds minter/pauser/upgrader]
- Audit status: [FME to complete — Slither/centralization check date, any external audit]
- Source: [FME to complete — path to verified source, e.g. /opt/FME/contracts/...]
- Notes: [FME to complete]

*(Copy the block above for each token: MARU, MMK, JPYC, NCK, AYET, DPP, and the FME native
token. Record the real deployed addresses and role holders.)*

---

## Deployment & upgrade log
- [FME to complete: date, contract, version/implementation hash, who approved, Safe tx if any.]

## Known centralization status (from audits)
- Current tokens: all privileged roles on a single treasury key; full supply to one address
  (flagged by CertiK and FME's centralization checker). Target: migrate roles to Gnosis Safe
  multisig + TimelockController. Migration status: [FME to complete].
