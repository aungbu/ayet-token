#!/usr/bin/env python3
"""
slither_to_spec.py
==================
Converts Slither's JSON detector output into a TrueL1 report spec (the JSON that
truel1-report.py renders). Findings come ONLY from Slither - real detectors with
real line numbers. Nothing is invented. A model may later be used to polish the
prose, but the set of findings is grounded in static analysis.

Usage:
    slither <file.sol> --json - | slither_to_spec.py --project AYET --prefix AYE \
        --file AYET.sol -o spec.json
  or
    slither_to_spec.py slither-output.json --project AYET -o spec.json
"""
import os
import sys
import json
import argparse

# Slither impact -> TrueL1 severity. Critical is reserved for manual escalation.
SEVERITY_MAP = {
    "High": "Major",
    "Medium": "Medium",
    "Low": "Minor",
    "Informational": "Informational",
    "Optimization": "Informational",
}

# check-name keyword -> category (best effort; falls back to "Security")
CATEGORY_RULES = [
    (("reentrancy",), "Logical Issue"),
    (("arbitrary-send", "suicidal", "controlled", "tx-origin"), "Logical Issue"),
    (("uninitialized", "missing-zero", "divide", "unchecked"), "Volatile Code"),
    (("owner", "centraliz", "access"), "Centralization"),
    (("solc", "pragma", "naming", "convention", "literal", "style",
      "unused", "dead-code", "assembly"), "Coding Style"),
]

# check-name keyword -> a concrete recommendation. Fallback below.
RECO_RULES = [
    (("reentrancy",),
     "Apply the checks-effects-interactions pattern and/or a reentrancy guard "
     "(e.g. OpenZeppelin ReentrancyGuard) around the affected external calls."),
    (("missing-zero",),
     "Add an explicit `require(addr != address(0))` (or custom-error) check "
     "before assigning or using the address."),
    (("solc", "pragma"),
     "Pin the Solidity pragma to a single, recent, audited compiler version "
     "rather than a floating range."),
    (("naming", "convention"),
     "Follow the Solidity style guide for naming (mixedCase for functions/"
     "variables, CapWords for contracts, UPPER_CASE for constants)."),
    (("unused", "dead-code"),
     "Remove unused code and state to reduce attack surface and gas cost."),
    (("tx-origin",),
     "Use `msg.sender` for authorization instead of `tx.origin`."),
    (("uninitialized",),
     "Initialize the flagged variable explicitly, or confirm the default is "
     "intended and document it."),
]

TITLE_OVERRIDES = {
    "solc-version": "Floating / Outdated Compiler Version",
    "reentrancy-eth": "Reentrancy (ETH)",
    "reentrancy-no-eth": "Reentrancy (No ETH)",
    "missing-zero-check": "Missing Zero-Address Validation",
    "naming-convention": "Naming Convention",
    "pragma": "Inconsistent Pragma",
    "dead-code": "Dead Code",
    "assembly": "Use of Inline Assembly",
    "low-level-calls": "Low-Level Call",
}


def _match(rules, check, default):
    c = check.lower()
    for keys, val in rules:
        if any(k in c for k in keys):
            return val
    return default


def humanize(check):
    if check in TITLE_OVERRIDES:
        return TITLE_OVERRIDES[check]
    return check.replace("-", " ").replace("_", " ").title()


def _el_filename(el):
    sm = el.get("source_mapping") or {}
    return (sm.get("filename_short") or sm.get("filename_relative")
            or sm.get("filename_used") or sm.get("filename_absolute")
            or sm.get("filename") or "")


def _is_dependency(fname):
    f = (fname or "").replace("\\", "/")
    return "node_modules/" in f or "/lib/" in f or f.startswith("lib/")


def detector_touches_project(det):
    """True if any element is in the project's own code (not a dependency)."""
    files = [f for f in (_el_filename(el) for el in det.get("elements", [])) if f]
    if not files:
        return False
    return any(not _is_dependency(f) for f in files)


def location_of(det, sol_file):
    """'file: lines', preferring the project element; filename as basename."""
    els = sorted(det.get("elements", []),
                 key=lambda el: 1 if _is_dependency(_el_filename(el)) else 0)
    for el in els:
        sm = el.get("source_mapping") or {}
        lines = sm.get("lines") or []
        fname = os.path.basename(_el_filename(el)) or sol_file or "source"
        if lines:
            return f"{fname}: {', '.join(str(n) for n in lines[:6])}"
        return fname
    return sol_file or "source"


def clean(text):
    return " ".join(str(text or "").split()).strip()


def parse_slither(sl, project, prefix, sol_file):
    if not isinstance(sl, dict):
        raise ValueError("Slither JSON root is not an object")
    if sl.get("success") is False and not (sl.get("results") or {}).get("detectors"):
        err = clean(sl.get("error") or "Slither reported failure (likely a "
                    "compilation error - check imports / solc version).")
        raise RuntimeError(err)

    dets = (sl.get("results") or {}).get("detectors") or []
    total_raw = len(dets)
    dets = [d for d in dets if detector_touches_project(d)]
    excluded = total_raw - len(dets)

    # Order by severity (High first), then keep stable order within a level.
    sev_rank = {"High": 0, "Medium": 1, "Low": 2, "Informational": 3, "Optimization": 4}
    dets = sorted(dets, key=lambda d: sev_rank.get(d.get("impact"), 5))

    findings = []
    for i, det in enumerate(dets, 1):
        check = det.get("check", "unknown")
        impact = det.get("impact", "Informational")
        sev = SEVERITY_MAP.get(impact, "Informational")
        conf = det.get("confidence", "")
        desc = clean(det.get("description"))
        if conf:
            desc = f"{desc} (Slither detector `{check}`, {impact.lower()} impact, " \
                   f"{conf.lower()} confidence.)"
        else:
            desc = f"{desc} (Slither detector `{check}`.)"
        findings.append({
            "id": f"{prefix}-{i:02d}",
            "title": humanize(check),
            "category": _match(CATEGORY_RULES, check, "Security"),
            "severity": sev,
            "status": "Pending",
            "location": location_of(det, sol_file),
            "description": desc,
            "recommendation": _match(
                RECO_RULES, check,
                "Review the flagged code and apply the appropriate mitigation; "
                "confirm the behaviour is intended if this is a false positive."),
        })

    approach = (
        "This report is generated automatically from a Slither static-analysis "
        "run over the uploaded contract. Findings correspond to Slither detectors "
        "that reference the project's own source; results located entirely within "
        "third-party dependencies (e.g. node_modules) are excluded.\n"
        "Important:\n"
        "- Static analysis surfaces common patterns; it is not exhaustive and can "
        "produce false positives and false negatives.\n"
        "- Centralization, business-logic, and economic risks generally require "
        "manual review and are not fully covered here.\n"
        "- This is an AI-assisted internal review aid, not a professional audit or "
        "certification. Verify important findings against the source.")
    if excluded:
        approach += (f"\nNote: {excluded} finding(s) located entirely within "
                     "third-party dependencies were excluded from this report.")

    spec = {
        "project": project,
        "assessor": "TrueL1",
        "report_type": "Automated (Slither)",
        "type": "Solidity Smart Contract",
        "ecosystem": "",
        "language": "Solidity",
        "methods": "Static Analysis (Slither)",
        "scope": [sol_file] if sol_file else [],
        "approach": approach,
        "findings": findings,
    }
    return spec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slither_json", nargs="?", default="-",
                    help="Slither --json output file, or '-' for stdin")
    ap.add_argument("--project", default="Contract")
    ap.add_argument("--prefix", default="F", help="finding ID prefix (e.g. AYE)")
    ap.add_argument("--file", dest="sol_file", default="", help="the .sol filename")
    ap.add_argument("--ecosystem", default="")
    ap.add_argument("--output", "-o", default="-")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.slither_json == "-" else open(args.slither_json).read()
    try:
        sl = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Could not parse Slither JSON: {e}", file=sys.stderr)
        sys.exit(2)

    spec = parse_slither(sl, args.project, args.prefix, args.sol_file)
    if args.ecosystem:
        spec["ecosystem"] = args.ecosystem

    out = json.dumps(spec, indent=2)
    if args.output == "-":
        print(out)
    else:
        with open(args.output, "w") as f:
            f.write(out)
        print(f"Wrote {args.output} ({len(spec['findings'])} findings)")


if __name__ == "__main__":
    main()
