# TrueLayer1 DPP — Deploy Guide

The combined DPP proof contract for FME Layer1. One contract, five registries
(product, license, tag, certificate, ownership). Deploys the same way as NCK.

---

## Files

- `TrueLayer1DPP.sol` — the contract
- `deploy-dpp.js` — deploy script (also seeds the demo product JIP-DLX-001847)

---

## Step 1 — Add these files to your GitHub repo

In your `aungbu/ayet-token` repo (GitHub web editor — no truncation):

1. Create `dpp/TrueLayer1DPP.sol` → paste the contract
2. Create `dpp/deploy-dpp.js` → paste the deploy script
3. Commit.

---

## Step 2 — On the server, set up the project folder

```bash
# New isolated folder — copies the working NCK setup (node_modules, config, .env)
mkdir -p /opt/FME/contracts/truelayer1-dpp
cp -r /opt/FME/contracts/nck-token/node_modules /opt/FME/contracts/truelayer1-dpp/
cp /opt/FME/contracts/nck-token/hardhat.config.js /opt/FME/contracts/truelayer1-dpp/
cp /opt/FME/contracts/nck-token/package.json /opt/FME/contracts/truelayer1-dpp/
cp /opt/FME/contracts/nck-token/.env /opt/FME/contracts/truelayer1-dpp/
chmod 600 /opt/FME/contracts/truelayer1-dpp/.env
mkdir -p /opt/FME/contracts/truelayer1-dpp/contracts
mkdir -p /opt/FME/contracts/truelayer1-dpp/scripts
```

---

## Step 3 — Pull the contract files from GitHub

```bash
cd /tmp
git clone https://github.com/aungbu/ayet-token.git dpp-pull
cp /tmp/dpp-pull/dpp/TrueLayer1DPP.sol /opt/FME/contracts/truelayer1-dpp/contracts/
cp /tmp/dpp-pull/dpp/deploy-dpp.js     /opt/FME/contracts/truelayer1-dpp/scripts/
rm -rf /tmp/dpp-pull

# Confirm both landed:
ls /opt/FME/contracts/truelayer1-dpp/contracts/
ls /opt/FME/contracts/truelayer1-dpp/scripts/
```

---

## Step 4 — Compile and deploy

```bash
cd /opt/FME/contracts/truelayer1-dpp
npx hardhat compile
npx hardhat run scripts/deploy-dpp.js --network fme
```

The script prints:
- **Contract address** — save this
- **Deployment tx hash**
- **Demo product tx hash** (JIP-DLX-001847 registered on-chain)
- Confirms `isAuthentic('JIP-DLX-001847') = true`

---

## Notes

- Uses the same `DEPLOYER_PRIVATE_KEY` and `INITIAL_OWNER` from `.env` as NCK.
- The contract uses standard (non-upgradeable) OpenZeppelin `Ownable` — simpler
  than the token. Already installed in node_modules.
- On-chain stores only IDs, hashes, status, timestamps. No personal data.
- After deploy, the demo product is queryable on the explorer and can be wired
  into the dpp.truel1.com passport page.
