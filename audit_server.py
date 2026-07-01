#!/usr/bin/env python3
"""TrueL1 AI Audit Server - Upload Solidity contracts, get professional audit reports."""

import os
import subprocess
import json
import re
import time
import uuid
import shutil
import threading
import http.server
import socketserver
from urllib.parse import parse_qs, urlparse
from datetime import datetime
import cgi
import io

PORT = 3002
BASE_DIR = "/opt/ai-temp/audit-app"
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
REPORTS_DIR = "/opt/ai-temp/reports"
WORKSPACE_DIR = os.path.join(BASE_DIR, "workspace")
OZ_MODULES = "/opt/ai-temp/AYET-workspace/node_modules"
STATIC_DIR = os.path.join(BASE_DIR, "static")

for d in [UPLOAD_DIR, REPORTS_DIR, WORKSPACE_DIR, STATIC_DIR]:
    os.makedirs(d, exist_ok=True)

# In-memory job tracking
JOBS = {}
JOBS_LOCK = threading.Lock()


def sanitize_filename(name):
    """Prevent path traversal."""
    name = os.path.basename(name)
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)[:100]


def run_slither(contract_path, work_dir):
    """Run Slither and return raw output."""
    try:
        # Copy OpenZeppelin modules to workspace if available
        oz_target = os.path.join(work_dir, "node_modules")
        if os.path.exists(OZ_MODULES) and not os.path.exists(oz_target):
            try:
                os.symlink(OZ_MODULES, oz_target)
            except Exception:
                pass

        remaps = []
        if os.path.exists(os.path.join(work_dir, "node_modules", "@openzeppelin")):
            remaps = ["--solc-remaps", f"@openzeppelin/={work_dir}/node_modules/@openzeppelin/"]

        result = subprocess.run(
            ["slither", os.path.basename(contract_path)] + remaps,
            capture_output=True, text=True, timeout=180, cwd=work_dir
        )
        return (result.stdout or "") + "\n" + (result.stderr or "")
    except subprocess.TimeoutExpired:
        return "ERROR: Slither analysis timed out after 3 minutes"
    except Exception as e:
        return f"ERROR: Slither failed - {str(e)}"


def parse_slither_findings(slither_output):
    """Extract structured findings from Slither output."""
    findings = {"high": [], "medium": [], "low": [], "informational": [], "optimization": []}

    # Slither uses "INFO:Detectors:" then lists findings
    # Each finding block ends before "Reference:" or before next detector
    sections = re.split(r"\n(?=INFO:Detectors:|\S)", slither_output)

    # Look for severity indicators in the text
    lines = slither_output.split("\n")
    current_finding = []

    severity_patterns = {
        "high": [r"[Hh]igh\s+(?:[Ss]everity|[Ii]mpact)", r"HIGH:", r"reentrancy-eth", r"suicidal", r"arbitrary-send"],
        "medium": [r"[Mm]edium\s+(?:[Ss]everity|[Ii]mpact)", r"MEDIUM:", r"reentrancy-no-eth", r"unchecked-transfer"],
        "low": [r"[Ll]ow\s+(?:[Ss]everity|[Ii]mpact)", r"LOW:", r"missing-zero-check", r"timestamp", r"assembly"],
        "informational": [r"[Ii]nformational", r"INFO:", r"naming-convention", r"solc-version"],
        "optimization": [r"[Oo]ptimization", r"constable-states", r"immutable-states"],
    }

    # Extract by parsing the summary line and detector blocks
    for i, line in enumerate(lines):
        # Detectors emit findings like "Function X.y() ... (severity)"
        # We collect based on pattern matches
        for sev, patterns in severity_patterns.items():
            for pat in patterns:
                if re.search(pat, line):
                    findings[sev].append(line.strip())
                    break

    return findings


def call_ai(contract_text, slither_output, contract_name):
    """Call Ollama API for AI-powered analysis."""
    prompt = f"""You are TrueL1 AI Builder, a professional Solidity security auditor.
Analyze the contract below using the Slither static analysis results as reference.

Produce a professional audit report with these sections:

# EXECUTIVE SUMMARY
Brief 2-3 sentence overview of the contract's purpose and overall security posture.

# CONTRACT OVERVIEW
- Contract Name
- Type (ERC-20, ERC-721, upgradeable, etc.)
- Solidity Version
- Key Features
- Dependencies

# VULNERABILITY SUMMARY
Count findings by severity level: Critical, High, Medium, Low, Informational.

# DETAILED FINDINGS

For each REAL vulnerability found (filter out false positives from library code):
## [Severity] - [Finding Name]
**Location:** line numbers or function names
**Description:** What the vulnerability is
**Impact:** What could go wrong
**Recommendation:** How to fix it, with corrected code example

# CENTRALIZATION RISKS
List privileged roles (owner, admin) and their capabilities.
Assess whether governance is decentralized enough for production.

# CODE QUALITY
Style, gas optimization, and best-practice observations.

# CONCLUSION
Overall assessment and recommended actions before mainnet deployment.

IMPORTANT RULES:
- Only report REAL issues that exist in THE PROVIDED CONTRACT below
- Do NOT invent functions that aren't in the code
- Explicitly mark any findings from OpenZeppelin library code as "Library - not user contract"
- Cite line numbers from the actual contract when possible
- Use markdown formatting with # ## for headings and ** ** for emphasis

---
SLITHER STATIC ANALYSIS OUTPUT:
{slither_output[:8000]}

---
CONTRACT SOURCE ({contract_name}):
{contract_text[:20000]}
"""

    try:
        req_body = json.dumps({
            "model": "truel1-ai-builder",
            "prompt": prompt,
            "stream": False,
            "options": {"num_ctx": 32768, "temperature": 0.3}
        }).encode()

        import urllib.request
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=req_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=1200) as resp:
            data = json.loads(resp.read().decode())
            return data.get("response", "AI analysis unavailable")
    except Exception as e:
        return f"ERROR: AI analysis failed - {str(e)}"


def markdown_to_html(md_text):
    """Simple markdown to HTML converter for the report body."""
    html = md_text
    # Headings
    html = re.sub(r"^# (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^### (.+)$", r"<h4>\1</h4>", html, flags=re.MULTILINE)
    # Bold
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    # Code blocks
    html = re.sub(r"```(\w+)?\n(.*?)```", r'<pre class="code"><code>\2</code></pre>', html, flags=re.DOTALL)
    # Inline code
    html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)
    # Lists
    html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
    html = re.sub(r"(<li>.*?</li>\n?)+", lambda m: "<ul>" + m.group(0) + "</ul>", html, flags=re.DOTALL)
    # Paragraphs (blank line separated)
    paragraphs = html.split("\n\n")
    result = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if p.startswith("<h") or p.startswith("<ul") or p.startswith("<pre") or p.startswith("<li"):
            result.append(p)
        else:
            result.append(f"<p>{p}</p>")
    return "\n".join(result)


def generate_html_report(job_id, contract_name, contract_text, slither_output, ai_analysis, findings):
    """Generate professional HTML audit report."""

    high_count = len(findings.get("high", []))
    medium_count = len(findings.get("medium", []))
    low_count = len(findings.get("low", []))
    info_count = len(findings.get("informational", []))
    total_count = high_count + medium_count + low_count + info_count

    # Count contract lines
    contract_lines = len(contract_text.splitlines())
    contract_size = len(contract_text)

    ai_html = markdown_to_html(ai_analysis)
    timestamp = datetime.now().strftime("%B %d, %Y at %H:%M UTC")
    slither_html = slither_output.replace("<", "&lt;").replace(">", "&gt;")
    contract_html = contract_text.replace("<", "&lt;").replace(">", "&gt;")

    html = HTML_TEMPLATE.replace("{{CONTRACT_NAME}}", contract_name)
    html = html.replace("{{JOB_ID}}", job_id)
    html = html.replace("{{TIMESTAMP}}", timestamp)
    html = html.replace("{{HIGH_COUNT}}", str(high_count))
    html = html.replace("{{MEDIUM_COUNT}}", str(medium_count))
    html = html.replace("{{LOW_COUNT}}", str(low_count))
    html = html.replace("{{INFO_COUNT}}", str(info_count))
    html = html.replace("{{TOTAL_COUNT}}", str(total_count))
    html = html.replace("{{CONTRACT_LINES}}", str(contract_lines))
    html = html.replace("{{CONTRACT_SIZE}}", f"{contract_size:,} bytes")
    html = html.replace("{{AI_ANALYSIS_HTML}}", ai_html)
    html = html.replace("{{SLITHER_OUTPUT}}", slither_html)
    html = html.replace("{{CONTRACT_SOURCE}}", contract_html)

    return html


def process_audit_job(job_id, contract_path, original_name):
    """Run the full audit pipeline. Called from background thread."""
    try:
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "running"
            JOBS[job_id]["message"] = "Reading contract..."
            JOBS[job_id]["progress"] = 10

        with open(contract_path, "r", encoding="utf-8", errors="replace") as f:
            contract_text = f.read()

        with JOBS_LOCK:
            JOBS[job_id]["message"] = "Running Slither static analysis (30-90 seconds)..."
            JOBS[job_id]["progress"] = 25

        # Create per-job workspace
        job_workspace = os.path.join(WORKSPACE_DIR, job_id)
        os.makedirs(job_workspace, exist_ok=True)
        target_file = os.path.join(job_workspace, os.path.basename(contract_path))
        shutil.copy(contract_path, target_file)

        slither_output = run_slither(target_file, job_workspace)

        with JOBS_LOCK:
            JOBS[job_id]["message"] = "Slither complete. Running AI analysis (2-8 minutes)..."
            JOBS[job_id]["progress"] = 45

        ai_analysis = call_ai(contract_text, slither_output, original_name)

        with JOBS_LOCK:
            JOBS[job_id]["message"] = "Generating report..."
            JOBS[job_id]["progress"] = 85

        findings = parse_slither_findings(slither_output)

        html_report = generate_html_report(
            job_id, original_name, contract_text,
            slither_output, ai_analysis, findings
        )

        # Save HTML report
        base_name = os.path.splitext(original_name)[0]
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        html_path = os.path.join(REPORTS_DIR, f"{base_name}-{timestamp}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_report)

        # Save markdown for later download
        md_path = os.path.join(REPORTS_DIR, f"{base_name}-{timestamp}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# Audit Report: {original_name}\n\n")
            f.write(f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M UTC')}\n\n")
            f.write("---\n\n## AI Analysis\n\n")
            f.write(ai_analysis)
            f.write("\n\n---\n\n## Slither Raw Output\n\n```\n")
            f.write(slither_output)
            f.write("\n```\n")

        # Try to generate PDF (weasyprint if available)
        pdf_path = None
        try:
            from weasyprint import HTML as WeasyHTML
            pdf_path = os.path.join(REPORTS_DIR, f"{base_name}-{timestamp}.pdf")
            WeasyHTML(string=html_report).write_pdf(pdf_path)
        except Exception as e:
            pdf_path = None

        with JOBS_LOCK:
            JOBS[job_id]["status"] = "complete"
            JOBS[job_id]["progress"] = 100
            JOBS[job_id]["message"] = "Audit complete"
            JOBS[job_id]["html_report"] = os.path.basename(html_path)
            JOBS[job_id]["md_report"] = os.path.basename(md_path)
            if pdf_path and os.path.exists(pdf_path):
                JOBS[job_id]["pdf_report"] = os.path.basename(pdf_path)
            JOBS[job_id]["completed_at"] = datetime.now().isoformat()

        # Cleanup job workspace after 1 hour
        def cleanup():
            time.sleep(3600)
            shutil.rmtree(job_workspace, ignore_errors=True)
        threading.Thread(target=cleanup, daemon=True).start()

    except Exception as e:
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["message"] = f"Error: {str(e)}"
            JOBS[job_id]["progress"] = 0


class AuditHandler(http.server.BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, content_type):
        try:
            with open(path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(path)}"')
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/audit":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(INDEX_HTML.encode())
        elif path.startswith("/api/status/"):
            job_id = path.split("/")[-1]
            with JOBS_LOCK:
                job = JOBS.get(job_id, {"status": "not_found"})
            self._send_json(job)
        elif path.startswith("/download/"):
            filename = os.path.basename(path.split("/")[-1])
            report_path = os.path.join(REPORTS_DIR, filename)
            if not os.path.abspath(report_path).startswith(os.path.abspath(REPORTS_DIR)):
                self.send_response(403); self.end_headers(); return
            if filename.endswith(".html"):
                self._send_file(report_path, "text/html")
            elif filename.endswith(".pdf"):
                self._send_file(report_path, "application/pdf")
            elif filename.endswith(".md"):
                self._send_file(report_path, "text/markdown")
            else:
                self.send_response(400); self.end_headers()
        elif path.startswith("/view/"):
            filename = os.path.basename(path.split("/")[-1])
            report_path = os.path.join(REPORTS_DIR, filename)
            if not os.path.abspath(report_path).startswith(os.path.abspath(REPORTS_DIR)):
                self.send_response(403); self.end_headers(); return
            try:
                with open(report_path, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(data)
            except FileNotFoundError:
                self.send_response(404); self.end_headers()
        elif path == "/api/reports":
            reports = []
            for f in sorted(os.listdir(REPORTS_DIR), reverse=True):
                if f.endswith(".html"):
                    reports.append({
                        "name": f,
                        "size": os.path.getsize(os.path.join(REPORTS_DIR, f)),
                        "date": datetime.fromtimestamp(os.path.getmtime(os.path.join(REPORTS_DIR, f))).isoformat(),
                    })
            self._send_json({"reports": reports[:20]})
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path == "/api/upload":
            try:
                ctype = self.headers.get("Content-Type", "")
                if "multipart/form-data" not in ctype:
                    self._send_json({"error": "Expected multipart/form-data"}, 400)
                    return

                fs = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": ctype},
                )

                if "file" not in fs:
                    self._send_json({"error": "No file provided"}, 400)
                    return

                file_item = fs["file"]
                original_name = sanitize_filename(file_item.filename or "contract.sol")

                if not original_name.endswith(".sol"):
                    self._send_json({"error": "Only .sol files accepted"}, 400)
                    return

                job_id = uuid.uuid4().hex[:12]
                upload_path = os.path.join(UPLOAD_DIR, f"{job_id}-{original_name}")
                with open(upload_path, "wb") as f:
                    f.write(file_item.file.read())

                file_size = os.path.getsize(upload_path)
                if file_size > 5 * 1024 * 1024:  # 5 MB max
                    os.remove(upload_path)
                    self._send_json({"error": "File too large (max 5 MB)"}, 400)
                    return

                with JOBS_LOCK:
                    JOBS[job_id] = {
                        "status": "queued",
                        "progress": 0,
                        "message": "Queued for analysis",
                        "filename": original_name,
                        "started_at": datetime.now().isoformat(),
                    }

                thread = threading.Thread(
                    target=process_audit_job,
                    args=(job_id, upload_path, original_name),
                    daemon=True,
                )
                thread.start()

                self._send_json({"job_id": job_id, "status": "queued"})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
        else:
            self.send_response(404); self.end_headers()

    def log_message(self, format, *args):
        pass  # silence access log


# ============ HTML TEMPLATES ============

INDEX_HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>TrueL1 AI Auditor</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;background:#0B1220;color:#E5E7EB;min-height:100vh;padding:24px}
.wrap{max-width:900px;margin:0 auto}
.header{text-align:center;margin-bottom:32px;padding:24px 0}
.logo{font-size:28px;font-weight:700;background:linear-gradient(90deg,#A8FF78,#78FFD6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:8px}
.tagline{color:#94A3B8;font-size:14px}
.dropzone{border:2px dashed #374151;border-radius:16px;padding:60px 24px;text-align:center;background:#1F2937;transition:all .3s;cursor:pointer}
.dropzone.dragover{border-color:#A8FF78;background:#1a2e1f}
.dropzone-icon{font-size:64px;margin-bottom:16px;opacity:.6}
.dropzone-text{font-size:18px;font-weight:600;margin-bottom:8px}
.dropzone-sub{color:#9CA3AF;font-size:13px}
input[type=file]{display:none}
.btn{background:linear-gradient(90deg,#059669,#10B981);color:#fff;border:none;padding:14px 32px;font-size:15px;font-weight:600;border-radius:8px;cursor:pointer;margin-top:16px;transition:transform .2s}
.btn:hover{transform:translateY(-1px)}
.btn:disabled{opacity:.5;cursor:not-allowed;transform:none}
.file-info{background:#1F2937;border-radius:12px;padding:16px 20px;margin-top:16px;display:none}
.file-info.show{display:block}
.file-info .name{font-weight:600;color:#A8FF78}
.file-info .size{color:#9CA3AF;font-size:12px;margin-top:4px}
.progress-panel{background:#1F2937;border-radius:16px;padding:24px;margin-top:24px;display:none}
.progress-panel.show{display:block}
.progress-title{font-weight:600;margin-bottom:16px;font-size:16px}
.progress-bar-wrap{height:12px;background:#374151;border-radius:6px;overflow:hidden;margin-bottom:12px}
.progress-bar{height:100%;background:linear-gradient(90deg,#059669,#A8FF78);border-radius:6px;transition:width .5s;width:0%}
.progress-msg{color:#9CA3AF;font-size:13px}
.result-panel{background:#1F2937;border-radius:16px;padding:24px;margin-top:24px;display:none}
.result-panel.show{display:block}
.result-title{color:#A8FF78;font-weight:600;font-size:18px;margin-bottom:16px}
.download-links{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-top:16px}
.dl-btn{background:#374151;color:#E5E7EB;padding:14px;border-radius:10px;text-decoration:none;text-align:center;font-weight:600;transition:background .2s;display:block}
.dl-btn:hover{background:#4B5563}
.dl-btn .icon{font-size:24px;display:block;margin-bottom:4px}
.dl-btn .label{font-size:13px}
.view-btn{background:linear-gradient(90deg,#3B82F6,#8B5CF6)}
.view-btn:hover{background:linear-gradient(90deg,#2563EB,#7C3AED)}
.reports-panel{background:#1F2937;border-radius:16px;padding:24px;margin-top:24px}
.reports-title{font-weight:600;margin-bottom:16px;color:#9CA3AF;font-size:12px;text-transform:uppercase;letter-spacing:.08em}
.report-item{padding:12px;border-bottom:1px solid #374151;display:flex;justify-content:space-between;align-items:center}
.report-item:last-child{border-bottom:none}
.report-item a{color:#A8FF78;text-decoration:none;font-weight:600}
.report-item a:hover{text-decoration:underline}
.report-item .date{color:#6B7280;font-size:12px}
.error{background:#7F1D1D;color:#FCA5A5;padding:16px;border-radius:10px;margin-top:16px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:24px}
.stat-card{background:#1F2937;border-radius:10px;padding:16px}
.stat-label{color:#9CA3AF;font-size:11px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px}
.stat-value{font-size:24px;font-weight:700;color:#A8FF78}
.stat-sub{color:#6B7280;font-size:11px;margin-top:2px}
.footer{margin-top:32px;text-align:center;color:#6B7280;font-size:12px}
</style></head><body><div class="wrap">
<div class="header">
<div class="logo">TrueL1 AI Auditor</div>
<div class="tagline">Professional smart contract security analysis powered by DeepSeek-R1 70B</div>
</div>

<div class="stats">
<div class="stat-card"><div class="stat-label">Model</div><div class="stat-value" style="font-size:18px">DeepSeek-R1</div><div class="stat-sub">70B parameters</div></div>
<div class="stat-card"><div class="stat-label">Static Analysis</div><div class="stat-value" style="font-size:18px">Slither</div><div class="stat-sub">Trail of Bits</div></div>
<div class="stat-card"><div class="stat-label">GPU</div><div class="stat-value" style="font-size:18px">RTX 8000</div><div class="stat-sub">48 GB VRAM</div></div>
<div class="stat-card"><div class="stat-label">Privacy</div><div class="stat-value" style="font-size:18px">100%</div><div class="stat-sub">Fully offline</div></div>
</div>

<div class="dropzone" id="dropzone">
<div class="dropzone-icon">📄</div>
<div class="dropzone-text">Drop your .sol file here</div>
<div class="dropzone-sub">or click to browse - max 5 MB</div>
<input type="file" id="fileInput" accept=".sol">
</div>

<div id="fileInfo" class="file-info">
<div class="name" id="fileName">-</div>
<div class="size" id="fileSize">-</div>
<button class="btn" id="auditBtn" onclick="startAudit()">Start Security Audit</button>
</div>

<div id="progressPanel" class="progress-panel">
<div class="progress-title">Analyzing Contract</div>
<div class="progress-bar-wrap"><div class="progress-bar" id="progressBar"></div></div>
<div class="progress-msg" id="progressMsg">Starting...</div>
</div>

<div id="resultPanel" class="result-panel">
<div class="result-title">✓ Audit Complete</div>
<div id="resultText"></div>
<div class="download-links" id="downloadLinks"></div>
</div>

<div id="errorPanel"></div>

<div class="reports-panel">
<div class="reports-title">Recent Reports</div>
<div id="reportsList">Loading...</div>
</div>

<div class="footer">Running on your private server at 192.168.1.15 - No data leaves your network</div>
</div>

<script>
let selectedFile = null;
let currentJobId = null;
let pollInterval = null;

const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');

dropzone.addEventListener('click', () => fileInput.click());
dropzone.addEventListener('dragover', e => {
  e.preventDefault();
  dropzone.classList.add('dragover');
});
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
dropzone.addEventListener('drop', e => {
  e.preventDefault();
  dropzone.classList.remove('dragover');
  if (e.dataTransfer.files.length > 0) handleFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', e => {
  if (e.target.files.length > 0) handleFile(e.target.files[0]);
});

function handleFile(file) {
  if (!file.name.endsWith('.sol')) {
    showError('Please select a .sol file');
    return;
  }
  if (file.size > 5 * 1024 * 1024) {
    showError('File too large (max 5 MB)');
    return;
  }
  selectedFile = file;
  document.getElementById('fileName').textContent = file.name;
  document.getElementById('fileSize').textContent = formatBytes(file.size) + ' - ' + file.type;
  document.getElementById('fileInfo').classList.add('show');
  clearError();
}

async function startAudit() {
  if (!selectedFile) return;
  document.getElementById('auditBtn').disabled = true;
  document.getElementById('progressPanel').classList.add('show');
  document.getElementById('resultPanel').classList.remove('show');
  clearError();

  const form = new FormData();
  form.append('file', selectedFile);

  try {
    const res = await fetch('/api/upload', { method: 'POST', body: form });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    currentJobId = data.job_id;
    startPolling();
  } catch (e) {
    showError(e.message);
    document.getElementById('auditBtn').disabled = false;
    document.getElementById('progressPanel').classList.remove('show');
  }
}

function startPolling() {
  if (pollInterval) clearInterval(pollInterval);
  pollInterval = setInterval(async () => {
    try {
      const res = await fetch('/api/status/' + currentJobId);
      const job = await res.json();
      document.getElementById('progressBar').style.width = (job.progress || 0) + '%';
      document.getElementById('progressMsg').textContent = job.message || '';
      if (job.status === 'complete') {
        clearInterval(pollInterval);
        showResults(job);
      } else if (job.status === 'error') {
        clearInterval(pollInterval);
        showError(job.message);
        document.getElementById('auditBtn').disabled = false;
        document.getElementById('progressPanel').classList.remove('show');
      }
    } catch (e) {}
  }, 2000);
}

function showResults(job) {
  document.getElementById('progressPanel').classList.remove('show');
  const links = document.getElementById('downloadLinks');
  links.innerHTML = '';
  if (job.html_report) {
    links.innerHTML += '<a class="dl-btn view-btn" href="/view/' + job.html_report + '" target="_blank"><span class="icon">👁</span><span class="label">View Report</span></a>';
    links.innerHTML += '<a class="dl-btn" href="/download/' + job.html_report + '"><span class="icon">📄</span><span class="label">HTML</span></a>';
  }
  if (job.pdf_report) {
    links.innerHTML += '<a class="dl-btn" href="/download/' + job.pdf_report + '"><span class="icon">📕</span><span class="label">PDF</span></a>';
  }
  if (job.md_report) {
    links.innerHTML += '<a class="dl-btn" href="/download/' + job.md_report + '"><span class="icon">📝</span><span class="label">Markdown</span></a>';
  }
  document.getElementById('resultPanel').classList.add('show');
  document.getElementById('auditBtn').disabled = false;
  loadReports();
}

async function loadReports() {
  try {
    const res = await fetch('/api/reports');
    const data = await res.json();
    const list = document.getElementById('reportsList');
    if (data.reports.length === 0) {
      list.innerHTML = '<div style="color:#6B7280;text-align:center;padding:12px">No reports yet</div>';
      return;
    }
    list.innerHTML = data.reports.map(r =>
      '<div class="report-item">' +
        '<a href="/view/' + r.name + '" target="_blank">' + r.name + '</a>' +
        '<div class="date">' + new Date(r.date).toLocaleString() + '</div>' +
      '</div>'
    ).join('');
  } catch (e) {}
}

function showError(msg) {
  document.getElementById('errorPanel').innerHTML = '<div class="error">Error: ' + msg + '</div>';
}
function clearError() {
  document.getElementById('errorPanel').innerHTML = '';
}
function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(2) + ' MB';
}

loadReports();
setInterval(loadReports, 15000);
</script></body></html>"""


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Security Audit - {{CONTRACT_NAME}}</title>
<style>
@page{size:A4;margin:2cm 1.5cm}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,"Segoe UI",Helvetica,Arial,sans-serif;color:#1a1a1a;line-height:1.6;background:#fff;padding:0}
.container{max-width:900px;margin:0 auto;padding:40px}
.cover{background:linear-gradient(135deg,#0B1220 0%,#1a1f3a 100%);color:#fff;padding:60px 40px;margin:-40px -40px 40px -40px;border-radius:0;page-break-after:always}
.logo{font-size:14px;font-weight:700;letter-spacing:.15em;color:#A8FF78;margin-bottom:32px;text-transform:uppercase}
.cover h1{font-size:44px;font-weight:800;margin-bottom:16px;line-height:1.15}
.cover .subtitle{font-size:20px;color:#93C5FD;margin-bottom:48px;font-weight:400}
.cover-meta{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:32px;padding-top:32px;border-top:1px solid rgba(255,255,255,0.15)}
.cover-meta-item{padding:12px 0}
.cover-meta-label{font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px}
.cover-meta-value{font-size:15px;color:#E5E7EB;font-weight:500}

h2{color:#0B1220;font-size:28px;font-weight:700;margin:40px 0 20px 0;padding-bottom:12px;border-bottom:3px solid #A8FF78;page-break-after:avoid}
h3{color:#1a1f3a;font-size:20px;font-weight:600;margin:32px 0 14px 0;page-break-after:avoid}
h4{color:#374151;font-size:16px;font-weight:600;margin:20px 0 10px 0;page-break-after:avoid}
p{margin:12px 0;color:#374151;font-size:14px;line-height:1.75}
ul{margin:12px 0 12px 24px}
li{margin:6px 0;color:#374151;font-size:14px;line-height:1.65}
strong{color:#0B1220;font-weight:600}
code{background:#F3F4F6;padding:2px 6px;border-radius:4px;font-family:"SF Mono",Monaco,Consolas,monospace;font-size:13px;color:#DC2626}
pre.code{background:#0B1220;color:#A8FF78;padding:16px;border-radius:8px;overflow-x:auto;margin:16px 0;font-family:"SF Mono",Monaco,Consolas,monospace;font-size:12px;line-height:1.5;page-break-inside:avoid}
pre.code code{background:transparent;color:inherit;padding:0}

.summary-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:24px 0}
.summary-card{padding:20px;border-radius:12px;text-align:center;border:1px solid #E5E7EB}
.summary-card.critical{background:#FEE2E2;border-color:#DC2626}
.summary-card.high{background:#FED7AA;border-color:#EA580C}
.summary-card.medium{background:#FEF3C7;border-color:#D97706}
.summary-card.low{background:#DBEAFE;border-color:#2563EB}
.summary-card.info{background:#F3F4F6;border-color:#6B7280}
.summary-count{font-size:36px;font-weight:800;line-height:1;margin-bottom:6px}
.summary-card.critical .summary-count{color:#991B1B}
.summary-card.high .summary-count{color:#9A3412}
.summary-card.medium .summary-count{color:#92400E}
.summary-card.low .summary-count{color:#1E40AF}
.summary-card.info .summary-count{color:#374151}
.summary-label{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#4B5563}

.meta-table{width:100%;border-collapse:collapse;margin:20px 0;border:1px solid #E5E7EB;border-radius:8px;overflow:hidden}
.meta-table th{background:#F9FAFB;padding:12px 16px;text-align:left;font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:#4B5563;font-weight:600;width:35%}
.meta-table td{padding:12px 16px;border-top:1px solid #E5E7EB;font-size:14px;color:#0B1220}

.stamp{background:linear-gradient(135deg,#A8FF78,#059669);color:#0B1220;padding:32px;border-radius:16px;text-align:center;margin:32px 0;page-break-inside:avoid}
.stamp-title{font-size:12px;font-weight:700;letter-spacing:.15em;text-transform:uppercase;margin-bottom:8px}
.stamp-subtitle{font-size:20px;font-weight:800;margin-bottom:16px}
.stamp-details{font-size:13px;font-weight:500;opacity:.9}

.footer{margin-top:60px;padding-top:20px;border-top:1px solid #E5E7EB;text-align:center;color:#6B7280;font-size:11px}
.footer-brand{color:#0B1220;font-weight:600;margin-bottom:8px}

.notice{background:#FFFBEB;border-left:4px solid #F59E0B;padding:16px 20px;margin:20px 0;border-radius:0 8px 8px 0}
.notice-title{font-weight:700;color:#92400E;font-size:13px;margin-bottom:4px}
.notice-text{color:#78350F;font-size:13px;line-height:1.6}

.raw-slither{background:#0B1220;color:#A8FF78;padding:20px;border-radius:8px;font-family:monospace;font-size:11px;line-height:1.5;white-space:pre-wrap;max-height:600px;overflow-y:auto;page-break-inside:avoid}
.raw-contract{background:#F9FAFB;color:#1F2937;padding:20px;border-radius:8px;font-family:monospace;font-size:11px;line-height:1.5;white-space:pre-wrap;border:1px solid #E5E7EB;max-height:600px;overflow-y:auto;page-break-inside:avoid}

.page-break{page-break-before:always}
</style></head><body>
<div class="container">

<div class="cover">
<div class="logo">TrueL1 AI Auditor</div>
<h1>Security Audit Report</h1>
<div class="subtitle">{{CONTRACT_NAME}}</div>

<div class="cover-meta">
<div class="cover-meta-item">
<div class="cover-meta-label">Report ID</div>
<div class="cover-meta-value">{{JOB_ID}}</div>
</div>
<div class="cover-meta-item">
<div class="cover-meta-label">Generated</div>
<div class="cover-meta-value">{{TIMESTAMP}}</div>
</div>
<div class="cover-meta-item">
<div class="cover-meta-label">Analysis Engine</div>
<div class="cover-meta-value">Slither + DeepSeek-R1 70B</div>
</div>
<div class="cover-meta-item">
<div class="cover-meta-label">Auditor</div>
<div class="cover-meta-value">TrueL1 AI Builder</div>
</div>
<div class="cover-meta-item">
<div class="cover-meta-label">Contract Size</div>
<div class="cover-meta-value">{{CONTRACT_LINES}} lines / {{CONTRACT_SIZE}}</div>
</div>
<div class="cover-meta-item">
<div class="cover-meta-label">Total Findings</div>
<div class="cover-meta-value">{{TOTAL_COUNT}}</div>
</div>
</div>
</div>

<h2>Vulnerability Summary</h2>
<div class="summary-grid">
<div class="summary-card critical"><div class="summary-count">0</div><div class="summary-label">Critical</div></div>
<div class="summary-card high"><div class="summary-count">{{HIGH_COUNT}}</div><div class="summary-label">High</div></div>
<div class="summary-card medium"><div class="summary-count">{{MEDIUM_COUNT}}</div><div class="summary-label">Medium</div></div>
<div class="summary-card low"><div class="summary-count">{{LOW_COUNT}}</div><div class="summary-label">Low</div></div>
<div class="summary-card info"><div class="summary-count">{{INFO_COUNT}}</div><div class="summary-label">Info</div></div>
</div>

<div class="notice">
<div class="notice-title">Important Note</div>
<div class="notice-text">This report is generated by an AI-powered auditor for internal review. It complements — but does not replace — manual auditing by professional firms like CertiK or Coinsult for production deployments. Cross-reference findings with static analysis results below.</div>
</div>

{{AI_ANALYSIS_HTML}}

<div class="page-break"></div>

<h2>Static Analysis (Slither)</h2>
<p>Raw output from Slither static analyzer by Trail of Bits — the industry standard for Solidity static analysis.</p>
<div class="raw-slither">{{SLITHER_OUTPUT}}</div>

<div class="page-break"></div>

<h2>Contract Source</h2>
<p>Full source code as audited:</p>
<div class="raw-contract">{{CONTRACT_SOURCE}}</div>

<div class="stamp">
<div class="stamp-title">Audited By</div>
<div class="stamp-subtitle">TrueL1 AI Auditor</div>
<div class="stamp-details">Private AI-powered security analysis - Powered by DeepSeek-R1 70B and Slither<br>Report generated on {{TIMESTAMP}}</div>
</div>

<div class="footer">
<div class="footer-brand">TrueL1 AI Auditor</div>
Report ID: {{JOB_ID}} - This report is confidential and intended for internal use.<br>
Cross-verify with professional auditor firms (CertiK, Coinsult, Trail of Bits) for production deployments.
</div>

</div>
</body></html>"""


if __name__ == "__main__":
    print(f"TrueL1 AI Auditor running on http://0.0.0.0:{PORT}/audit")
    print(f"Reports directory: {REPORTS_DIR}")
    with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), AuditHandler) as httpd:
        httpd.serve_forever()
