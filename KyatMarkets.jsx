import { useState, useEffect, useMemo } from "react";
import {
  Wallet, Search, Clock, ArrowLeft, Activity, Briefcase,
  Zap, AlertTriangle, Check, TrendingUp,
} from "lucide-react";

/* ============================================================
   CONFIG — set these for your Kyat L1, then redeploy
   ============================================================ */
const CHAIN = {
  id: 0,                       // TODO: your L1 chainId (decimal). e.g. 88888
  name: "Kyat L1 Testnet",
  rpcUrl: "",                  // TODO: e.g. "https://rpc.kyat.net"
  explorerUrl: "",             // optional, e.g. "https://scan.kyat.net"
  // Your chain still needs a "native currency" entry for wallets, even though
  // users pay gas in pUSD via your gasless layer. Adjust name/symbol as needed.
  native: { name: "Kyat", symbol: "KYAT", decimals: 18 },
};

const PUSD = {
  address: "0x471C04100b3101C3A0714e24FDc50237E2935D3F", // your pUSD token
  symbol: "pUSD",
  decimals: 6,                 // auto-detected from the contract when RPC works
};

const GOLD = "#F5B301";
const GOLD_LT = "#FFD66B";
const GOLD_DK = "#C8860D";
const goldGrad = `linear-gradient(135deg, ${GOLD_LT} 0%, ${GOLD} 45%, ${GOLD_DK} 100%)`;

/* ============================================================
   Minimal ERC-20 reads via the injected wallet (no libraries)
   ============================================================ */
const SELECTOR = { decimals: "0x313ce567", symbol: "0x95d89b41", balanceOf: "0x70a08231" };

function pad32(addr) {
  return addr.toLowerCase().replace(/^0x/, "").padStart(64, "0");
}
function toBigInt(hex) {
  if (!hex || hex === "0x") return 0n;
  try { return BigInt(hex); } catch { return 0n; }
}
function decodeString(hex) {
  try {
    if (!hex || hex.length < 130) return "";
    const data = hex.slice(2);
    const len = parseInt(data.slice(64, 128), 16);
    const strHex = data.slice(128, 128 + len * 2);
    let s = "";
    for (let i = 0; i < strHex.length; i += 2) s += String.fromCharCode(parseInt(strHex.substr(i, 2), 16));
    return s.replace(/\u0000/g, "");
  } catch { return ""; }
}
function formatUnits(value, decimals) {
  let bi = value, neg = false;
  if (bi < 0n) { neg = true; bi = -bi; }
  const base = 10n ** BigInt(decimals);
  const whole = (bi / base).toString();
  let frac = (bi % base).toString().padStart(decimals, "0").replace(/0+$/, "");
  frac = frac.slice(0, 2);
  return (neg ? "-" : "") + whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + (frac ? "." + frac : "");
}
async function ethCall(to, data) {
  if (!window.ethereum) throw new Error("no wallet");
  return window.ethereum.request({ method: "eth_call", params: [{ to, data }, "latest"] });
}

/* ============================================================
   Demo market data (placeholder — swap for your on-chain markets)
   ============================================================ */
const MARKETS = [
  { id: "m1", category: "Crypto", q: "Will BTC close above $150k this year?", yes: 62, vol: 1284500, ends: "Dec 31" },
  { id: "m2", category: "Politics", q: "Will the proposed budget pass before the recess?", yes: 41, vol: 842300, ends: "Aug 14" },
  { id: "m3", category: "Sports", q: "Home side to win the league final?", yes: 55, vol: 2103900, ends: "Jul 02" },
  { id: "m4", category: "Economics", q: "Rate cut at the next central-bank meeting?", yes: 73, vol: 1567200, ends: "Sep 18" },
  { id: "m5", category: "Tech", q: "New flagship phone ships before Q4?", yes: 38, vol: 459800, ends: "Oct 01" },
  { id: "m6", category: "Crypto", q: "ETH/BTC ratio above 0.05 by quarter end?", yes: 29, vol: 731400, ends: "Sep 30" },
  { id: "m7", category: "Culture", q: "Sequel announced at the summer showcase?", yes: 67, vol: 318900, ends: "Aug 25" },
  { id: "m8", category: "Economics", q: "Inflation print under 3% next release?", yes: 48, vol: 988100, ends: "Jul 11" },
];
const CATEGORIES = ["All", "Crypto", "Politics", "Sports", "Economics", "Tech", "Culture"];

function fmtVol(n) {
  if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(0) + "k";
  return String(n);
}

/* ============================================================
   Components
   ============================================================ */
function Logo() {
  const [broken, setBroken] = useState(false);
  if (broken) {
    return (
      <div className="h-9 w-9 rounded-xl flex items-center justify-center shrink-0"
        style={{ background: goldGrad, boxShadow: "0 0 18px rgba(245,179,1,.35)" }}>
        <span className="font-bold text-black text-lg" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>K</span>
      </div>
    );
  }
  return (
    <img src="/kyat_logo.png" alt="Kyat" onError={() => setBroken(true)}
      className="h-9 w-9 rounded-xl object-cover shrink-0"
      style={{ boxShadow: "0 0 18px rgba(245,179,1,.25)" }} />
  );
}

function ProbBar({ yes }) {
  return (
    <div className="h-1.5 w-full rounded-full overflow-hidden flex bg-zinc-800">
      <div style={{ width: `${yes}%`, background: "linear-gradient(90deg,#10b981,#34d399)" }} />
      <div style={{ width: `${100 - yes}%`, background: "linear-gradient(90deg,#fb7185,#f43f5e)" }} />
    </div>
  );
}

function MarketCard({ m, onPick }) {
  return (
    <div className="group rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 flex flex-col gap-3
                    transition hover:border-zinc-700 hover:-translate-y-0.5">
      <div className="flex items-center justify-between text-[11px]">
        <span className="font-semibold tracking-widest uppercase" style={{ color: GOLD, fontFamily: "'JetBrains Mono', monospace" }}>
          {m.category}
        </span>
        <span className="flex items-center gap-1 text-zinc-500">
          <Clock size={12} /> {m.ends}
        </span>
      </div>

      <h3 className="text-zinc-100 leading-snug" style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600 }}>
        {m.q}
      </h3>

      <div className="mt-auto">
        <div className="flex items-end justify-between mb-1.5">
          <span className="text-zinc-500 text-xs">Yes</span>
          <span className="text-2xl text-zinc-50 leading-none" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            {m.yes}<span className="text-sm text-zinc-500">%</span>
          </span>
        </div>
        <ProbBar yes={m.yes} />
        <div className="grid grid-cols-2 gap-2 mt-3">
          <button onClick={() => onPick(m, "YES")}
            className="py-2 rounded-lg text-sm font-semibold text-emerald-300 bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-500/20 transition"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            Yes {m.yes}¢
          </button>
          <button onClick={() => onPick(m, "NO")}
            className="py-2 rounded-lg text-sm font-semibold text-rose-300 bg-rose-500/10 border border-rose-500/20 hover:bg-rose-500/20 transition"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            No {100 - m.yes}¢
          </button>
        </div>
        <div className="mt-3 text-[11px] text-zinc-500 flex items-center gap-1" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
          <Activity size={12} /> {fmtVol(m.vol)} {PUSD.symbol} vol
        </div>
      </div>
    </div>
  );
}

function Drawer({ open, onClose, children, title }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="absolute right-0 top-0 h-full w-full max-w-md bg-zinc-950 border-l border-zinc-800 overflow-y-auto">
        <div className="sticky top-0 bg-zinc-950/90 backdrop-blur border-b border-zinc-800 px-5 h-14 flex items-center gap-3">
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-100"><ArrowLeft size={18} /></button>
          <span className="text-zinc-200 font-semibold" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>{title}</span>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

function TradeTicket({ market, side, setSide, onSubmit }) {
  const [amt, setAmt] = useState("");
  const price = side === "YES" ? market.yes : 100 - market.yes;
  const n = parseFloat(amt || "0");
  const shares = price > 0 ? n / (price / 100) : 0;

  return (
    <div className="flex flex-col gap-5">
      <p className="text-zinc-100 text-lg leading-snug" style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600 }}>
        {market.q}
      </p>

      <div className="grid grid-cols-2 gap-2 p-1 rounded-xl bg-zinc-900 border border-zinc-800">
        {["YES", "NO"].map((s) => {
          const active = side === s;
          const c = s === "YES" ? "emerald" : "rose";
          return (
            <button key={s} onClick={() => setSide(s)}
              className={`py-2.5 rounded-lg text-sm font-semibold transition ${
                active ? `bg-${c}-500/20 text-${c}-300 border border-${c}-500/40`
                       : "text-zinc-500 hover:text-zinc-300"
              }`} style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              {s} · {s === "YES" ? market.yes : 100 - market.yes}¢
            </button>
          );
        })}
      </div>

      <label className="block">
        <span className="text-xs text-zinc-500">Amount ({PUSD.symbol})</span>
        <div className="mt-1 flex items-center rounded-xl border border-zinc-800 bg-zinc-900 px-3">
          <input value={amt} onChange={(e) => setAmt(e.target.value.replace(/[^0-9.]/g, ""))}
            inputMode="decimal" placeholder="0.00"
            className="w-full bg-transparent py-3 text-zinc-100 outline-none text-lg"
            style={{ fontFamily: "'JetBrains Mono', monospace" }} />
          <span className="text-zinc-500 text-sm">{PUSD.symbol}</span>
        </div>
        <div className="mt-2 flex gap-2">
          {[10, 50, 100, 500].map((v) => (
            <button key={v} onClick={() => setAmt(String(v))}
              className="px-2.5 py-1 rounded-md text-xs text-zinc-400 bg-zinc-900 border border-zinc-800 hover:border-zinc-600"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}>+{v}</button>
          ))}
        </div>
      </label>

      <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 text-sm space-y-2"
        style={{ fontFamily: "'JetBrains Mono', monospace" }}>
        <Row k="Avg price" v={`${price}¢`} />
        <Row k="Est. shares" v={shares ? shares.toFixed(2) : "0.00"} />
        <Row k="Max payout" v={`${shares ? shares.toFixed(2) : "0.00"} ${PUSD.symbol}`} hi />
      </div>

      <button disabled={!n}
        onClick={() => onSubmit({ market, side, amt: n, shares, price })}
        className="w-full py-3.5 rounded-xl font-bold text-black disabled:opacity-40 transition"
        style={{ background: goldGrad, fontFamily: "'Space Grotesk', sans-serif" }}>
        Place test order
      </button>

      <div className="flex gap-2 rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 text-xs text-amber-200/80">
        <AlertTriangle size={16} className="shrink-0 mt-0.5" style={{ color: GOLD }} />
        <span>
          Orders are simulated locally. To settle real trades in {PUSD.symbol}, wire this ticket to your
          market/exchange contract (address + ABI) and submit the on-chain transaction here.
        </span>
      </div>
    </div>
  );
}
function Row({ k, v, hi }) {
  return (
    <div className="flex justify-between">
      <span className="text-zinc-500">{k}</span>
      <span className={hi ? "" : "text-zinc-200"} style={hi ? { color: GOLD } : undefined}>{v}</span>
    </div>
  );
}

/* ============================================================
   App
   ============================================================ */
export default function App() {
  const [account, setAccount] = useState(null);
  const [chainOk, setChainOk] = useState(false);
  const [bal, setBal] = useState(null);
  const [decimals, setDecimals] = useState(PUSD.decimals);
  const [symbol, setSymbol] = useState(PUSD.symbol);
  const [cat, setCat] = useState("All");
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState(null);   // {market, side}
  const [positions, setPositions] = useState([]);
  const [showPortfolio, setShowPortfolio] = useState(false);
  const [toast, setToast] = useState(null);

  const hasWallet = typeof window !== "undefined" && !!window.ethereum;
  const configured = CHAIN.id > 0 && CHAIN.rpcUrl;

  const idHex = useMemo(() => "0x" + CHAIN.id.toString(16), []);

  async function refreshToken(addr) {
    try {
      const [dHex, sHex, bHex] = await Promise.all([
        ethCall(PUSD.address, SELECTOR.decimals),
        ethCall(PUSD.address, SELECTOR.symbol),
        ethCall(PUSD.address, SELECTOR.balanceOf + pad32(addr)),
      ]);
      const d = Number(toBigInt(dHex)) || PUSD.decimals;
      setDecimals(d);
      const s = decodeString(sHex);
      if (s) setSymbol(s);
      setBal(formatUnits(toBigInt(bHex), d));
    } catch {
      setBal(null); // chain/RPC not reachable yet — header shows a dash
    }
  }

  async function ensureNetwork() {
    if (!hasWallet || CHAIN.id <= 0) return false;
    try {
      await window.ethereum.request({ method: "wallet_switchEthereumChain", params: [{ chainId: idHex }] });
      setChainOk(true);
      return true;
    } catch (e) {
      if (e && e.code === 4902 && CHAIN.rpcUrl) {
        try {
          await window.ethereum.request({
            method: "wallet_addEthereumChain",
            params: [{
              chainId: idHex, chainName: CHAIN.name,
              rpcUrls: [CHAIN.rpcUrl],
              nativeCurrency: CHAIN.native,
              blockExplorerUrls: CHAIN.explorerUrl ? [CHAIN.explorerUrl] : undefined,
            }],
          });
          setChainOk(true);
          return true;
        } catch { return false; }
      }
      return false;
    }
  }

  async function connect() {
    if (!hasWallet) { setToast("No wallet found — install MetaMask or a compatible wallet."); return; }
    try {
      const accs = await window.ethereum.request({ method: "eth_requestAccounts" });
      const a = accs[0];
      setAccount(a);
      await ensureNetwork();
      refreshToken(a);
    } catch {
      setToast("Wallet connection was cancelled.");
    }
  }

  useEffect(() => {
    if (!hasWallet) return;
    const onAcc = (accs) => { setAccount(accs[0] || null); if (accs[0]) refreshToken(accs[0]); else setBal(null); };
    const onChain = () => { window.location.reload(); };
    window.ethereum.on?.("accountsChanged", onAcc);
    window.ethereum.on?.("chainChanged", onChain);
    return () => {
      window.ethereum.removeListener?.("accountsChanged", onAcc);
      window.ethereum.removeListener?.("chainChanged", onChain);
    };
  }, []); // eslint-disable-line

  function placeOrder({ market, side, amt, shares, price }) {
    setPositions((p) => [
      { id: Date.now(), q: market.q, side, amt, shares, price, ts: new Date().toLocaleTimeString() },
      ...p,
    ]);
    setPicked(null);
    setToast(`Test order placed · ${side} · ${amt} ${symbol}`);
  }

  useEffect(() => { if (toast) { const t = setTimeout(() => setToast(null), 3200); return () => clearTimeout(t); } }, [toast]);

  const shown = MARKETS.filter(
    (m) => (cat === "All" || m.category === cat) && m.q.toLowerCase().includes(query.toLowerCase())
  );

  const short = (a) => a.slice(0, 6) + "…" + a.slice(-4);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-200">
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500;700&display=swap');`}</style>
      <div style={{ fontFamily: "'Inter', sans-serif" }}>

        {/* Header */}
        <header className="sticky top-0 z-30 border-b border-zinc-800 bg-zinc-950/85 backdrop-blur">
          <div className="mx-auto max-w-6xl px-4 h-16 flex items-center gap-3">
            <Logo />
            <div className="flex items-baseline gap-1.5 mr-2">
              <span className="text-lg font-bold" style={{ color: GOLD, fontFamily: "'Space Grotesk', sans-serif" }}>Kyat</span>
              <span className="text-lg font-bold text-zinc-100" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>Markets</span>
              <span className="ml-1 px-1.5 py-0.5 rounded text-[9px] font-bold tracking-wider text-amber-300 bg-amber-500/10 border border-amber-500/20"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}>TESTNET</span>
            </div>

            <div className="hidden md:flex items-center flex-1 max-w-sm rounded-full border border-zinc-800 bg-zinc-900 px-3">
              <Search size={15} className="text-zinc-500" />
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search markets"
                className="w-full bg-transparent py-2 px-2 text-sm text-zinc-200 outline-none" />
            </div>

            <div className="ml-auto flex items-center gap-2">
              <button onClick={() => setShowPortfolio(true)}
                className="hidden sm:flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm text-zinc-300 border border-zinc-800 bg-zinc-900 hover:border-zinc-600">
                <Briefcase size={15} /> Portfolio
              </button>
              <div className="hidden sm:flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm border border-zinc-800 bg-zinc-900"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                <Activity size={14} style={{ color: GOLD }} />
                <span className="text-zinc-200">{bal ?? "—"}</span>
                <span className="text-zinc-500">{symbol}</span>
              </div>
              {account ? (
                <span className="px-3 py-2 rounded-lg text-sm text-black font-semibold" style={{ background: goldGrad, fontFamily: "'JetBrains Mono', monospace" }}>
                  {short(account)}
                </span>
              ) : (
                <button onClick={connect}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-sm font-bold text-black"
                  style={{ background: goldGrad, fontFamily: "'Space Grotesk', sans-serif" }}>
                  <Wallet size={15} /> Connect
                </button>
              )}
            </div>
          </div>

          <div className="mx-auto max-w-6xl px-4 pb-3 flex gap-2 overflow-x-auto">
            {CATEGORIES.map((c) => (
              <button key={c} onClick={() => setCat(c)}
                className={`px-3 py-1.5 rounded-full text-sm whitespace-nowrap transition border ${
                  cat === c ? "text-black border-transparent font-semibold" : "text-zinc-400 border-zinc-800 bg-zinc-900 hover:border-zinc-600"
                }`} style={cat === c ? { background: goldGrad } : undefined}>
                {c}
              </button>
            ))}
          </div>
        </header>

        {/* Config notice */}
        {!configured && (
          <div className="mx-auto max-w-6xl px-4 pt-4">
            <div className="flex gap-3 rounded-xl border border-amber-500/25 bg-amber-500/5 p-4 text-sm text-amber-100/85">
              <Zap size={18} className="shrink-0 mt-0.5" style={{ color: GOLD }} />
              <div>
                <p className="font-semibold text-amber-200" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>Connect this to your chain</p>
                <p className="mt-0.5">
                  Set <code className="text-amber-300">CHAIN.id</code> and <code className="text-amber-300">CHAIN.rpcUrl</code> at
                  the top of <code className="text-amber-300">KyatMarkets.jsx</code>. The {symbol} token is already pointed at{" "}
                  <code className="text-amber-300">{PUSD.address.slice(0, 10)}…</code>. Once set, the header shows your live balance.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Hero strip */}
        <div className="mx-auto max-w-6xl px-4 pt-6 pb-2">
          <h1 className="text-3xl sm:text-4xl text-zinc-50 leading-tight" style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700 }}>
            Trade what you <span style={{ color: GOLD }}>believe</span>.
          </h1>
          <p className="mt-1 text-zinc-400">Prediction markets on the Kyat chain, settled in {symbol}.</p>
        </div>

        {/* Markets */}
        <main className="mx-auto max-w-6xl px-4 py-4">
          {shown.length === 0 ? (
            <div className="py-20 text-center text-zinc-500">
              <TrendingUp size={28} className="mx-auto mb-3 opacity-40" />
              No markets match that. Try another category or search.
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {shown.map((m) => (
                <MarketCard key={m.id} m={m} onPick={(mk, side) => setPicked({ market: mk, side })} />
              ))}
            </div>
          )}
        </main>

        <footer className="mx-auto max-w-6xl px-4 py-10 text-xs text-zinc-600 border-t border-zinc-900 mt-6">
          Kyat Markets · test environment · markets shown are placeholder data.
        </footer>
      </div>

      {/* Trade drawer */}
      <Drawer open={!!picked} onClose={() => setPicked(null)} title="Place order">
        {picked && (
          <TradeTicket market={picked.market} side={picked.side}
            setSide={(s) => setPicked((p) => ({ ...p, side: s }))}
            onSubmit={placeOrder} />
        )}
      </Drawer>

      {/* Portfolio drawer */}
      <Drawer open={showPortfolio} onClose={() => setShowPortfolio(false)} title="Your test positions">
        {positions.length === 0 ? (
          <div className="py-16 text-center text-zinc-500">
            <Briefcase size={26} className="mx-auto mb-3 opacity-40" />
            No positions yet. Pick a market and place a test order.
          </div>
        ) : (
          <div className="space-y-3">
            {positions.map((p) => (
              <div key={p.id} className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
                <p className="text-zinc-200 text-sm" style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600 }}>{p.q}</p>
                <div className="mt-2 flex items-center justify-between text-xs" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                  <span className={p.side === "YES" ? "text-emerald-400" : "text-rose-400"}>{p.side} @ {p.price}¢</span>
                  <span className="text-zinc-400">{p.amt} {symbol} · {p.shares.toFixed(2)} sh</span>
                </div>
                <div className="mt-1 text-[10px] text-zinc-600">{p.ts}</div>
              </div>
            ))}
          </div>
        )}
      </Drawer>

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2 px-4 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-sm text-zinc-100 shadow-xl">
          <Check size={16} style={{ color: GOLD }} /> {toast}
        </div>
      )}
    </div>
  );
}
