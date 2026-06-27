const hre = require("hardhat");
const { ethers } = hre;

// ====== EDIT THIS after deploying LogisticsRegistry ======
const LOGISTICS_CONTRACT = "0xYOUR_LOGISTICS_CONTRACT_ADDRESS";
// =========================================================

// Usage:
//   npx hardhat run --network fme scripts/add-logistics.js "DPP-ID" "status" "location" true "note"
// Hardhat passes script args after the script name in process.argv.

async function main() {
  const [s] = await ethers.getSigners();

  if (LOGISTICS_CONTRACT.indexOf("YOUR_LOGISTICS") !== -1) {
    throw new Error("Set LOGISTICS_CONTRACT at the top of scripts/add-logistics.js");
  }

  // collect args after the script filename
  const argv = process.argv;
  const meIdx = argv.findIndex(a => a.includes("add-logistics.js"));
  const args = meIdx >= 0 ? argv.slice(meIdx + 1) : argv.slice(2);

  const [dppId, status, location, sealStr, note] = args;
  if (!dppId || !status || !location) {
    throw new Error('Usage: add-logistics.js "DPP-ID" "status" "location" true|false "note"');
  }
  const sealIntact = String(sealStr).toLowerCase() !== "false";
  const noteVal = note || "";

  const abi = [
    "function addEvent(string dppId,string status,string location,bool sealIntact,string note)",
    "function eventCount(string) view returns (uint256)"
  ];
  const c = new ethers.Contract(LOGISTICS_CONTRACT, abi, s);

  console.log("Recording logistics event...");
  console.log("  DPP ID:  ", dppId);
  console.log("  Status:  ", status);
  console.log("  Location:", location);
  console.log("  Seal:    ", sealIntact ? "intact" : "BROKEN");
  console.log("  Note:    ", noteVal || "(none)");

  const tx = await c.addEvent(dppId, status, location, sealIntact, noteVal);
  const r = await tx.wait();

  const count = await c.eventCount(dppId);
  console.log("\nRecorded. tx:", r.hash);
  console.log(dppId + " now has " + count.toString() + " logistics events.");
}

main().catch((e) => { console.error(e); process.exitCode = 1; });
