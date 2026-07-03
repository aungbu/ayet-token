#!/usr/bin/env python3
"""
TrueL1 reports index generator (interactive).
Scans /opt/ai-temp/reports and writes index.html with:
  - click-to-sort columns (Contract / Date+Time / Stage / Format), asc & desc
  - client-side pagination, 50 rows per page
  - American-English dates/times
Run standalone (rag-style) or import rebuild_reports_index().
"""
import os, re, json, html, datetime

REPORTS = os.environ.get("TRUEL1_REPORTS_DIR", "/opt/ai-temp/reports")
PER_PAGE = 50

def _scan():
    items = []
    for fn in os.listdir(REPORTS):
        if fn == "index.html" or fn.startswith("."):
            continue
        if not fn.lower().endswith((".pdf", ".html", ".md")):
            continue
        path = os.path.join(REPORTS, fn)
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(path))
        name, dt = fn, mtime
        low = fn.lower()
        stage = "Final" if "-final-" in low else ("Preliminary" if "-preliminary-" in low else "")
        m = re.search(r"(.+?)-(?:final|preliminary)?-?(?:audit-)?(\d{8})-(\d{6})\.(pdf|html|md)$", fn, re.I)
        if m:
            name = m.group(1).strip("-") or fn
            try:
                dt = datetime.datetime.strptime(m.group(2)+m.group(3), "%Y%m%d%H%M%S")
            except Exception:
                dt = mtime
        ext = low.rsplit(".", 1)[-1]
        items.append({
            "name": name,
            "file": fn,
            "ext": ext,
            "stage": stage,
            "ts": int(dt.timestamp()),
            "date": dt.strftime("%B %d, %Y").replace(" 0", " "),
            "time": dt.strftime("%I:%M %p").lstrip("0"),
        })
    return items

def rebuild_reports_index():
    items = _scan()
    data_json = json.dumps(items)
    gen = datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p").replace(" 0", " ")
    total = len(items)
    doc = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TrueL1 - Audit Reports</title><style>
:root{--navy:#1f3a5f;--red:#d21c46;--ink:#222;--muted:#667;--line:#e6ebf1;}
*{box-sizing:border-box;}
body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;color:var(--ink);background:#f6f8fb;}
header{background:var(--navy);color:#fff;padding:26px 32px;}
header h1{margin:0;font-size:24px;letter-spacing:.5px;}
header .sub{opacity:.85;font-size:13px;margin-top:5px;}
.wrap{max-width:1040px;margin:24px auto;padding:0 20px;}
.bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;gap:12px;flex-wrap:wrap;}
.search{flex:1;min-width:200px;}
.search input{width:100%;padding:9px 12px;border:1px solid var(--line);border-radius:8px;font-size:14px;background:#fff;}
.count{color:var(--muted);font-size:13px;white-space:nowrap;}
.card{background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden;box-shadow:0 1px 3px rgba(20,40,80,.05);}
table{width:100%;border-collapse:collapse;font-size:14px;}
th{text-align:left;background:#f0f4f9;color:var(--muted);font-weight:600;padding:12px 16px;border-bottom:1px solid var(--line);font-size:12px;text-transform:uppercase;letter-spacing:.4px;cursor:pointer;user-select:none;white-space:nowrap;}
th.sortable:hover{background:#e7edf5;color:var(--navy);}
th .arrow{opacity:.4;font-size:10px;margin-left:5px;}
th.active .arrow{opacity:1;color:var(--red);}
td{padding:13px 16px;border-bottom:1px solid var(--line);}
tr:last-child td{border-bottom:none;}
tbody tr:hover td{background:#fafcff;}
.nm{font-weight:600;color:var(--navy);}
.ext{font-size:11px;font-weight:700;padding:2px 8px;border-radius:20px;}
.ext-pdf{background:#fde8ec;color:var(--red);}.ext-html{background:#e7f0ff;color:#1b5cbf;}.ext-md{background:#eef1f5;color:#556;}
.stg{font-size:11px;font-weight:700;padding:2px 9px;border-radius:20px;background:#eef1f5;color:#667;}
.stg-Final{background:#e5f6ec;color:#1b7a3d;}.stg-Preliminary{background:#fff2df;color:#9a6212;}
a.view{color:var(--red);text-decoration:none;font-weight:600;}a.view:hover{text-decoration:underline;}
.empty{text-align:center;color:var(--muted);padding:34px;}
.pager{display:flex;justify-content:center;align-items:center;gap:6px;margin:18px 0 4px;flex-wrap:wrap;}
.pager button{border:1px solid var(--line);background:#fff;color:var(--navy);padding:7px 12px;border-radius:7px;font-size:13px;cursor:pointer;font-weight:600;}
.pager button:hover:not(:disabled){background:#f0f4f9;}
.pager button:disabled{opacity:.4;cursor:default;}
.pager button.active{background:var(--navy);color:#fff;border-color:var(--navy);}
.pager .info{color:var(--muted);font-size:13px;margin:0 8px;}
footer{max-width:1040px;margin:14px auto 40px;padding:0 20px;color:var(--muted);font-size:12px;line-height:1.6;}
</style></head><body>
<header><h1>TrueL1 &mdash; Smart Contract Audit Reports</h1>
<div class="sub">FME Layer 1 &middot; AI-assisted review aid &mdash; not a certified audit</div></header>
<div class="wrap">
  <div class="bar">
    <div class="search"><input id="q" type="text" placeholder="Search contract name..."></div>
    <div class="count" id="count"></div>
  </div>
  <div class="card">
    <table>
      <thead><tr>
        <th class="sortable" data-k="name">Contract<span class="arrow"></span></th>
        <th class="sortable" data-k="ts">Date &amp; Time<span class="arrow"></span></th>
        <th class="sortable" data-k="stage">Stage<span class="arrow"></span></th>
        <th class="sortable" data-k="ext">Format<span class="arrow"></span></th>
        <th></th>
      </tr></thead>
      <tbody id="rows"></tbody>
    </table>
  </div>
  <div class="pager" id="pager"></div>
</div>
<footer>Reports are generated by TrueL1 automated tooling (Slither static analysis with AI-assisted
review). Preliminary reports indicate issues to resolve; final reports are issued after remediation.
None constitute a professional or certified audit. Index generated __GEN__ &middot; __TOTAL__ report(s).</footer>
<script>
const DATA = __DATA__;
const PER = __PER__;
let sortKey = "ts", sortDir = -1, page = 1, q = "";

function filtered(){
  let a = DATA;
  if(q){ const s=q.toLowerCase(); a = a.filter(r => r.name.toLowerCase().includes(s)); }
  a = a.slice().sort((x,y)=>{
    let vx=x[sortKey], vy=y[sortKey];
    if(typeof vx==="string"){ vx=vx.toLowerCase(); vy=(vy||"").toLowerCase(); }
    if(vx<vy) return -1*sortDir; if(vx>vy) return 1*sortDir; return 0;
  });
  return a;
}
function render(){
  const a = filtered();
  const pages = Math.max(1, Math.ceil(a.length/PER));
  if(page>pages) page=pages;
  const start=(page-1)*PER, slice=a.slice(start, start+PER);
  const rows=document.getElementById("rows");
  if(slice.length===0){ rows.innerHTML='<tr><td colspan="5" class="empty">No reports found.</td></tr>'; }
  else{
    rows.innerHTML = slice.map(r=>{
      const badge = r.ext.toUpperCase();
      const stg = r.stage ? '<span class="stg stg-'+r.stage+'">'+r.stage+'</span>' : '<span class="stg">&mdash;</span>';
      return '<tr><td class="nm">'+esc(r.name)+'</td>'
        +'<td>'+r.date+' &middot; '+r.time+'</td>'
        +'<td>'+stg+'</td>'
        +'<td><span class="ext ext-'+r.ext+'">'+badge+'</span></td>'
        +'<td><a class="view" href="'+esc(r.file)+'">View &rarr;</a></td></tr>';
    }).join("");
  }
  // headers
  document.querySelectorAll("th.sortable").forEach(th=>{
    const k=th.dataset.k, ar=th.querySelector(".arrow");
    th.classList.toggle("active", k===sortKey);
    ar.textContent = k===sortKey ? (sortDir<0?"\u25BC":"\u25B2") : "\u25B8";
  });
  document.getElementById("count").textContent = a.length+" report"+(a.length===1?"":"s");
  // pager
  const pg=document.getElementById("pager"); pg.innerHTML="";
  const mk=(label,pnum,dis,act)=>{ const b=document.createElement("button");
    b.textContent=label; if(dis)b.disabled=true; if(act)b.classList.add("active");
    b.onclick=()=>{ page=pnum; render(); window.scrollTo({top:0,behavior:"smooth"}); }; return b; };
  if(pages>1){
    pg.appendChild(mk("\u2039 Prev", Math.max(1,page-1), page===1, false));
    let lo=Math.max(1,page-2), hi=Math.min(pages,lo+4); lo=Math.max(1,hi-4);
    if(lo>1){ pg.appendChild(mk("1",1,false,page===1)); if(lo>2){const s=document.createElement("span");s.className="info";s.textContent="\u2026";pg.appendChild(s);} }
    for(let i=lo;i<=hi;i++) pg.appendChild(mk(String(i),i,false,i===page));
    if(hi<pages){ if(hi<pages-1){const s=document.createElement("span");s.className="info";s.textContent="\u2026";pg.appendChild(s);} pg.appendChild(mk(String(pages),pages,false,page===pages)); }
    pg.appendChild(mk("Next \u203A", Math.min(pages,page+1), page===pages, false));
    const info=document.createElement("span"); info.className="info"; info.textContent="Page "+page+" of "+pages; pg.appendChild(info);
  }
}
function esc(s){ return s.replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }
document.querySelectorAll("th.sortable").forEach(th=>{
  th.onclick=()=>{ const k=th.dataset.k;
    if(k===sortKey) sortDir*=-1; else { sortKey=k; sortDir = (k==="ts")?-1:1; }
    page=1; render(); };
});
document.getElementById("q").addEventListener("input", e=>{ q=e.target.value; page=1; render(); });
render();
</script>
</body></html>"""
    doc = (doc.replace("__DATA__", data_json)
              .replace("__PER__", str(PER_PAGE))
              .replace("__GEN__", gen)
              .replace("__TOTAL__", str(total)))
    with open(os.path.join(REPORTS, "index.html"), "w") as f:
        f.write(doc)
    return total

if __name__ == "__main__":
    n = rebuild_reports_index()
    print(f"Wrote {REPORTS}/index.html with {n} report(s).")
