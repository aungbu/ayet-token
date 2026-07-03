#!/usr/bin/env python3
"""
TrueL1 Audit Web
================
Upload a .sol file -> Slither static analysis -> TrueL1 assessment report.

Standard-library only (no Flask / no new packages). Runs on its OWN port
(default 3004). Findings come from Slither; the model is not used to invent
findings.

Improvements in this version:
  * Auto-selects the solc compiler version from each contract's pragma
    (so contracts with different pragmas all compile).
  * American English wording throughout.
  * Two-stage workflow: every report is PRELIMINARY unless "Mark as Final
    Assessment" is ticked; contracts that fail to compile get a clear
    "resolve and re-submit" preliminary notice.
  * Timestamped reports + a professional /reports/ index page.

Env:
  TRUEL1_AUDIT_PORT   listen port (default 3004)
  TRUEL1_PUBLIC_BASE  base URL where /opt/ai-temp/reports is served
"""
import os
import re
import json
import html
import shutil
import tempfile
import datetime
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("TRUEL1_AUDIT_PORT", "3004"))
PUBLIC_BASE = os.environ.get("TRUEL1_PUBLIC_BASE", "http://l1.aucfans.com:3003").rstrip("/")
TOOLS = "/opt/ai-temp"
REPORTS = "/opt/ai-temp/reports"
PYBIN = "/opt/ai-temp/slither-env/bin/python3"
SLITHER = "/usr/local/bin/slither"
SOLC_SELECT = "/opt/ai-temp/slither-env/bin/solc-select"
NODE_MODULES = os.environ.get("TRUEL1_NODE_MODULES", "/opt/ai-temp/AYET-workspace/node_modules")
MAX_UPLOAD = 3 * 1024 * 1024  # 3 MB

PAGE = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TrueL1 Audit</title><style>
:root{{color-scheme:dark}}
body{{background:#0B0E14;color:#E6E8EC;font-family:-apple-system,Helvetica,Arial,sans-serif;
margin:0;padding:0}}
.wrap{{max-width:640px;margin:0 auto;padding:48px 22px}}
.brand{{color:#E11D48;font-weight:700;letter-spacing:3px;font-size:14px}}
h1{{font-weight:300;font-size:30px;margin:6px 0 4px}}
.muted{{color:#99A1B0;font-size:13px;line-height:1.5}}
.card{{background:#12161F;border:1px solid #232A38;border-radius:12px;padding:22px;margin-top:22px}}
label{{display:block;color:#99A1B0;font-size:12px;text-transform:uppercase;
letter-spacing:1px;margin:14px 0 6px}}
input[type=text],input[type=file]{{width:100%;box-sizing:border-box;background:#0B0E14;
color:#E6E8EC;border:1px solid #232A38;border-radius:8px;padding:11px 12px;font-size:14px}}
input[type=file]{{padding:9px}}
.row{{display:flex;gap:12px}}.row>div{{flex:1}}
.check{{display:flex;align-items:center;gap:10px;margin-top:18px;color:#C7CDD9;font-size:14px}}
.check input{{width:18px;height:18px;accent-color:#E11D48}}
button{{margin-top:20px;background:#E11D48;color:#fff;border:none;border-radius:8px;
padding:12px 20px;font-size:15px;font-weight:600;cursor:pointer;width:100%}}
button:hover{{background:#c01840}}
a{{color:#E11D48}}
.ok{{border-color:#30A46C}}.err{{border-color:#E5484D}}.prelim{{border-color:#F5A623}}
.badge{{display:inline-block;font-size:11px;font-weight:700;padding:3px 10px;border-radius:20px;
letter-spacing:.5px}}
.badge-final{{background:#0f3d26;color:#5BD08C}}
.badge-prelim{{background:#3d2f0f;color:#F5C15B}}
code{{background:#1A1F2B;color:#E6C07B;padding:1px 5px;border-radius:4px;font-size:12px}}
pre{{white-space:pre-wrap;color:#99A1B0;font-size:12px;background:#0B0E14;
border:1px solid #232A38;border-radius:8px;padding:12px;overflow:auto;max-height:280px}}
.note{{color:#6b7688;font-size:11px;margin-top:26px;line-height:1.5}}
</style></head><body><div class="wrap">
<div class="brand">TRUEL1</div>
<h1>Smart Contract Audit</h1>
<div class="muted">Upload a Solidity file. It is analyzed with Slither and rendered
into a TrueL1 assessment report. This is an AI-assisted review aid, not a
professional audit or certification.</div>
{body}
<div class="note">Findings come from static analysis (Slither) and may include
false positives or false negatives; verify important findings against the source.
Reports are written to the shared reports folder and served from {base}. A full
list is available on the <a href="{base}/index.html">reports index</a>.</div>
</div></body></html>"""

FORM = """
<form class="card" method="POST" action="" enctype="multipart/form-data">
  <label>Solidity file (.sol)</label>
  <input type="file" name="solfile" accept=".sol" required>
  <div class="row">
    <div><label>Project name</label><input type="text" name="project" placeholder="AYET"></div>
    <div><label>Finding prefix</label><input type="text" name="prefix" placeholder="AYE"></div>
  </div>
  <label>Ecosystem (optional)</label>
  <input type="text" name="ecosystem" placeholder="BNB Smart Chain">
  <label class="check"><input type="checkbox" name="final" value="1">
    Mark as Final Assessment (leave unchecked for a preliminary review)</label>
  <button type="submit">Run analysis &amp; generate report</button>
</form>"""


def render_page(body):
    return PAGE.format(body=body, base=html.escape(PUBLIC_BASE))


def parse_multipart(content_type, body):
    m = re.search(r"boundary=([^;]+)", content_type or "")
    if not m:
        return {}
    boundary = m.group(1).strip().strip('"')
    delim = ("--" + boundary).encode()
    fields = {}
    for part in body.split(delim):
        part = part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        if b"\r\n\r\n" not in part:
            continue
        head, data = part.split(b"\r\n\r\n", 1)
        head_txt = head.decode("utf-8", "replace")
        nm = re.search(r'name="([^"]*)"', head_txt)
        if not nm:
            continue
        name = nm.group(1)
        fm = re.search(r'filename="([^"]*)"', head_txt)
        data = data[:-2] if data.endswith(b"\r\n") else data
        if fm is not None:
            fields[name] = {"filename": fm.group(1), "data": data}
        else:
            fields[name] = data.decode("utf-8", "replace").strip()
    return fields


def solc_version():
    try:
        r = subprocess.run(["solc", "--version"], capture_output=True, text=True, timeout=15)
        lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
        return lines[-1].strip() if lines else "unknown"
    except Exception:
        return "unknown"


def detect_pragma_version(sol_text):
    """Extract an exact solc version (e.g. '0.8.26') from the contract pragma."""
    m = re.search(r"pragma\s+solidity\s+([^;]+);", sol_text or "")
    if not m:
        return None
    versions = re.findall(r"(\d+)\.(\d+)\.(\d+)", m.group(1))
    if not versions:
        return None
    a, b, c = versions[0]
    return f"{a}.{b}.{c}"


def ensure_solc(version):
    """Install (if needed) and select the given solc version for this analysis."""
    if not version:
        return None
    try:
        inst = subprocess.run([SOLC_SELECT, "versions"], capture_output=True, text=True, timeout=30)
        if version not in (inst.stdout or ""):
            subprocess.run([SOLC_SELECT, "install", version], capture_output=True, text=True, timeout=180)
        subprocess.run([SOLC_SELECT, "use", version], capture_output=True, text=True, timeout=30)
        return version
    except Exception:
        return None


def build_remaps(node_modules):
    remaps = []
    if not node_modules or not os.path.isdir(node_modules):
        return remaps
    for entry in sorted(os.listdir(node_modules)):
        if entry.startswith("."):
            continue
        if os.path.isdir(os.path.join(node_modules, entry)):
            remaps.append(f"{entry}/=node_modules/{entry}/")
    return remaps


def run_audit(sol_bytes, filename, project, prefix, ecosystem, is_final):
    safe = os.path.basename(filename or "contract.sol")
    if not safe.lower().endswith(".sol"):
        safe += ".sol"
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", safe)
    work = tempfile.mkdtemp(prefix="tl-audit-")
    try:
        if os.path.isdir(NODE_MODULES):
            try:
                os.symlink(NODE_MODULES, os.path.join(work, "node_modules"))
            except OSError:
                pass
        with open(os.path.join(work, safe), "wb") as f:
            f.write(sol_bytes)

        # Auto-select the solc version this contract requests.
        sol_text = sol_bytes.decode("utf-8", "ignore")
        want = detect_pragma_version(sol_text)
        selected = ensure_solc(want) if want else None

        remaps = build_remaps(os.path.join(work, "node_modules"))
        sl_json = os.path.join(work, "slither.json")
        cmd = [SLITHER, safe, "--json", sl_json]
        if remaps:
            cmd += ["--solc-remaps", " ".join(remaps)]

        sl = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=240)
        sj = ""
        if os.path.exists(sl_json):
            with open(sl_json) as fh:
                sj = fh.read().strip()
        if not sj:
            detail = (sl.stderr or "").strip() or (sl.stdout or "").strip() or "(no output)"
            remap_note = " ".join(remaps) if remaps else \
                f"(none - no node_modules found at {NODE_MODULES})"
            ver_note = (f"Detected pragma version: {want or 'not found'}. "
                        f"Compiler used for this analysis: {selected or solc_version()}.")
            raise RuntimeError(
                "PRELIMINARY RESULT - the contract could not be analyzed because it "
                "did not compile. This is not a final assessment. Please resolve the "
                "issue below and re-submit the corrected file for a full report.\n\n"
                f"{ver_note}\n"
                f"Import remappings tried: {remap_note}\n"
                "If the contract imports libraries that are not in node_modules, "
                "upload a flattened .sol instead.\n\n"
                f"Compiler / analyzer output:\n{detail[-1800:]}")

        spec = os.path.join(work, "spec.json")
        conv = subprocess.run(
            [PYBIN, os.path.join(TOOLS, "slither_to_spec.py"), "-",
             "--project", project, "--prefix", prefix, "--file", safe,
             "--ecosystem", ecosystem, "-o", spec],
            input=sj, capture_output=True, text=True, timeout=60)
        if conv.returncode != 0 or not os.path.exists(spec):
            raise RuntimeError("The report could not be built from the analyzer output.\n\n"
                               + (conv.stderr or conv.stdout or "")[-1500:])

        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        stage = "final" if is_final else "preliminary"
        base = re.sub(r"[^a-z0-9]+", "-", (project or "report").lower()).strip("-") or "report"
        pdf = os.path.join(REPORTS, f"{base}-{stage}-audit-{ts}.pdf")
        rep = subprocess.run([PYBIN, os.path.join(TOOLS, "truel1-report.py"), spec, "-o", pdf],
                             capture_output=True, text=True, timeout=120)
        if rep.returncode != 0 or not os.path.exists(pdf):
            raise RuntimeError("Report rendering failed.\n\n"
                               + (rep.stderr or rep.stdout or "")[-1500:])

        nf = len(json.load(open(spec)).get("findings", []))
        try:
            rebuild_reports_index()
        except Exception:
            pass
        return os.path.basename(pdf), nf, stage
    finally:
        shutil.rmtree(work, ignore_errors=True)


def rebuild_reports_index():
    """Write a professional index.html listing reports: Contract/Date/Time/Type/Stage."""
    rows = []
    for fn in os.listdir(REPORTS):
        if fn == "index.html" or fn.startswith("."):
            continue
        if not fn.lower().endswith((".pdf", ".html")):
            continue
        path = os.path.join(REPORTS, fn)
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(path))
        name, dt = fn, mtime
        stage = "final" if "-final-" in fn.lower() else ("preliminary" if "-preliminary-" in fn.lower() else "")
        m = re.search(r"(.+?)-(?:final|preliminary)?-?(?:audit-)?(\d{8})-(\d{6})\.(pdf|html)$", fn, re.I)
        if m:
            name = m.group(1).strip("-") or fn
            try:
                dt = datetime.datetime.strptime(m.group(2) + m.group(3), "%Y%m%d%H%M%S")
            except Exception:
                dt = mtime
        rows.append((dt, name, fn, fn.lower().rsplit(".", 1)[-1], stage))
    rows.sort(key=lambda r: r[0], reverse=True)

    trs = []
    for dt, name, fn, ext, stage in rows:
        date_s = dt.strftime("%B %d, %Y").replace(" 0", " ")
        time_s = dt.strftime("%I:%M %p").lstrip("0")
        badge = "PDF" if ext == "pdf" else "HTML"
        if stage == "final":
            stg = '<span class="stg stg-final">Final</span>'
        elif stage == "preliminary":
            stg = '<span class="stg stg-prelim">Preliminary</span>'
        else:
            stg = '<span class="stg">&mdash;</span>'
        trs.append(
            f'<tr><td class="nm">{html.escape(name)}</td>'
            f'<td>{date_s}</td><td>{time_s}</td>'
            f'<td>{stg}</td>'
            f'<td><span class="ext ext-{ext}">{badge}</span></td>'
            f'<td><a href="{html.escape(fn)}">View &rarr;</a></td></tr>')
    if not trs:
        trs.append('<tr><td colspan="6" class="empty">No reports yet.</td></tr>')

    gen = datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p").replace(" 0", " ")
    doc = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TrueL1 - Audit Reports</title><style>
:root{--navy:#1f3a5f;--red:#d21c46;--ink:#222;--muted:#667;--line:#e6ebf1;}
*{box-sizing:border-box;}
body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;color:var(--ink);background:#f6f8fb;}
header{background:var(--navy);color:#fff;padding:28px 32px;}
header h1{margin:0;font-size:24px;letter-spacing:.5px;}
header .sub{opacity:.85;font-size:13px;margin-top:5px;}
.wrap{max-width:1000px;margin:26px auto;padding:0 20px;}
.card{background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden;box-shadow:0 1px 3px rgba(20,40,80,.05);}
table{width:100%;border-collapse:collapse;font-size:14px;}
th{text-align:left;background:#f0f4f9;color:var(--muted);font-weight:600;padding:12px 16px;border-bottom:1px solid var(--line);font-size:12px;text-transform:uppercase;letter-spacing:.4px;}
td{padding:13px 16px;border-bottom:1px solid var(--line);}
tr:last-child td{border-bottom:none;}
tr:hover td{background:#fafcff;}
.nm{font-weight:600;color:var(--navy);}
.ext{font-size:11px;font-weight:700;padding:2px 8px;border-radius:20px;}
.ext-pdf{background:#fde8ec;color:var(--red);}.ext-html{background:#e7f0ff;color:#1b5cbf;}
.stg{font-size:11px;font-weight:700;padding:2px 9px;border-radius:20px;background:#eef1f5;color:#667;}
.stg-final{background:#e5f6ec;color:#1b7a3d;}.stg-prelim{background:#fff2df;color:#9a6212;}
a{color:var(--red);text-decoration:none;font-weight:600;}a:hover{text-decoration:underline;}
.empty{text-align:center;color:var(--muted);padding:30px;}
footer{max-width:1000px;margin:14px auto 40px;padding:0 20px;color:var(--muted);font-size:12px;line-height:1.6;}
</style></head><body>
<header><h1>TrueL1 &mdash; Smart Contract Audit Reports</h1>
<div class="sub">FME Layer 1 &middot; AI-assisted review aid &mdash; not a certified audit</div></header>
<div class="wrap"><div class="card"><table>
<thead><tr><th>Contract</th><th>Date</th><th>Time</th><th>Stage</th><th>Format</th><th></th></tr></thead>
<tbody>
""" + "".join(trs) + """
</tbody></table></div></div>
<footer>Reports are generated by TrueL1 automated tooling (Slither static analysis with
AI-assisted review). Preliminary reports indicate issues to resolve; final reports are
issued after remediation. None of these constitute a professional or certified audit.
Index generated """ + gen + """.</footer>
</body></html>"""
    with open(os.path.join(REPORTS, "index.html"), "w") as f:
        f.write(doc)


def result_ok(pdf_name, nf, project, stage):
    url = f"{PUBLIC_BASE}/{pdf_name}"
    if stage == "final":
        badge = '<span class="badge badge-final">FINAL ASSESSMENT</span>'
        head = "Final report generated"
        cls = "ok"
    else:
        badge = '<span class="badge badge-prelim">PRELIMINARY</span>'
        head = "Preliminary report generated"
        cls = "prelim"
    return f"""
<div class="card {cls}">
  <div style="display:flex;align-items:center;gap:12px">
    <div style="font-size:18px;font-weight:600">{head}</div> {badge}
  </div>
  <div class="muted" style="margin-top:8px">Project <b>{html.escape(project)}</b> -
    <b>{nf}</b> finding(s) from Slither.</div>
  <p style="margin-top:14px"><a href="{html.escape(url)}">Open the PDF report &rarr;</a></p>
  <div class="muted"><code>{html.escape(pdf_name)}</code></div>
  <p class="muted" style="margin-top:10px">{"This is the final assessment." if stage=="final" else "This is a preliminary review. After the contract is repaired, re-submit and tick <b>Mark as Final Assessment</b> for the final report."}</p>
  <p style="margin-top:16px"><a href="/">&larr; Analyze another contract</a>
     &nbsp;|&nbsp; <a href="{html.escape(PUBLIC_BASE)}/index.html">All reports</a></p>
</div>"""


def result_err(msg):
    prelim = msg.strip().startswith("PRELIMINARY")
    cls = "prelim" if prelim else "err"
    head = "Preliminary result - action needed" if prelim else "Could not complete the analysis"
    return f"""
<div class="card {cls}">
  <div style="font-size:18px;font-weight:600">{head}</div>
  <pre>{html.escape(msg)}</pre>
  <p><a href="/">&larr; {'Fix and re-submit' if prelim else 'Try again'}</a></p>
</div>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/health"):
            self._send(200, "ok", "text/plain; charset=utf-8")
            return
        self._send(200, render_page(FORM))

    def do_POST(self):
        if not (self.path.rstrip("/").endswith("/audit") or self.path.rstrip("/") == "" or self.path.startswith("/audit")):
            self._send(404, render_page(result_err("Not found.")))
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        if length <= 0:
            self._send(400, render_page(result_err("Empty request.")))
            return
        if length > MAX_UPLOAD:
            self._send(413, render_page(result_err("File too large (max 3 MB).")))
            return
        body = self.rfile.read(length)
        fields = parse_multipart(self.headers.get("Content-Type", ""), body)
        up = fields.get("solfile")
        if not isinstance(up, dict) or not up.get("data"):
            self._send(400, render_page(result_err("No .sol file was uploaded.")))
            return
        project = (fields.get("project") or "").strip() \
            or (up.get("filename") or "Contract").rsplit(".", 1)[0] or "Contract"
        prefix = re.sub(r"[^A-Za-z0-9]", "", (fields.get("prefix") or "").strip()) or "F"
        ecosystem = (fields.get("ecosystem") or "").strip()
        is_final = (fields.get("final") == "1")
        try:
            pdf_name, nf, stage = run_audit(up["data"], up.get("filename", ""),
                                            project, prefix, ecosystem, is_final)
        except subprocess.TimeoutExpired:
            self._send(200, render_page(result_err(
                "Analysis timed out. The contract may be very large or slow to "
                "compile.")))
            return
        except Exception as e:
            self._send(200, render_page(result_err(str(e))))
            return
        self._send(200, render_page(result_ok(pdf_name, nf, project, stage)))

    def log_message(self, *a):
        pass  # quiet


def main():
    os.makedirs(REPORTS, exist_ok=True)
    try:
        rebuild_reports_index()
    except Exception:
        pass
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"TrueL1 Audit Web on 0.0.0.0:{PORT} (reports served at {PUBLIC_BASE})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
