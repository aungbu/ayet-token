// TrueLayer1 Logistics API — one-tap checkpoint recording
// Listens on 127.0.0.1 only. Nginx proxies /api/logistics/ with basic auth.
const express = require("express");
const { ethers } = require("ethers");
require("dotenv").config();

const PORT = process.env.PORT || 3801;
const RPC_URL = process.env.RPC_URL || "http://127.0.0.1:8545";
const CONTRACT = process.env.LOGISTICS_CONTRACT;
const PK = process.env.PRIVATE_KEY;

if (!CONTRACT || !PK) { console.error("Missing LOGISTICS_CONTRACT or PRIVATE_KEY in .env"); process.exit(1); }

const ABI = [
  "function addEvent(string dppId,string status,string location,bool sealIntact,string note)",
  "function eventCount(string) view returns (uint256)"
];

const provider = new ethers.JsonRpcProvider(RPC_URL);
const signer = new ethers.Wallet(PK, provider);
const contract = new ethers.Contract(CONTRACT, ABI, signer);

const STATUSES = ["manufactured","shipped","hub_arrived","out_delivery","delivered","inspected"];
const ID_RE = /^[A-Za-z0-9][A-Za-z0-9\-]{2,39}$/;

const app = express();
app.use(express.json({ limit: "8kb" }));

// simple in-memory rate limit: max 30 writes / 5 min
let hits = [];
function limited(){ const now=Date.now(); hits=hits.filter(t=>now-t<300000); if(hits.length>=30) return true; hits.push(now); return false; }

app.get("/health", async (_req,res)=>{
  try { const bn = await provider.getBlockNumber(); res.json({ok:true, block:bn, contract:CONTRACT, signer:signer.address}); }
  catch(e){ res.status(500).json({ok:false, error:String(e.message||e)}); }
});

app.post("/record", async (req,res)=>{
  try{
    if (limited()) return res.status(429).json({ok:false, error:"rate limit"});
    const { dppId, status, location, sealIntact, note } = req.body || {};
    if (!ID_RE.test(String(dppId||"")))      return res.status(400).json({ok:false, error:"invalid dppId"});
    if (!STATUSES.includes(String(status)))  return res.status(400).json({ok:false, error:"invalid status"});
    const loc = String(location||"").slice(0,60).trim();
    if (loc.length < 2)                      return res.status(400).json({ok:false, error:"invalid location"});
    const nt = String(note||"").slice(0,120);
    const seal = sealIntact === true || sealIntact === "true";

    const tx = await contract.addEvent(dppId, status, loc, seal, nt);
    const r  = await tx.wait();
    const count = await contract.eventCount(dppId);
    console.log(new Date().toISOString(), "recorded", dppId, status, loc, "seal="+seal, r.hash);
    res.json({ ok:true, tx:r.hash, block:r.blockNumber, count:Number(count),
               passport:"https://dpp.truel1.com/"+encodeURIComponent(dppId) });
  }catch(e){
    console.error("record error:", e.message||e);
    res.status(500).json({ok:false, error:String(e.message||e).slice(0,200)});
  }
});

app.listen(PORT, "127.0.0.1", ()=>console.log("logistics-api on 127.0.0.1:"+PORT+" → "+CONTRACT));
