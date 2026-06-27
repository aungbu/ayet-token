const hre = require("hardhat");
const { ethers } = hre;
const fs = require("fs");
const path = require("path");

// ====== EDIT THIS: your deployed TrueLayer1DPP contract address ======
const CONTRACT_ADDRESS = "0xc29485B66eCA4F029af7cFd24af5B9f8826BCB1b";
// =====================================================================

// CSV file location (same folder as this script by default)
const CSV_FILE = path.join(__dirname, "products.csv");

async function main() {
  const [signer] = await ethers.getSigners();
  if (!signer) throw new Error("No wallet found. Set DEPLOYER_PRIVATE_KEY in .env");

  if (!ethers.isAddress(CONTRACT_ADDRESS)) {
    throw new Error("Set CONTRACT_ADDRESS at the top of this script");
  }
  if (!fs.existsSync(CSV_FILE)) {
    throw new Error("CSV not found at " + CSV_FILE);
  }

  console.log("Using account:", signer.address);
  console.log("DPP contract:  ", CONTRACT_ADDRESS);
  console.log("Reading CSV:   ", CSV_FILE, "\n");

  // ---- minimal ABI: just the function we call + the read check ----
  const ABI = [
    "function registerFull(string dppId,string sku,uint256 edition,uint256 totalEditions,string batch,string origin,string ipHolder,string licensee,string territory,string licenseNo,string nfcId) external",
    "function isAuthentic(string dppId) view returns (bool)",
    "function totalDPPs() view returns (uint256)"
  ];
  const dpp = new ethers.Contract(CONTRACT_ADDRESS, ABI, signer);

  // ---- parse CSV (simple comma split; no quoted-comma fields) ----
  const raw = fs.readFileSync(CSV_FILE, "utf8").trim();
  const lines = raw.split(/\r?\n/);
  const header = lines[0].split(",").map(h => h.trim());
  const rows = lines.slice(1).filter(l => l.trim().length > 0);

  const expected = ["dppId","sku","edition","totalEditions","batch","origin","ipHolder","licensee","territory","licenseNo","nfcId"];
  const headerOk = expected.every((h, i) => header[i] === h);
  if (!headerOk) {
    console.log("WARNING: CSV header doesn't match expected order.");
    console.log("Expected:", expected.join(","));
    console.log("Found:   ", header.join(","), "\n");
  }

  console.log("Found " + rows.length + " products to register.\n");

  let ok = 0, skip = 0, fail = 0;

  for (let i = 0; i < rows.length; i++) {
    const cols = rows[i].split(",").map(c => c.trim());
    const p = {
      dppId: cols[0], sku: cols[1],
      edition: cols[2], totalEditions: cols[3],
      batch: cols[4], origin: cols[5],
      ipHolder: cols[6], licensee: cols[7],
      territory: cols[8], licenseNo: cols[9], nfcId: cols[10]
    };

    if (!p.dppId) { console.log("  (row " + (i+1) + " empty, skipping)"); skip++; continue; }

    // skip if already on-chain (so re-running the script is safe)
    try {
      const already = await dpp.isAuthentic(p.dppId);
      if (already) {
        console.log("• " + p.dppId + " already registered — skipping");
        skip++;
        continue;
      }
    } catch (e) { /* ignore, attempt to register */ }

    try {
      process.stdout.write("→ registering " + p.dppId + " (edition " + p.edition + ") ... ");
      const tx = await dpp.registerFull(
        p.dppId, p.sku,
        BigInt(p.edition), BigInt(p.totalEditions),
        p.batch, p.origin,
        p.ipHolder, p.licensee, p.territory, p.licenseNo, p.nfcId
      );
      const receipt = await tx.wait();
      console.log("done  tx: " + receipt.hash);
      ok++;
    } catch (e) {
      console.log("FAILED: " + (e.shortMessage || e.message));
      fail++;
    }
  }

  const total = await dpp.totalDPPs();
  console.log("\n==== SUMMARY ====");
  console.log("Registered now:", ok);
  console.log("Skipped:       ", skip, "(already on-chain or empty)");
  console.log("Failed:        ", fail);
  console.log("Total products on contract:", total.toString());
}

main().catch((e) => { console.error(e); process.exitCode = 1; });
