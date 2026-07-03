#!/usr/bin/env python3
"""
TrueL1 Centralization & Governance Check
========================================
Static, pattern-based analysis of a Solidity contract for CENTRALIZATION and
governance risks - the class of issue that bytecode/detector tools (e.g. Slither)
usually do NOT flag, but that professional auditors focus on.

This is ORIGINAL analysis by TrueL1 tooling. It does not reproduce any third-party
audit. Output is guidance to investigate, not a certified finding.

Usage:
    python3 centralization_check.py Contract.sol            # human-readable
    python3 centralization_check.py Contract.sol --json out.json   # spec fragment

Emits findings in the same shape truel1-report.py expects (id/title/severity/
category/location/description/recommendation), so they can be merged into a report.
"""
import sys, re, json, argparse, os

PREFIX = "GOV"

def _lines(src):
    return src.split("\n")

def _find_line(src, pattern, flags=0):
    for i, ln in enumerate(src.split("\n"), 1):
        if re.search(pattern, ln, flags):
            return i
    return None

def analyze(src, filename="Contract.sol"):
    findings = []
    n = 0

    def add(title, severity, category, line, desc, rec):
        nonlocal n
        n += 1
        findings.append({
            "id": f"{PREFIX}-{n:02d}",
            "title": title,
            "severity": severity,
            "category": category,
            "location": f"{filename}" + (f": {line}" if line else ""),
            "description": desc,
            "recommendation": rec,
        })

    low = src

    # 1) Upgradeable + owner/role-gated upgrade authorization
    is_upgradeable = bool(re.search(r"UUPSUpgradeable|_authorizeUpgrade|UpgradeableProxy|Initializable", low))
    auth_line = _find_line(low, r"_authorizeUpgrade")
    if is_upgradeable and auth_line:
        # who gates it?
        gate = "an unspecified privileged role"
        if re.search(r"_authorizeUpgrade[^{)]*onlyOwner", low):
            gate = "the single contract owner (onlyOwner)"
        elif re.search(r"_authorizeUpgrade[^{)]*onlyRole", low):
            gate = "a single privileged role (onlyRole)"
        add(
            "Centralized Control of Contract Upgrade",
            "Medium", "Centralization", auth_line,
            "The contract is an upgradeable proxy whose implementation can be replaced by "
            f"{gate}. Because an upgrade can change ALL contract logic, a compromise of that "
            "key (or its misuse) would let an attacker replace the contract with arbitrary "
            "code, including code that seizes or freezes user funds. Upgrades appear to take "
            "effect immediately, with no on-chain delay or second approval.",
            "Reduce single-key upgrade power by: (1) routing upgrades through a time-lock "
            "controller with a reasonable delay (e.g. 48 hours) so changes are visible before "
            "they take effect; (2) assigning the upgrade authority to a multi-signature wallet "
            "rather than one key; and/or (3) introducing governance (DAO/voting). Renouncing "
            "the upgrade authority or removing upgradeability entirely fully resolves the risk, "
            "at the cost of future upgradability."
        )

    # 2) Entire initial supply minted to a single address
    m = re.search(r"_mint\s*\(\s*([A-Za-z_][\w.]*)", low)
    mint_line = _find_line(low, r"_mint\s*\(")
    if m:
        target = m.group(1)
        # heuristics: single mint to a receiver/treasury/owner param
        if re.search(r"receiver|treasury|owner|to\b", target, re.I) or target:
            add(
                "Initial Token Distribution Centralization",
                "Medium", "Centralization", mint_line,
                f"The initial token supply is minted in full to a single address (`{target}`). "
                "Concentrating the entire supply in one account is a centralization risk: the "
                "holder can move or distribute the whole supply at will, and the safety of the "
                "entire supply depends on that one key. For tokens intended for broad use, this "
                "concentrates both economic weight and risk.",
                "Distribute the initial supply according to a documented, transparent allocation "
                "(e.g. vesting contracts, a treasury multi-sig, liquidity, and community "
                "allocations) rather than a single address. If a single recipient is intended, "
                "hold it in a multi-signature wallet or vesting/timelock contract and publish the "
                "allocation plan."
            )

    # 3) Owner/role can pause transfers
    pause_line = _find_line(low, r"function\s+pause")
    if re.search(r"function\s+pause\s*\([^)]*\)\s*[^{]*only(Owner|Role)", low):
        add(
            "Privileged Pause of All Transfers",
            "Low", "Centralization", pause_line,
            "A privileged account can pause the contract, halting all token transfers. This "
            "capability can protect users in an emergency, but it is also a centralization "
            "power: the privileged account can freeze all movement of the token unilaterally.",
            "Confirm this capability is intended. Hold the pausing authority under a "
            "multi-signature wallet or governance, document when and how it may be used, and "
            "disclose the capability clearly to users. Consider limiting pause duration or "
            "requiring multiple approvals for extended pauses."
        )

    # 4) Owner can mint after deploy (open-ended minting)
    open_mint = re.search(r"function\s+mint\s*\([^)]*\)\s*[^{]*only(Owner|Role)", low)
    mint_fn_line = _find_line(low, r"function\s+mint\s*\(")
    if open_mint:
        add(
            "Unlimited Post-Deployment Minting",
            "High", "Centralization", mint_fn_line,
            "A privileged account can mint new tokens after deployment, with no cap or rate "
            "limit evident in the contract. This lets the key holder inflate the supply at will; "
            "for a value-bearing or pegged token this directly threatens holders and any peg.",
            "Enforce a minting policy in code where possible (hard cap, per-window rate limit, "
            "or two-step timelocked mint). At minimum, hold the minting authority under a "
            "multi-signature wallet with a documented, publicly verifiable issuance/backing "
            "process."
        )

    # 5) Missing timelock (informational, only if privileged ops exist and no timelock seen)
    has_priv = bool(re.search(r"onlyOwner|onlyRole", low))
    has_timelock = bool(re.search(r"[Tt]imelock|TimelockController|minDelay", low))
    if has_priv and not has_timelock:
        add(
            "No Time-Lock on Privileged Operations",
            "Informational", "Centralization", None,
            "Privileged operations (e.g. upgrades, pausing, minting) appear to execute "
            "immediately, with no time-lock. A time-lock gives users advance notice of "
            "sensitive changes and time to react.",
            "Introduce an on-chain time-lock (e.g. OpenZeppelin TimelockController) for "
            "privileged operations, with a reasonable delay (e.g. 24-72 hours), so the community "
            "can observe and respond to queued privileged actions before they take effect."
        )

    return findings

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("solfile")
    ap.add_argument("--json", help="write spec-fragment JSON to this path")
    ap.add_argument("--name", help="override the filename shown in locations")
    args = ap.parse_args()
    src = open(args.solfile, encoding="utf-8", errors="ignore").read()
    fname = args.name or os.path.basename(args.solfile)
    findings = analyze(src, fname)
    if args.json:
        json.dump({"findings": findings}, open(args.json, "w"), indent=2)
        print(f"Wrote {len(findings)} centralization finding(s) to {args.json}")
    else:
        print(f"\nTrueL1 Centralization & Governance Check - {fname}")
        print("=" * 60)
        if not findings:
            print("No centralization patterns matched. NOTE: absence of matches does not")
            print("mean the contract is decentralized or secure - review manually.")
        for f in findings:
            print(f"\n[{f['id']}] {f['title']}  ({f['severity']} - {f['category']})")
            print(f"  Location: {f['location']}")
            print(f"  {f['description']}")
            print(f"  Recommendation: {f['recommendation']}")
        print("\n" + "=" * 60)
        print("This is ORIGINAL TrueL1 automated analysis - guidance to investigate,")
        print("not a certified audit. Verify each item against the source and intended design.")

if __name__ == "__main__":
    main()
