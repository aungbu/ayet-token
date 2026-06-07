# AYET Admin Handbook

_Operator guide for the AYET fan-token platform on NCK Network._
_Last updated: 2026-06-07. Keep this document private._

---

## 1. What you're running

AYET is a fan-token platform on your self-hosted **NCK Network** (Hyperledger Besu, Chain ID 77777, gasless, ~2-second blocks). Fans use **MetaMask** to connect and use six on-chain programs. The website lives at **ayet.aucfans.com**; the blockchain/explorer lives at **l1.aucfans.com**.

**Golden rule: never modify `l1.aucfans.com`** — that's the live blockchain node. All website work happens under `ayet.aucfans.com` only.

---

## 2. Wallets (important)

| Wallet | Address | Use |
|---|---|---|
| **Owner / Safe** | `0x790107F335B02b220b78FF45b01Fec4B23C4454b` | Your admin wallet. Owns all contracts + the PegSwap. Use this in the Owner Panel and for all admin actions. Keep its seed phrase safe and offline. |
| **Deployer (compromised)** | `0x054dbBB401D28E219440BFe0C6700de7C4A922D5` | Only used to deploy contracts. Its key was exposed earlier, so treat it as **compromised** — never store value in it. Ownership of everything has been transferred away from it to the Owner wallet. |

- **Never type a private key or seed phrase into a website, a chat, or this document.** For deploys you set the deployer key only in your SSH terminal: `export DEPLOYER_KEY=0x...`
- The Owner wallet's key/seed should live only in your MetaMask + an offline backup.

---

## 3. Contract addresses

| Program | Contract | Notes |
|---|---|---|
| Vote | `0x59ae332c5b6cbcd07d2d556ef4809746e587a2c9` | Token-weighted polls; anyone creates polls |
| VIP | `0xc7ca312ac6142045f19d6403583161848f3373c4` | Token-gated tiers + reserve registry |
| Support Creators | `0x5e5026b3fdc38aff68397b341fc5499dd19daac7` | Direct AYET funding; owner can hide listings |
| Shop / EC | `0x366e0f02b2d6da4bc765be9d0551103c394348e6` | Pay AYET to redeem; owner lists products |
| Stage & Music | `0xedd58d403d64dc867958278d0bfa61d4bfb086ee` | Reserve a spot; owner creates events |
| Join (Membership) | `0x3771656dd4bd5b6f129ab52f2f8f22113b57783d` | One-tap membership for AYET holders |
| PegSwap (DEX) | `0xa93e9a0fc3449c79b04dbfa405f9574f938698ed` | Fixed-rate token swaps |

**Tokens** (gating/funding uses the DEX AYET): AYET `0x6e07234932fa3daa1e91ed78f551b2b5c7c75bac`, JPYC `0x6601ec3242808f300cbb9ce01aaaa1bab1cf6fea`, MARU `0x7c6244e16143dd3f2991481545a06c847733cf56`, MMK `0x7e70d8e5ee41c8299227b5934ea77fdf9f3db7ff`.

All six programs are owned by the Owner wallet and gating/paying in the DEX AYET. Each contract has `setToken(address)` (change the token) and `transferOwnership(address)` — use these rarely and carefully.

---

## 4. The Owner Panel — your main tool

**URL:** `https://ayet.aucfans.com/owner/` (behind the `admin` login)

1. Open the URL; enter the `admin` username and your password.
2. Click **Connect MetaMask** and connect the **Owner wallet** (`0x7901…`).
3. Use the tabs. Read-only data shows for any wallet, but **actions only work from the Owner wallet** (the contracts enforce this).

| Tab | What you can do |
|---|---|
| Overview | Live counts across all programs |
| Support | **Hide / Unhide** any project (scam moderation) |
| Shop | Add products, activate/deactivate, restock, read **orders** (for fulfilment) |
| Stage | Add events, activate/deactivate, read **reservists** (for fulfilment) |
| VIP | Read registrant list (wallet, amount, date) |
| Members | Read member list |
| Vote | Read polls and live tallies |

---

## 5. Day-to-day tasks

**Moderate a scam project (Support):** Owner Panel → Support → find the listing → **Hide**. It immediately disappears from the public page. Funds always go straight to each project's payout address — the contract never holds money — so hiding stops new contributions but cannot claw back past ones. This is why the page warns fans to verify before sending.

**Add a shop product:** Owner Panel → Shop → "Add product" (name, description, price in AYET, stock) → confirm in MetaMask. Use **Deactivate** to pull a product, **Restock** to add inventory. Payments arrive in the Owner wallet (treasury).

**Fulfil shop orders:** Owner Panel → Shop → Orders table shows buyer wallet, product, amount, date, and order # (shown to the buyer on the site). **Shipping/personal details are never on-chain** — collect them off-chain against the order ID.

**Add a stage/music event:** Owner Panel → Stage → "Add event" (title, description, capacity `0`=unlimited, min AYET `0`=any holder). Use **Show reservists** to get the list of wallets who reserved, for off-chain fulfilment.

**Read VIP/members/votes:** Owner Panel → respective tab. These are read-only lists.

**Change VIP tier thresholds** (Bronze 100 / Silver 1,000 / Gold 10,000 / Platinum 100,000 AYET): these are front-end values on the VIP page — ask your developer to edit and redeploy the page.

---

## 6. The admin login (Basic Auth)

Three pages are behind an HTTP Basic Auth login: **`/support/`**, **`/kyc/`**, **`/owner/`**. Username: `admin`.

- **Change the password** (in SSH): `htpasswd /etc/nginx/.ayet_htpasswd admin` then `nginx -s reload`. You type the new password at the prompt; it is never shown.
- **Add another user:** same command with a different username.
- The login protects the **web pages**. It does **not** gate the smart contracts (those are public on-chain; owner actions are still protected by the owner wallet key).

---

## 7. Deploying / updating pages

Two methods (the chunked method is the reliable fallback because GitHub raw sometimes serves stale/404):

1. **GitHub + curl:** upload the deploy script to the repo, then `curl -fsSL "https://raw.githubusercontent.com/aungbu/ayet-token/main/FILE.sh" -o /tmp/FILE.sh && bash /tmp/FILE.sh`.
2. **Direct paste:** open the deploy script and paste its contents straight into SSH.

Deploy scripts always print a `*_DONE` line on success. nginx config changes always run `nginx -t` before reloading, so a bad config can't take the site down. Config backups are saved under `/root/ayet-backups/`.

---

## 8. Backups

**Website backup (run regularly):**
```
mkdir -p /root/ayet-backups && tar -czf /root/ayet-backups/ayet_$(date +%Y%m%d_%H%M%S).tar.gz -C /var/www ayet.aucfans.com && ls -t /root/ayet-backups/ayet_*.tar.gz | tail -n +8 | xargs -r rm -- && echo "BACKUP DONE"
```

**Restore a website backup:**
```
tar -xzf /root/ayet-backups/ayet_YYYYMMDD_HHMMSS.tar.gz -C /var/www && nginx -s reload && echo "RESTORE DONE"
```

> **Still outstanding:** a full **server + blockchain-node** backup (node data + validator key). The website backup above does NOT cover the blockchain node. Losing the node key can break the chain — back this up separately and store it off-server.

---

## 9. Pre-launch checklist

- [ ] **KYC**: wire the page to a licensed eKYC provider; install their credentials server-side; confirm **FSA registration / compliance** before collecting any real ID. The `/kyc/` page today is a non-functional sample.
- [ ] **My Number**: only ever the **front** of the card; never the back / the 12-digit number.
- [ ] **Japanese proofread** of all site copy by a native speaker.
- [ ] **CertiK / Polygon** badges: swap "in progress / planned" for live links once real (cert URL + Polygon contract address).
- [ ] **Full node backup** completed and stored off-server.
- [ ] Test each program end-to-end on the live site with a real wallet.
- [ ] Confirm the `admin` password is strong and stored safely.

---

## 10. Security reminders

- Never modify `l1.aucfans.com`.
- Never share the Owner wallet seed phrase. No legitimate party will ask for it.
- The deployer wallet is compromised — never hold value there.
- Always verify you're on `ayet.aucfans.com` before connecting a wallet.
- Keep this handbook private (it maps out your admin surface).

---

_Questions or changes (new products, tier thresholds, new programs, KYC wiring): note them and bring them to your developer._
