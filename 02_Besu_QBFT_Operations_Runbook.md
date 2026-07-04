# 02 — Besu / QBFT Operations Runbook

*Day-to-day operations for the FME L1. TrueAI uses this to guide routine support. All
production actions follow doc 08 (pre-check / impact / verification / rollback, and never
restart fme-core without owner approval). Items marked [FME to complete] need FME input.*

## Health & status checks (safe, read-only)
- Container status: `docker ps --format '{{.Names}}\t{{.Status}}' | grep fme-core`
  (expect: Up ... (healthy))
- Current block height (via RPC, localhost only):
  `curl -s -X POST http://127.0.0.1:8545 -H 'Content-Type: application/json' \
   -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'`
- Peer count:
  `... "method":"net_peerCount" ...`
- QBFT validators list:
  `... "method":"qbft_getValidatorsByChainHeight" ...` [FME to confirm exact method/params]
- Logs (read-only): `docker logs --tail 100 fme-core`

## Routine operations TrueAI may guide (low-risk)
- Reading logs and explaining errors.
- Checking sync status, peer count, block production.
- Explaining RPC responses to customers.
- Checking a token balance / transaction status via read-only RPC calls.

## Operations that REQUIRE FME approval / escalation (see doc 08)
- Restarting / stopping fme-core (owner approval required).
- Adding/removing validators (quorum + Safe approval).
- Any change to genesis, keys, or node flags.
- Anything exposing RPC beyond localhost/firewalled access.

## Standard operating format for ANY production action
1. Pre-check (verify current state + that a backup exists)
2. Exact impact (what it does, what it affects)
3. Command (only if permitted by doc 08)
4. Verification (confirm success)
5. Rollback (how to undo)

## Monitoring
- GPU/AI monitoring: gpu-monitor.service (AI stack only, not the L1).
- [FME to complete: L1 monitoring/alerting setup — what watches block production, disk,
  peer count, and how the team is alerted.]

## Common routine tasks
- [FME to complete: e.g. how customers add a token to MetaMask (network 77777, RPC URL,
  chain details), how to read a transaction on the explorer, etc.]
