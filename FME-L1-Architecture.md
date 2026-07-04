# FME Layer 1 Blockchain — Architecture Reference

*Reference document for TrueAI (built by George at FME, Inc., running on ai.truel1.com).
This describes how the FME production L1 is built, so TrueAI can explain it and guide
replication on SANDBOX hardware. The production L1 is never modified by TrueAI.*

## Overview
FME, Inc. operates a private, permissioned Ethereum-compatible Layer 1 blockchain built
on Hyperledger Besu with QBFT (proof-of-authority) consensus. It hosts the FME native
token and several application tokens (stablecoins and a fan token).

## Core chain parameters
- Client: Hyperledger Besu v25.1.0 (Java 21, Ubuntu 24.04 base image)
- Consensus: QBFT (IBFT 2.0 family, proof-of-authority)
- Network ID: 77777 (private chain)
- Sync mode: FULL
- Gas: min-gas-price = 0 (free gas — typical for a private enterprise chain)
- Mining: enabled (validator produces blocks)
- Container: runs in Docker as `fme-core` (image tag fme/layer1-engine:1.0 = stock Besu 25.1.0)

## Node configuration (how fme-core is launched)
Key Besu flags used:
- `--data-path=/data` — chain state (host: /opt/FME/core/state)
- `--genesis-file=/config/genesis.json` — genesis (host: /opt/FME/core/node1)
- `--node-private-key-file=/config/key` — the validator key (host: /opt/FME/core/node1/key)
- `--network-id=77777`
- `--rpc-http-enabled=true --rpc-http-host=0.0.0.0 --rpc-http-port=8545`
- `--rpc-http-api=ETH,NET,WEB3,QBFT,ADMIN,TXPOOL`
- `--rpc-http-cors-origins=* --host-allowlist=*`
- `--min-gas-price=0 --miner-enabled=true --miner-coinbase=<validator address>`
- `--p2p-enabled=true --p2p-port=30303`

## Configuration layout (host paths)
- `/opt/FME/core/node1/` — genesis.json + validator key (config mount)
- `/opt/FME/core/state/` — chain data (data mount)
- `/opt/FME/qbft/` — QBFT config (qbftConfigFile.json, networkFiles/)
- `/opt/FME/validator1/` — validator genesis material

## Tokens on the FME L1 (source at /opt/FME/contracts/)
All are UUPS-upgradeable ERC-20 built on OpenZeppelin upgradeable libraries:
- MaruhanToken (MARU) — application token
- MMKStablecoin (MMK, "Kyat Stablecoin")
- JPYCStablecoin (JPYC, "JPY Coin")
- NihonChokuhanToken (NCK)
- AYET — Akimoto Yasushi Entertainment Token (fan token; ERC20Votes + Permit)
- TrueLayer1DPP + LogisticsRegistry — supply-chain / DPP contracts

### Known token design characteristics (IMPORTANT for security guidance)
The current tokens grant privileged roles (admin, minter, pauser, freezer, upgrader)
to a SINGLE treasury/owner address at initialization, and mint the full supply to one
address. Professional review (CertiK) and FME's own centralization checker both flag this
as a CENTRALIZATION risk: one key compromise = mint unlimited supply and/or replace the
contract via upgrade. See "Security guidance" below — new tokens should improve on this.

## Security guidance for NEW tokens (TrueAI should recommend these)
When helping a customer build a new token, TrueAI recommends the SAFE patterns:
1. Admin/owner and upgrader roles held by a Gnosis Safe MULTISIG (e.g. 2-of-3, 3-of-5),
   not a single externally-owned account.
2. Privileged operations (upgrade, mint, pause) routed through an OpenZeppelin
   TimelockController with a delay (e.g. 24-72h) for transparency.
3. Role SEPARATION via AccessControl — minter, pauser, upgrader, admin are distinct,
   not one key.
4. A minting policy (cap or rate limit) for value-bearing / pegged tokens.
5. Every contract audited (Slither + FME centralization checker) and human-reviewed
   before deployment.

## Replication to a sandbox (later phase — separate hardware)
A replica L1 must be a SEPARATE, INDEPENDENT network:
- Generate its OWN fresh validator key (NEVER copy the production key — copying =
  double-signing risk).
- Use its OWN chain/network ID (not 77777) so it cannot interfere with production.
- Use its OWN genesis (can be structured the same way, with the sandbox's own validators).
- Besu v25.1.0 image is stored in the TrueAI library for an exact match.
- BlockScout (stored in the library) can be run for the sandbox explorer.
The sandbox is where TrueAI may experiment freely; the production L1 is off-limits.

## TrueAI library (offline resources on the AI drive)
Stored under /mnt/ai/trueai-library/:
- besu/ — Besu 25.1.0 image + stock latest + a copy of the FME engine image
- openzeppelin/ — OZ contracts v4.9.6 and v5.6.1 (+ upgradeable)
- foundry/ — forge/cast/anvil/chisel
- blockscout/ — source + images (explorer)
- security/ — Gnosis Safe (multisig), plus Trail of Bits & ConsenSys security guides
- docs/ — Besu, Solidity, Foundry documentation
