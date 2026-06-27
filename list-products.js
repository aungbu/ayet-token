const hre = require("hardhat");
const { ethers } = hre;

const CONTRACT = "0xc29485B66eCA4F029af7cFd24af5B9f8826BCB1b";

async function main() {
  const [s] = await ethers.getSigners();
  const abi = [
    "function totalDPPs() view returns (uint256)",
    "function dppIds(uint256) view returns (string)",
    "function products(string) view returns (string sku, uint256 edition, uint256 totalEditions, string batch, string origin, uint256 createdAt, bool exists)",
    "function licenses(string) view returns (string ipHolder, string licensee, string territory, string licenseNo, uint256 registeredAt, bool exists)"
  ];
  const c = new ethers.Contract(CONTRACT, abi, s);

  const total = await c.totalDPPs();
  console.log("\nTrueLayer1DPP contract:", CONTRACT);
  console.log("Total products on-chain:", total.toString());
  console.log("=".repeat(70));

  for (let i = 0; i < Number(total); i++) {
    const id = await c.dppIds(i);
    const p = await c.products(id);
    const lic = await c.licenses(id);
    console.log(
      (i + 1) + ". " + id +
      "\n     SKU: " + p.sku +
      "  |  Edition: " + p.edition.toString() + "/" + p.totalEditions.toString() +
      "\n     Origin: " + p.origin +
      "  |  IP: " + (lic.exists ? lic.ipHolder : "—") +
      "  |  Maker: " + (lic.exists ? lic.licensee : "—") +
      "\n     Passport: https://dpp.truel1.com/" + id
    );
    console.log("-".repeat(70));
  }
}

main().catch((e) => { console.error(e); process.exitCode = 1; });
