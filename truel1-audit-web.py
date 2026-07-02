#!/usr/bin/env python3
"""
TrueL1 Audit Web
================
Upload a .sol file -> Slither static analysis -> TrueL1 CertiK-class PDF.

Standard-library only (no Flask / no new packages). Runs on its OWN port
(default 3004) so it does NOT interfere with the existing service on 3002.
Findings come from Slither; the model is not used to invent findings.

Env:
  TRUEL1_AUDIT_PORT   listen port (default 3004)
  TRUEL1_PUBLIC_BASE  base URL where /opt/ai-temp/reports is served
                      (default http://l1.aucfans.com:3003)
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
NODE_MODULES = os.environ.get("TRUEL1_NODE_MODULES", "/opt/ai-temp/AYET-workspace/node_modules")
MAX_UPLOAD = 3 * 1024 * 1024  # 3 MB

PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8">
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
button{{margin-top:20px;background:#E11D48;color:#fff;border:none;border-radius:8px;
padding:12px 20px;font-size:15px;font-weight:600;cursor:pointer;width:100%}}
button:hover{{background:#c01840}}
a{{color:#E11D48}}
.ok{{border-color:#30A46C}}.err{{border-color:#E5484D}}
code{{background:#1A1F2B;color:#E6C07B;padding:1px 5px;border-radius:4px;font-size:12px}}
pre{{white-space:pre-wrap;color:#99A1B0;font-size:12px;background:#0B0E14;
border:1px solid #232A38;border-radius:8px;padding:12px;overflow:auto;max-height:280px}}
.note{{color:#6b7688;font-size:11px;margin-top:26px;line-height:1.5}}
</style></head><body><div class="wrap">
<div class="brand">TRUEL1</div>
<h1>Smart Contract Audit</h1>
<div class="muted">Upload a Solidity file. It is analysed with Slither and rendered
into a TrueL1 assessment report. This is an AI-assisted review aid, not a
professional audit or certification.</div>
{body}
<div class="note">Findings come from static analysis (Slither) and may include
false positives/negatives; verify important findings against the source. Reports
are written to the shared reports folder and served from {base}.</div>
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
        r = subprocess.run(["solc", "--version"], capture_output=True,
                           text=True, timeout=15)
        lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
        return lines[-1].strip() if lines else "unknown"
    except Exception:
        return "unknown"


def build_remaps(node_modules):
    """One remapping per top-level package in node_modules, e.g.
    '@openzeppelin/=node_modules/@openzeppelin/' (relative to the run cwd)."""
    remaps = []
    if not node_modules or not os.path.isdir(node_modules):
        return remaps
    for entry in sorted(os.listdir(node_modules)):
        if entry.startswith("."):
            continue
        if os.path.isdir(os.path.join(node_modules, entry)):
            remaps.append(f"{entry}/=node_modules/{entry}/")
    return remaps


def run_audit(sol_bytes, filename, project, prefix, ecosystem):
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

        # Resolve library imports (e.g. OpenZeppelin) via remappings that point
        # at the symlinked node_modules.
        remaps = build_remaps(os.path.join(work, "node_modules"))
        sl_json = os.path.join(work, "slither.json")
        cmd = [SLITHER, safe, "--json", sl_json]
        if remaps:
            cmd += ["--solc-remaps", " ".join(remaps)]

        # 1. Slither -> JSON file. Writing to a file (not stdout) keeps the
        # error log on stderr when compilation fails, so failures are visible.
        # Nonzero exit when findings exist is normal.
        sl = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=240)
        sj = ""
        if os.path.exists(sl_json):
            with open(sl_json) as fh:
                sj = fh.read().strip()
        if not sj:
            detail = (sl.stderr or "").strip() or (sl.stdout or "").strip() or "(no output)"
            remap_note = " ".join(remaps) if remaps else \
                f"(none - no node_modules found at {NODE_MODULES})"
            raise RuntimeError(
                "Slither could not analyse the contract - it most likely failed "
                "to compile (unresolved imports or a solc version mismatch).\n"
                f"solc in use: {solc_version()}\n"
                f"import remappings tried: {remap_note}\n"
                "If the contract imports libraries that aren't in node_modules, "
                "upload a flattened .sol instead.\n\n"
                f"Slither reported:\n{detail[-1800:]}")

        # 2. convert to report spec
        spec = os.path.join(work, "spec.json")
        conv = subprocess.run(
            [PYBIN, os.path.join(TOOLS, "slither_to_spec.py"), "-",
             "--project", project, "--prefix", prefix, "--file", safe,
             "--ecosystem", ecosystem, "-o", spec],
            input=sj, capture_output=True, text=True, timeout=60)
        if conv.returncode != 0 or not os.path.exists(spec):
            raise RuntimeError("Could not build the report from Slither output.\n\n"
                               + (conv.stderr or conv.stdout or "")[-1500:])

        # 3. render PDF
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        base = re.sub(r"[^a-z0-9]+", "-", (project or "report").lower()).strip("-") or "report"
        pdf = os.path.join(REPORTS, f"{base}-audit-{ts}.pdf")
        rep = subprocess.run([PYBIN, os.path.join(TOOLS, "truel1-report.py"), spec, "-o", pdf],
                             capture_output=True, text=True, timeout=120)
        if rep.returncode != 0 or not os.path.exists(pdf):
            raise RuntimeError("Report rendering failed.\n\n"
                               + (rep.stderr or rep.stdout or "")[-1500:])

        nf = len(json.load(open(spec)).get("findings", []))
        return os.path.basename(pdf), nf
    finally:
        shutil.rmtree(work, ignore_errors=True)


def result_ok(pdf_name, nf, project):
    url = f"{PUBLIC_BASE}/{pdf_name}"
    return f"""
<div class="card ok">
  <div style="font-size:18px;font-weight:600">Report generated</div>
  <div class="muted" style="margin-top:8px">Project <b>{html.escape(project)}</b> -
    <b>{nf}</b> finding(s) from Slither.</div>
  <p style="margin-top:14px"><a href="{html.escape(url)}">Open the PDF report &rarr;</a></p>
  <div class="muted"><code>{html.escape(pdf_name)}</code></div>
  <p style="margin-top:16px"><a href="/">&larr; Analyse another contract</a></p>
</div>"""


def result_err(msg):
    return f"""
<div class="card err">
  <div style="font-size:18px;font-weight:600">Could not complete the analysis</div>
  <pre>{html.escape(msg)}</pre>
  <p><a href="/">&larr; Try again</a></p>
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
        try:
            pdf_name, nf = run_audit(up["data"], up.get("filename", ""),
                                     project, prefix, ecosystem)
        except subprocess.TimeoutExpired:
            self._send(200, render_page(result_err(
                "Analysis timed out. The contract may be very large or slow to "
                "compile.")))
            return
        except Exception as e:
            self._send(200, render_page(result_err(str(e))))
            return
        self._send(200, render_page(result_ok(pdf_name, nf, project)))

    def log_message(self, *a):
        pass  # quiet


def main():
    os.makedirs(REPORTS, exist_ok=True)
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"TrueL1 Audit Web on 0.0.0.0:{PORT} (reports served at {PUBLIC_BASE})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
