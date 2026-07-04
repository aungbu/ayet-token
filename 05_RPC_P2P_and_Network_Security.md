# 05 — RPC / P2P & Network Security

*The network attack surface of the FME L1 and how it is protected. TrueAI never recommends
weakening these. Items marked [FME to complete].*

## RPC (JSON-RPC, port 8545)
- Enabled methods: ETH, NET, WEB3, QBFT, ADMIN, TXPOOL.
- Binds to 0.0.0.0 inside the container but is protected by the host firewall (ufw) and is
  NOT publicly exposed.
- ADMIN and DEBUG methods must NEVER be reachable from the public internet.
- For remote access, use a private path (VPN/Tailscale) or a firewall allowlist — never open
  8545 to the world (doc 08 rule 3).

## P2P (port 30303)
- Used for node-to-node communication. [FME to complete: which peers/enodes are expected.]

## Host firewall (ufw) — current posture
- Default deny incoming.
- SSH (22) allowed (key-only authentication; passwords disabled).
- 80/443 for nginx (public sites).
- 30303 tcp+udp for P2P.
- Docker bridge (172.17.0.0/16) allowed for internal container↔Ollama.
- Tailscale interface allowed (for roaming admin access).
- Webmin (10000) restricted to the LAN only.

## SSH hardening (current)
- Key-only (PasswordAuthentication no), fail2ban active.
- Admin roams on a changing IP → access via Tailscale (server 100.111.78.10) or office LAN.

## Public endpoints
- ai.truel1.com (TrueAI / audit), reverse-proxied via nginx with TLS.
- [FME to complete: full list of public endpoints and what each exposes.]

## Rules TrueAI enforces
- Never suggest exposing RPC publicly, disabling the firewall, or enabling ADMIN/DEBUG on a
  public interface. Escalate any non-trivial network change to the FME team.
