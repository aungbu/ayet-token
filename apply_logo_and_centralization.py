#!/usr/bin/env python3
"""
In-place patcher for the TrueL1 audit pipeline. Adds:
  (1) per-upload logo -> embedded in the report cover
  (2) centralization_check findings merged into every report
Run once on the server:  python3 apply_logo_and_centralization.py
Makes .bak_patch backups first. Idempotent-ish: warns if markers already present.
"""
import re, sys, os, shutil

TOOLS = "/opt/ai-temp"
REPORT = os.path.join(TOOLS, "truel1-report.py")
WEB = os.path.join(TOOLS, "truel1-audit-web.py")

def backup(p):
    shutil.copy(p, p + ".bak_patch")

# ---------- 1) truel1-report.py: embed logo in the cover ----------
def patch_report():
    s = open(REPORT).read()
    if "TL_LOGO_BLOCK" in s:
        print("report.py: logo block already present, skipping")
        return
    # a) read logo from spec near the other spec.get lines (after assessed_on line)
    anchor = 'assessed_on = spec.get("assessed_on", datetime.date.today().isoformat())'
    if anchor not in s:
        print("report.py: anchor for spec fields not found — NOT patched")
        return False
    inject = (anchor +
              '\n    logo_data = spec.get("logo", "")  # TL_LOGO_BLOCK: base64 data URI or empty')
    s = s.replace(anchor, inject, 1)

    # b) build a logo <img> (or fall back to SHIELD) and use it in the cover brand div
    cover_brand = '<div class="brand">{SHIELD}<span class="name">{esc(assessor).upper()}</span>'
    if cover_brand not in s:
        print("report.py: cover brand div not found — NOT patched")
        return False
    new_cover_brand = (
        '<div class="brand">{logo_html}<span class="name">{esc(assessor).upper()}</span>')
    s = s.replace(cover_brand, new_cover_brand, 1)

    # c) define logo_html just before the cover f-string is built.
    #    Insert after the `sub = (...) + "Security Assessment"` line.
    sub_line_re = re.compile(r'(\n\s*sub = \(f"\{report_type\} " if report_type else "AI Automated "\) \+ "Security Assessment"\n)')
    m = sub_line_re.search(s)
    if not m:
        # try a looser match
        sub_line_re = re.compile(r'(\n\s*sub = .+Security Assessment"\n)')
        m = sub_line_re.search(s)
    if not m:
        print("report.py: sub= line not found — NOT patched")
        return False
    logo_def = (m.group(1) +
        '    if logo_data:\n'
        '        logo_html = (f\'<img src="{logo_data}" alt="logo" \'\n'
        '                     f\'style="height:46px;width:auto;max-width:180px;'
        'vertical-align:middle;border-radius:6px;margin-right:10px;" />\')\n'
        '    else:\n'
        '        logo_html = SHIELD\n')
    s = s.replace(m.group(1), logo_def, 1)

    open(REPORT, "w").write(s)
    # validate
    import ast; ast.parse(open(REPORT).read())
    print("report.py: PATCHED (logo support added) + valid")
    return True

# ---------- 2) truel1-audit-web.py: logo upload + centralization merge ----------
def patch_web():
    s = open(WEB).read()
    if "TL_CENTRAL_MERGE" in s:
        print("web.py: already patched, skipping")
        return
    # a) after slither_to_spec writes spec, before rendering: merge centralization + add logo.
    # find the spec build + the render call, inject between them.
    render_anchor = 'rep = subprocess.run([PYBIN, os.path.join(TOOLS, "truel1-report.py"), spec, "-o", pdf],'
    if render_anchor not in s:
        print("web.py: render anchor not found — NOT patched")
        return False
    merge_code = (
'        # TL_CENTRAL_MERGE: add centralization findings + optional logo to the spec\n'
'        try:\n'
'            import json as _json, base64 as _b64\n'
'            _specd = _json.load(open(spec))\n'
'            # run the centralization checker on the uploaded .sol\n'
'            _cc = subprocess.run(\n'
'                [PYBIN, os.path.join(TOOLS, "centralization_check.py"),\n'
'                 os.path.join(work, safe), "--json", os.path.join(work, "central.json"),\n'
'                 "--name", safe],\n'
'                capture_output=True, text=True, timeout=60)\n'
'            if os.path.exists(os.path.join(work, "central.json")):\n'
'                _cd = _json.load(open(os.path.join(work, "central.json")))\n'
'                _specd.setdefault("findings", []).extend(_cd.get("findings", []))\n'
'            # optional per-upload logo (base64 data URI)\n'
'            if _LOGO_BYTES.get("data"):\n'
'                _mime = _LOGO_BYTES.get("mime", "image/png")\n'
'                _b = _b64.b64encode(_LOGO_BYTES["data"]).decode("ascii")\n'
'                _specd["logo"] = f"data:{_mime};base64,{_b}"\n'
'            _json.dump(_specd, open(spec, "w"))\n'
'        except Exception as _e:\n'
'            pass\n'
'        ' )
    s = s.replace(render_anchor, merge_code + render_anchor, 1)

    # b) run_audit needs the logo bytes. Add a param default and a module-level holder.
    #    Simplest: pass logo via a dict the handler sets. Add holder near top.
    if "_LOGO_BYTES" not in s.split("def run_audit")[0]:
        s = s.replace("MAX_UPLOAD = 3 * 1024 * 1024  # 3 MB",
                      "MAX_UPLOAD = 3 * 1024 * 1024  # 3 MB\n_LOGO_BYTES = {}  # per-request logo holder")

    # c) add a logo file input to the FORM
    form_field = '<input type="file" name="solfile" accept=".sol" required>'
    if form_field in s:
        s = s.replace(form_field,
            form_field +
            '\n  <label>Project / customer logo (optional, PNG/JPG)</label>'
            '\n  <input type="file" name="logo" accept="image/*">')

    # d) in do_POST, capture the logo upload into _LOGO_BYTES before run_audit
    post_anchor = 'is_final = (fields.get("final") == "1")'
    if post_anchor in s:
        s = s.replace(post_anchor, post_anchor +
'\n        _lg = fields.get("logo")\n'
'        _LOGO_BYTES.clear()\n'
'        if isinstance(_lg, dict) and _lg.get("data"):\n'
'            _fn = (_lg.get("filename") or "").lower()\n'
'            _mime = ("image/png" if _fn.endswith(".png") else\n'
'                     "image/jpeg" if _fn.endswith((".jpg", ".jpeg")) else\n'
'                     "image/webp" if _fn.endswith(".webp") else\n'
'                     "image/gif" if _fn.endswith(".gif") else "image/png")\n'
'            _LOGO_BYTES["data"] = _lg["data"]; _LOGO_BYTES["mime"] = _mime')

    open(WEB, "w").write(s)
    import ast; ast.parse(open(WEB).read())
    print("web.py: PATCHED (logo upload + centralization merge) + valid")
    return True

if __name__ == "__main__":
    ok = True
    backup(REPORT); backup(WEB)
    r = patch_report()
    w = patch_web()
    print("\nDONE." if (r is not False and w is not False) else "\nSOME PATCHES FAILED — check messages above; .bak_patch backups exist.")
