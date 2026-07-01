#!/usr/bin/env python3
"""TrueL1 PDF Generator - Fixed version with proper error handling."""
import sys
import os
import re
import argparse
import traceback
from datetime import datetime

try:
    from weasyprint import HTML
except ImportError:
    print("ERROR: weasyprint not installed. Run: /opt/ai-temp/slither-env/bin/pip install weasyprint", file=sys.stderr)
    sys.exit(1)


def markdown_to_html(md_text):
    """Convert markdown to HTML with proper formatting."""
    html = md_text

    # Preserve code blocks first
    code_blocks = []
    def save_code(match):
        code_blocks.append(match.group(1))
        return f"CODEBLOCK{len(code_blocks)-1}CODEBLOCK"
    html = re.sub(r'```(?:\w+)?\n(.*?)```', save_code, html, flags=re.DOTALL)

    # Escape HTML special chars in remaining text
    html = html.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    # Restore code blocks with proper formatting
    for i, code in enumerate(code_blocks):
        escaped_code = code.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        html = html.replace(f'CODEBLOCK{i}CODEBLOCK', f'<pre class="code"><code>{escaped_code}</code></pre>')

    # Headers
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)

    # Bold and italic
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'(?<![\*\w])\*([^\*\n]+?)\*(?![\*\w])', r'<em>\1</em>', html)

    # Inline code
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)

    # Tables (simple pipe format)
    def format_table(match):
        try:
            rows = match.group(0).strip().split('\n')
            if len(rows) < 2:
                return match.group(0)
            html_table = '<table>'
            header_row = True
            for row in rows:
                if re.match(r'^\s*\|?\s*[-|:\s]+\|?\s*$', row):
                    continue
                cells = [c.strip() for c in row.strip().strip('|').split('|')]
                tag = 'th' if header_row else 'td'
                html_table += '<tr>' + ''.join(f'<{tag}>{c}</{tag}>' for c in cells) + '</tr>'
                header_row = False
            html_table += '</table>'
            return html_table
        except Exception:
            return match.group(0)
    html = re.sub(r'(\|[^\n]+\|\n\|[-:|\s]+\|(?:\n\|[^\n]+\|)*)', format_table, html)

    # Ordered lists (numbered)
    lines = html.split('\n')
    result_lines = []
    in_ol = False
    for line in lines:
        if re.match(r'^\d+\.\s+', line):
            if not in_ol:
                result_lines.append('<ol>')
                in_ol = True
            content = re.sub(r'^\d+\.\s+', '', line)
            result_lines.append(f'<li>{content}</li>')
        else:
            if in_ol:
                result_lines.append('</ol>')
                in_ol = False
            result_lines.append(line)
    if in_ol:
        result_lines.append('</ol>')
    html = '\n'.join(result_lines)

    # Unordered lists (dash or asterisk)
    lines = html.split('\n')
    result_lines = []
    in_ul = False
    for line in lines:
        if re.match(r'^[-\*]\s+', line):
            if not in_ul:
                result_lines.append('<ul>')
                in_ul = True
            content = re.sub(r'^[-\*]\s+', '', line)
            result_lines.append(f'<li>{content}</li>')
        else:
            if in_ul:
                result_lines.append('</ul>')
                in_ul = False
            result_lines.append(line)
    if in_ul:
        result_lines.append('</ul>')
    html = '\n'.join(result_lines)

    # Links
    html = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', html)

    # Horizontal rules
    html = re.sub(r'^---+$', r'<hr>', html, flags=re.MULTILINE)

    # Paragraphs (double newlines)
    paragraphs = html.split('\n\n')
    result = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if any(p.startswith(t) for t in ['<h', '<ul', '<ol', '<pre', '<table', '<hr', '<li']):
            result.append(p)
        else:
            result.append(f'<p>{p}</p>')

    return '\n'.join(result)


HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
@page { size: A4; margin: 2cm 1.5cm; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: sans-serif; color: #1a1a1a; line-height: 1.65; }
.cover { background: #0B1220; color: white; padding: 60px 40px; margin: -40px -40px 40px -40px; page-break-after: always; min-height: 90vh; }
.cover .logo { font-size: 14px; font-weight: 700; letter-spacing: 0.15em; color: #A8FF78; margin-bottom: 32px; text-transform: uppercase; }
.cover h1 { font-size: 44px; font-weight: 800; margin-bottom: 16px; line-height: 1.15; color: white; border: none; padding: 0; }
.cover .subtitle { font-size: 20px; color: #93C5FD; margin-bottom: 48px; font-weight: 400; }
.cover .meta { margin-top: 60px; padding-top: 32px; border-top: 1px solid rgba(255,255,255,0.15); font-size: 13px; color: #94A3B8; }
.cover .meta strong { color: #E5E7EB; }
.container { padding: 20px 40px; max-width: 900px; margin: 0 auto; }
h1 { color: #0B1220; font-size: 28px; font-weight: 700; margin: 36px 0 20px 0; padding-bottom: 12px; border-bottom: 3px solid #A8FF78; page-break-after: avoid; }
h2 { color: #059669; font-size: 22px; font-weight: 700; margin: 28px 0 14px 0; page-break-after: avoid; }
h3 { color: #1a1f3a; font-size: 18px; font-weight: 600; margin: 24px 0 12px 0; page-break-after: avoid; }
h4 { color: #374151; font-size: 15px; font-weight: 600; margin: 18px 0 8px 0; page-break-after: avoid; }
p { margin: 10px 0; color: #374151; font-size: 12pt; }
strong { color: #0B1220; font-weight: 600; }
em { color: #4B5563; }
code { background: #F3F4F6; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 10pt; color: #DC2626; }
pre.code { background: #0B1220; color: #A8FF78; padding: 16px 20px; border-radius: 8px; overflow-x: auto; margin: 16px 0; page-break-inside: avoid; border-left: 4px solid #059669; }
pre.code code { background: transparent; color: inherit; padding: 0; font-size: 10pt; line-height: 1.5; }
ul, ol { margin: 12px 0 12px 28px; }
li { margin: 5px 0; color: #374151; font-size: 12pt; line-height: 1.6; }
table { width: 100%; border-collapse: collapse; margin: 16px 0; page-break-inside: avoid; }
th { background: #F9FAFB; padding: 10px 14px; text-align: left; font-size: 11pt; text-transform: uppercase; letter-spacing: 0.03em; color: #4B5563; font-weight: 600; border-bottom: 2px solid #E5E7EB; }
td { padding: 10px 14px; border-bottom: 1px solid #E5E7EB; font-size: 11pt; color: #1F2937; }
a { color: #2563EB; text-decoration: none; }
hr { border: none; border-top: 1px solid #E5E7EB; margin: 24px 0; }
.footer-stamp { margin-top: 60px; padding: 24px; background: #059669; color: white; border-radius: 12px; text-align: center; page-break-inside: avoid; }
.footer-stamp .title { font-size: 10pt; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase; }
.footer-stamp .name { font-size: 16pt; font-weight: 800; margin: 8px 0; }
.footer-stamp .details { font-size: 10pt; }
</style>
</head>
<body>
<div class="cover">
<div class="logo">TrueL1 - {model_name}</div>
<h1>{title}</h1>
<div class="subtitle">{subtitle}</div>
<div class="meta">
<strong>Generated:</strong> {timestamp}<br>
<strong>Source:</strong> {model_name} on RTX 8000<br>
<strong>Server:</strong> fmeinc @ 192.168.1.15<br>
<strong>Classification:</strong> Confidential - Internal Use
</div>
</div>
<div class="container">
{content}
<div class="footer-stamp">
<div class="title">Generated By</div>
<div class="name">TrueL1 AI Server</div>
<div class="details">DeepSeek-R1 70B on NVIDIA RTX 8000 - 100 Percent Offline</div>
</div>
</div>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description='TrueL1 PDF Generator')
    parser.add_argument('input', help='Input markdown/text file')
    parser.add_argument('-t', '--title', default='TrueL1 AI Output', help='Document title')
    parser.add_argument('-s', '--subtitle', default='Generated Report', help='Document subtitle')
    parser.add_argument('-m', '--model', default='TrueL1 AI', help='Which model generated this')
    parser.add_argument('-o', '--output', help='Output PDF path')
    args = parser.parse_args()

    # Read input
    if not os.path.exists(args.input):
        print(f"ERROR: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.input, 'r', encoding='utf-8', errors='replace') as f:
            md_text = f.read()
    except Exception as e:
        print(f"ERROR: Could not read input file: {e}", file=sys.stderr)
        sys.exit(1)

    if not md_text.strip():
        print("ERROR: Input file is empty", file=sys.stderr)
        sys.exit(1)

    # Convert markdown to HTML
    try:
        content_html = markdown_to_html(md_text)
    except Exception as e:
        print(f"ERROR: Markdown conversion failed: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        base = os.path.splitext(os.path.basename(args.input))[0]
        output_path = f'/opt/ai-temp/reports/{base}-{timestamp}.pdf'

    # Make sure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
        except Exception as e:
            print(f"ERROR: Could not create output directory: {e}", file=sys.stderr)
            sys.exit(1)

    # Escape special characters for template substitution
    safe_title = args.title.replace('{', '{{').replace('}', '}}')
    safe_subtitle = args.subtitle.replace('{', '{{').replace('}', '}}')
    safe_model = args.model.replace('{', '{{').replace('}', '}}')

    # Build full HTML - use replace instead of format to avoid brace conflicts
    full_html = HTML_TEMPLATE
    full_html = full_html.replace('{title}', args.title)
    full_html = full_html.replace('{subtitle}', args.subtitle)
    full_html = full_html.replace('{model_name}', args.model)
    full_html = full_html.replace('{timestamp}', datetime.now().strftime('%B %d, %Y at %H:%M UTC'))
    full_html = full_html.replace('{content}', content_html)

    # Generate PDF with proper error handling
    print(f"Generating PDF: {output_path}", file=sys.stderr)
    try:
        HTML(string=full_html).write_pdf(output_path)
    except Exception as e:
        print(f"ERROR: PDF generation failed: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

    # Verify file was created
    if not os.path.exists(output_path):
        print(f"ERROR: PDF was not created at {output_path}", file=sys.stderr)
        sys.exit(1)

    file_size = os.path.getsize(output_path)
    if file_size == 0:
        print(f"ERROR: PDF is empty (0 bytes) at {output_path}", file=sys.stderr)
        sys.exit(1)

    print(f"SUCCESS: PDF created at {output_path} ({file_size:,} bytes)")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"FATAL ERROR: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
