const hre = require("hardhat");
const { ethers } = hre;

async function main() {
  const [deployer] = await ethers.getSigners();
  if (!deployer) {
    throw new Error("No deployer wallet found. Set DEPLOYER_PRIVATE_KEY in .env");
  }

  const initialOwner = process.env.INITIAL_OWNER;
  if (!ethers.isAddress(initialOwner)) {
    throw new Error("INITIAL_OWNER is missing or invalid in .env");
  }

  console.log("Deploying TrueLayer1DPP to FME Layer1...");
  console.log("Deployer:", deployer.address);
  console.log("Initial owner:", initialOwner);

  const DPP = await ethers.getContractFactory("TrueLayer1DPP");
  const dpp = await DPP.deploy(initialOwner);
  await dpp.waitForDeployment();

  const address = await dpp.getAddress();
  const deployTx = dpp.deploymentTransaction();

  console.log("\nDeployment complete.");
  console.log("TrueLayer1DPP address:", address);
  console.log("Deployment tx hash:", deployTx.hash);
  console.log("Owner:", await dpp.owner());

  // ---- Seed the demo product so the CEO can see a real on-chain record ----
  console.log("\nSeeding demo product JIP-DLX-001847 ...");
  const tx = await dpp.registerFull(
    "JIP-DLX-001847",          // dppId
    "JIP-DLX",                 // sku
    1847,                      // edition
    10000,                     // totalEditions
    "BATCH-2026-03",           // batch
    "Tokyo, Japan",            // origin
    "Publisher Alpha",         // ipHolder
    "Licensed Maker A",        // licensee
    "Japan / Global",          // territory
    "LIC-2026-0042",           // licenseNo
    "NFC-04A2B7C9"             // nfcId
  );
  const receipt = await tx.wait();

  console.log("Demo product registered.");
  console.log("Seed tx hash:", receipt.hash);
  console.log("\n=== SAVE THESE ===");
  console.log("Contract address:", address);
  console.log("Demo product tx:", receipt.hash);
  console.log("isAuthentic('JIP-DLX-001847'):", await dpp.isAuthentic("JIP-DLX-001847"));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
