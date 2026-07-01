#!/usr/bin/env python3
"""
TrueL1 Security Assessment - report generator
=============================================
Renders a professional, multi-page audit report PDF (cover, executive summary
with severity counts, table of contents, codebase, scope, methods, findings
table, per-finding pages, appendix, disclaimer, back cover) from a JSON spec.

It is deliberately TrueL1-branded. It does NOT reproduce any third-party
auditor's name, logo, or report text - a report that looks issued by another
firm would be misleading and is not something this tool will produce. Output is
clearly labelled as a TrueL1 AI-assisted review, not a professional
certification.

Usage:
    truel1-report.py <spec.json> --output <report.pdf>

The JSON drives everything; see ayet-report.json for the schema. Severity and
status counts are computed automatically from the findings list.
"""
import sys
import re
import json
import html
import argparse
import datetime

# ----- palette (literal hex; no CSS variables, so it renders identically in
#       both WeasyPrint and older engines) -----
BG      = "#0B0E14"
PANEL   = "#12161F"
PANEL2  = "#1A1F2B"
TEXT    = "#E6E8EC"
MUTED   = "#99A1B0"
ACCENT  = "#E11D48"   # TrueL1 crimson accent
LINE    = "#232A38"

SEVERITY = {
    "Critical":      ("#E5484D", "Critical risks impact the safe functioning of the platform and must be addressed before launch."),
    "Major":         ("#F76808", "Major risks may include logic errors that, under specific conditions, could cause fund loss or loss of control."),
    "Medium":        ("#FFB224", "Medium risks may not directly threaten user funds but can affect the overall functioning of the platform."),
    "Minor":         ("#5B9DFF", "Minor risks are smaller-scale issues that generally do not compromise the project's integrity."),
    "Informational": ("#99A1B0", "Informational items are recommendations to improve code style or align with best practices."),
    "Centralization":("#A78BFA", "Centralization findings highlight privileged roles and functions, or custody over user assets."),
    "Discussion":    ("#2DD4BF", "Discussion items require further clarification from the project team to determine impact."),
}
SEVERITY_ORDER = list(SEVERITY.keys())

STATUS_ORDER = ["Resolved", "Partially Resolved", "Acknowledged", "Declined", "Pending"]
STATUS_COLOR = {
    "Resolved": "#30A46C", "Partially Resolved": "#FFB224",
    "Acknowledged": "#5B9DFF", "Declined": "#E5484D", "Pending": "#99A1B0",
}


def esc(s):
    return html.escape(str(s if s is not None else ""))


def inline(s):
    s = esc(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s


def render_body(text):
    """Small markdown-lite: '- ' bullets, 'Heading:' subheads, `code`, paras."""
    lines = str(text or "").split("\n")
    out, i = [], 0
    while i < len(lines):
        raw = lines[i]
        if not raw.strip():
            i += 1
            continue
        if raw.lstrip().startswith("- "):
            items = []
            while i < len(lines) and lines[i].lstrip().startswith("- "):
                items.append("<li>" + inline(lines[i].lstrip()[2:]) + "</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        stripped = raw.strip()
        if stripped.endswith(":") and len(stripped) <= 64:
            out.append('<div class="subhead">' + inline(stripped) + "</div>")
        else:
            out.append("<p>" + inline(stripped) + "</p>")
        i += 1
    return "".join(out) or "<p></p>"


def sev_badge(sev):
    color = SEVERITY.get(sev, (MUTED, ""))[0]
    return (f'<span class="badge" style="color:{color};border-color:{color}">'
            f'{esc(sev)}</span>')


def status_badge(st):
    color = STATUS_COLOR.get(st, MUTED)
    return (f'<span class="badge" style="color:{color};border-color:{color}">'
            f'{esc(st)}</span>')


SHIELD = (
    '<svg width="54" height="60" viewBox="0 0 54 60" fill="none" '
    'xmlns="http://www.w3.org/2000/svg">'
    f'<path d="M27 2 L50 12 V30 C50 44 40 54 27 58 C14 54 4 44 4 30 V12 Z" '
    f'stroke="{ACCENT}" stroke-width="2.5" fill="none"/>'
    f'<path d="M18 30 l7 7 l12 -15" stroke="{ACCENT}" stroke-width="3" '
    'fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'
)


def css():
    return """
@page { size: A4; margin: 1.6cm 1.5cm 1.7cm 1.5cm; }
@page { @bottom-center { content: "TrueL1 Security Assessment - Confidential";
        color: #5b6472; font-size: 7pt; }
        @bottom-right { content: counter(page); color: #5b6472; font-size: 7pt; } }
@page cover { margin: 0; }
html, body { background: %BG%; color: %TEXT%;
    font-family: "Helvetica Neue", Helvetica, Arial, "Liberation Sans", sans-serif;
    font-size: 10pt; line-height: 1.5; margin: 0; padding: 0; }
code { font-family: "DejaVu Sans Mono", "Courier New", monospace;
    background: %PANEL2%; color: #E6C07B; padding: 0 3px; border-radius: 3px;
    font-size: 8.6pt; }
.sheet { page-break-before: always; }

/* cover */
.cover { page: cover; background: %BG%; min-height: 26cm; padding: 3.4cm 2.4cm; }
.cover .brand { display: block; margin-bottom: 3.2cm; }
.cover .brand .name { color: %TEXT%; font-size: 15pt; letter-spacing: 3px;
    font-weight: 700; vertical-align: middle; margin-left: 12px; }
.cover .brand .tag { color: %MUTED%; font-size: 8.5pt; letter-spacing: 2px;
    display: block; margin-top: 6px; margin-left: 2px; }
.cover h1 { color: %TEXT%; font-size: 40pt; font-weight: 300; margin: 0; }
.cover .sub { color: %ACCENT%; font-size: 30pt; font-weight: 600;
    margin: 2px 0 0 0; }
.cover .rule { height: 2px; background: %ACCENT%; width: 8.5cm; margin: 22px 0; opacity: .5; }
.cover .meta { color: %MUTED%; font-size: 11pt; }

/* section headings */
.sec-h { border-left: 3px solid %ACCENT%; padding-left: 12px; margin: 0 0 18px 0; }
.sec-h .k { color: %MUTED%; font-size: 8pt; letter-spacing: 2px; text-transform: uppercase; }
.sec-h .t { color: %TEXT%; font-size: 20pt; font-weight: 600; margin-top: 2px; }
h3 { color: %TEXT%; font-size: 12pt; margin: 18px 0 8px; }
.subhead { color: %ACCENT%; font-weight: 600; margin: 12px 0 4px; font-size: 9.5pt; }
p { margin: 6px 0; }
ul { margin: 6px 0 6px 0; padding-left: 18px; }
li { margin: 3px 0; }

/* panels + layout */
.panel { background: %PANEL%; border: 1px solid %LINE%; border-radius: 8px;
    padding: 14px 16px; }
.col-wrap { width: 100%; }
.col-main { display: inline-block; width: 62%; vertical-align: top;
    padding-right: 3%; box-sizing: border-box; }
.col-side { display: inline-block; width: 35%; vertical-align: top; }

/* severity summary rows */
.sevrow { border-bottom: 1px solid %LINE%; padding: 9px 0; }
.sevrow .n { display: inline-block; width: 34px; font-size: 17pt; font-weight: 700;
    vertical-align: top; }
.sevrow .b { display: inline-block; width: calc(100% - 42px); vertical-align: top; }
.sevrow .b .nm { color: %TEXT%; font-weight: 600; font-size: 9.5pt; }
.sevrow .b .ds { color: %MUTED%; font-size: 8pt; line-height: 1.4; }

/* sidebar facts */
.fact { border-bottom: 1px solid %LINE%; padding: 8px 0; }
.fact .k { color: %MUTED%; font-size: 7.5pt; letter-spacing: 1.5px; text-transform: uppercase; }
.fact .v { color: %TEXT%; font-size: 9.5pt; margin-top: 2px; }
.bignum { text-align: center; padding: 6px 0; }
.bignum .x { font-size: 26pt; font-weight: 700; color: %TEXT%; }
.bignum .y { color: %MUTED%; font-size: 8pt; letter-spacing: 1px; text-transform: uppercase; }

/* badges + tables */
.badge { display: inline-block; border: 1px solid %MUTED%; border-radius: 20px;
    padding: 1px 9px; font-size: 7.6pt; font-weight: 600; }
table { width: 100%; border-collapse: collapse; margin: 8px 0; }
th { text-align: left; color: %MUTED%; font-size: 7.6pt; letter-spacing: 1px;
    text-transform: uppercase; border-bottom: 1px solid %LINE%; padding: 8px 6px; }
td { color: %TEXT%; font-size: 9pt; border-bottom: 1px solid %LINE%;
    padding: 8px 6px; vertical-align: top; }
td.mono, .mono { font-family: "DejaVu Sans Mono", "Courier New", monospace;
    font-size: 8.4pt; color: #cfd6e4; word-break: break-all; }

/* chips row */
.chips { margin: 6px 0 14px; }
.chip { display: inline-block; background: %PANEL%; border: 1px solid %LINE%;
    border-radius: 8px; padding: 8px 12px; margin: 0 8px 8px 0; }
.chip .c { font-size: 15pt; font-weight: 700; }
.chip .l { color: %MUTED%; font-size: 7.6pt; text-transform: uppercase;
    letter-spacing: 1px; margin-left: 6px; }

/* finding */
.finding .fid { color: %ACCENT%; font-size: 9pt; font-weight: 700; letter-spacing: 1px; }
.finding .ftitle { color: %TEXT%; font-size: 18pt; font-weight: 600; margin: 2px 0 12px; }
.metatab td { border: none; padding: 4px 10px 4px 0; }
.metatab .k { color: %MUTED%; font-size: 7.6pt; text-transform: uppercase;
    letter-spacing: 1px; }

/* toc */
.toc-item { border-bottom: 1px solid %LINE%; padding: 8px 2px; color: %TEXT%; font-size: 10pt; }
.toc-item .fid { color: %ACCENT%; font-family: "DejaVu Sans Mono", monospace;
    font-size: 8.5pt; margin-right: 8px; }
.toc-sub { color: %MUTED%; }

/* disclaimer + back */
.disc { color: %MUTED%; font-size: 8pt; line-height: 1.55; }
.back { background: %BG%; min-height: 24cm; padding: 6cm 2.4cm; }
.back h2 { color: %TEXT%; font-size: 26pt; font-weight: 300; }
.back h2 b { color: %ACCENT%; font-weight: 600; }
.back p { color: %MUTED%; font-size: 10pt; max-width: 15cm; }
.back .foot { color: #5b6472; font-size: 8pt; margin-top: 3cm; }
""".replace("%BG%", BG).replace("%PANEL2%", PANEL2).replace("%PANEL%", PANEL)\
   .replace("%TEXT%", TEXT).replace("%MUTED%", MUTED).replace("%ACCENT%", ACCENT)\
   .replace("%LINE%", LINE)


def build_html(spec):
    findings = spec.get("findings", [])
    project = spec.get("project", "Project")
    assessor = spec.get("assessor", "TrueL1")
    report_type = spec.get("report_type", "")
    assessed_on = spec.get("assessed_on", datetime.date.today().isoformat())

    sev_counts = {s: 0 for s in SEVERITY_ORDER}
    st_counts = {s: 0 for s in STATUS_ORDER}
    for f in findings:
        sev_counts[f.get("severity")] = sev_counts.get(f.get("severity"), 0) + 1
        st_counts[f.get("status")] = st_counts.get(f.get("status"), 0) + 1
    total = len(findings)

    sub = (f"{report_type} " if report_type else "") + "Security Assessment"

    # ---------- cover ----------
    cover = f"""
<div class="cover">
  <div class="brand">{SHIELD}<span class="name">{esc(assessor).upper()}</span>
    <span class="tag">AI-ASSISTED SMART CONTRACT REVIEW</span></div>
  <h1>{esc(project)}</h1>
  <div class="sub">{esc(sub)}</div>
  <div class="rule"></div>
  <div class="meta">Assessed by {esc(assessor)} on {esc(assessed_on)}</div>
</div>"""

    # ---------- executive summary ----------
    sevrows = ""
    for s in SEVERITY_ORDER:
        color, desc = SEVERITY[s]
        sevrows += (f'<div class="sevrow"><span class="n" style="color:{color}">'
                    f'{sev_counts[s]}</span><span class="b"><span class="nm">{s}'
                    f'</span><div class="ds">{esc(desc)}</div></span></div>')
    facts = ""
    for k, key in [("Types", "type"), ("Ecosystem", "ecosystem"),
                   ("Methods", "methods"), ("Language", "language"),
                   ("Timeline", "timeline")]:
        if spec.get(key):
            facts += (f'<div class="fact"><div class="k">{k}</div>'
                      f'<div class="v">{esc(spec[key])}</div></div>')
    statuslines = ""
    for s in STATUS_ORDER:
        if st_counts.get(s):
            statuslines += (f'<div class="fact"><div class="k">{s}</div>'
                            f'<div class="v">{st_counts[s]}</div></div>')

    execsum = f"""
<div class="sheet">
  <div class="sec-h"><div class="k">Executive Summary</div>
    <div class="t">Vulnerability Summary</div></div>
  <div class="col-wrap">
    <div class="col-main">{sevrows}</div>
    <div class="col-side">
      <div class="panel bignum"><div class="x">{total}</div>
        <div class="y">Total Findings</div></div>
      <div style="height:12px"></div>
      <div class="panel">{facts}</div>
      <div style="height:12px"></div>
      <div class="panel">{statuslines or '<div class="fact"><div class="k">Status</div><div class="v">-</div></div>'}</div>
    </div>
  </div>
</div>"""

    # ---------- table of contents ----------
    toc_items = "".join(
        f'<div class="toc-item toc-sub">{esc(t)}</div>' for t in
        ["Audit Summary", "Executive Summary", "Codebase", "Audit Scope",
         "Approach & Methods", "Findings"])
    toc_findings = "".join(
        f'<div class="toc-item"><span class="fid">{esc(f.get("id",""))}</span>'
        f'{esc(f.get("title",""))}</div>' for f in findings)
    toc = f"""
<div class="sheet">
  <div class="sec-h"><div class="k">Contents</div>
    <div class="t">Table of Contents</div></div>
  {toc_items}{toc_findings}
  <div class="toc-item toc-sub">Appendix</div>
  <div class="toc-item toc-sub">Disclaimer</div>
</div>"""

    # ---------- codebase + scope ----------
    scope_rows = "".join(f'<div class="mono">{esc(x)}</div>' for x in spec.get("scope", []))
    codebase = f"""
<div class="sheet">
  <div class="sec-h"><div class="k">Codebase</div><div class="t">Codebase &amp; Scope</div></div>
  <div class="panel">
    <div class="fact"><div class="k">Repository</div>
      <div class="v mono">{esc(spec.get("repository","-"))}</div></div>
    <div class="fact"><div class="k">Commit</div>
      <div class="v mono">{esc(spec.get("commit","-"))}</div></div>
    <div class="fact"><div class="k">In-Scope Files</div>
      <div class="v">{scope_rows or '-'}</div></div>
  </div>
</div>"""

    # ---------- approach ----------
    approach_default = (
        "This assessment evaluated the security and correctness of the in-scope "
        "contracts using a combination of manual review and static analysis.\n"
        "The review emphasised:\n"
        "- Architecture review and threat modelling to surface design-level risk.\n"
        "- Identification of common and edge-case vulnerability classes.\n"
        "- Manual verification of contract logic against intended behaviour.\n"
        "- Assessment of code quality, maintainability, and best-practice alignment.\n"
        "Note: this is an AI-assisted internal review intended to support a human "
        "reviewer. It is not a certification and does not replace an independent "
        "professional audit.")
    approach = f"""
<div class="sheet">
  <div class="sec-h"><div class="k">Methodology</div><div class="t">Approach &amp; Methods</div></div>
  {render_body(spec.get("approach", approach_default))}
</div>"""

    # ---------- findings summary ----------
    chips = f'<div class="chip"><span class="c" style="color:{TEXT}">{total}</span>' \
            f'<span class="l">Total</span></div>'
    for s in SEVERITY_ORDER:
        if sev_counts[s]:
            chips += (f'<div class="chip"><span class="c" style="color:'
                      f'{SEVERITY[s][0]}">{sev_counts[s]}</span>'
                      f'<span class="l">{s}</span></div>')
    rows = ""
    for f in findings:
        rows += (f'<tr><td class="mono">{esc(f.get("id",""))}</td>'
                 f'<td>{esc(f.get("title",""))}</td>'
                 f'<td>{esc(f.get("category",""))}</td>'
                 f'<td>{sev_badge(f.get("severity",""))}</td>'
                 f'<td>{status_badge(f.get("status",""))}</td></tr>')
    fsummary = f"""
<div class="sheet">
  <div class="sec-h"><div class="k">Findings</div><div class="t">Findings Summary</div></div>
  <div class="chips">{chips}</div>
  <table><thead><tr><th>ID</th><th>Title</th><th>Category</th>
    <th>Severity</th><th>Status</th></tr></thead>
  <tbody>{rows or '<tr><td colspan="5">No findings.</td></tr>'}</tbody></table>
</div>"""

    # ---------- per-finding ----------
    finding_pages = ""
    for f in findings:
        finding_pages += f"""
<div class="finding sheet">
  <div class="fid">{esc(f.get("id",""))}</div>
  <div class="ftitle">{esc(f.get("title",""))}</div>
  <table class="metatab"><tr>
    <td><div class="k">Category</div>{esc(f.get("category",""))}</td>
    <td><div class="k">Severity</div>{sev_badge(f.get("severity",""))}</td>
    <td><div class="k">Location</div><span class="mono">{esc(f.get("location","-"))}</span></td>
    <td><div class="k">Status</div>{status_badge(f.get("status",""))}</td>
  </tr></table>
  <h3>Description</h3>
  {render_body(f.get("description",""))}
  <h3>Recommendation</h3>
  {render_body(f.get("recommendation",""))}
</div>"""

    # ---------- appendix ----------
    approws = "".join(
        f'<tr><td>{sev_badge(s)}</td><td>{esc(SEVERITY[s][1])}</td></tr>'
        for s in SEVERITY_ORDER)
    appendix = f"""
<div class="finding sheet">
  <div class="sec-h"><div class="k">Appendix</div><div class="t">Severity Definitions</div></div>
  <table><thead><tr><th>Severity</th><th>Definition</th></tr></thead>
  <tbody>{approws}</tbody></table>
</div>"""

    # ---------- disclaimer (original TrueL1 text) ----------
    disclaimer = f"""
<div class="sheet">
  <div class="sec-h"><div class="k">Legal</div><div class="t">Disclaimer</div></div>
  <div class="disc">
  <p>This document is a TrueL1 AI-assisted security review prepared for internal
  use by the project team. It is provided on an "as is" and "as available" basis
  for informational purposes only.</p>
  <p>This review is <b>not</b> a professional audit, certification, endorsement,
  or guarantee of any kind. It does not warrant that the reviewed code is free of
  vulnerabilities, errors, or defects, and it may contain false positives and
  false negatives. Automated and AI-assisted analysis can misinterpret source
  material; important findings must be independently verified against the
  original code before any reliance is placed on them.</p>
  <p>Nothing in this document constitutes financial, investment, legal, tax, or
  regulatory advice, and it must not be used to make investment decisions or be
  relied upon by any third party. Blockchain systems carry ongoing risk; each
  party is responsible for its own due diligence and continuous security. For any
  high-value or production deployment, an independent professional audit is
  strongly recommended.</p>
  <p>&copy; {datetime.date.today().year} {esc(assessor)}. Prepared for the {esc(project)} project team.</p>
  </div>
</div>"""

    # ---------- back cover ----------
    back = f"""
<div class="back sheet">
  <div class="brand">{SHIELD}<span class="name" style="color:{TEXT};font-size:13pt;letter-spacing:3px;font-weight:700;margin-left:10px;vertical-align:middle;">{esc(assessor).upper()}</span></div>
  <h2 style="margin-top:1.4cm">Build on a <b>verifiable</b> foundation</h2>
  <p>TrueL1 is an AI-assisted smart-contract review toolchain used to help a
  human reviewer find issues and precedents quickly - a complement to, not a
  replacement for, an independent professional audit.</p>
  <div class="foot">{esc(project)} {esc(sub)} &middot; Assessed by {esc(assessor)}
  on {esc(assessed_on)} &middot; Confidential</div>
</div>"""

    return (f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<style>{css()}</style></head><body>"
            f"{cover}{execsum}{toc}{codebase}{approach}{fsummary}"
            f"{finding_pages}{appendix}{disclaimer}{back}"
            f"</body></html>")


def render_pdf(spec, out_path):
    from weasyprint import HTML  # lazy: lets build_html be imported/tested without it
    HTML(string=build_html(spec)).write_pdf(out_path)


def main():
    ap = argparse.ArgumentParser(description="Generate a TrueL1 assessment PDF.")
    ap.add_argument("spec", help="path to the JSON report spec")
    ap.add_argument("--output", "-o", required=True, help="output PDF path")
    args = ap.parse_args()
    with open(args.spec) as f:
        spec = json.load(f)
    render_pdf(spec, args.output)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
