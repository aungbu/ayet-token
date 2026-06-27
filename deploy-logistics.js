const hre = require("hardhat");
const { ethers } = hre;

async function main() {
  const [deployer] = await ethers.getSigners();
  const initialOwner = process.env.INITIAL_OWNER;
  if (!ethers.isAddress(initialOwner)) throw new Error("INITIAL_OWNER missing/invalid in .env");

  console.log("Deploying LogisticsRegistry to FME Layer1...");
  console.log("Deployer:", deployer.address);

  const Reg = await ethers.getContractFactory("LogisticsRegistry");
  const reg = await Reg.deploy(initialOwner);
  await reg.waitForDeployment();

  const address = await reg.getAddress();
  const deployTx = reg.deploymentTransaction();
  console.log("\nLogisticsRegistry address:", address);
  console.log("Deployment tx:", deployTx.hash);

  // ---- Seed a believable journey for the demo product ----
  const demoId = "JIP-DLX-001847";
  console.log("\nSeeding logistics journey for", demoId, "...");

  const journey = [
    ["manufactured", "Tokyo Factory",      true,  "製造完了・品質検査済み"],
    ["shipped",      "Tokyo Factory",      true,  "JP Logistics 集荷"],
    ["hub_arrived",  "Osaka Hub",          true,  "中継ハブ到着"],
    ["out_delivery", "Osaka Hub",          true,  "配達中"],
    ["delivered",    "Osaka City",         true,  "配達完了・受領確認"]
  ];

  for (const [status, location, seal, note] of journey) {
    const tx = await reg.addEvent(demoId, status, location, seal, note);
    const r = await tx.wait();
    console.log("  +", status.padEnd(13), "@", location.padEnd(16), "tx:", r.hash.slice(0, 18) + "...");
  }

  const count = await reg.eventCount(demoId);
  console.log("\nDone. " + demoId + " now has " + count.toString() + " logistics events on-chain.");
  console.log("\n=== SAVE THIS ===");
  console.log("LogisticsRegistry address:", address);
}

main().catch((e) => { console.error(e); process.exitCode = 1; });
