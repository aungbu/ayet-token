# TrueL1 AI Shortcuts v3 - Fixed control character stripping
# Source: source /opt/ai-temp/truel1-shortcuts.sh

# Strip ANSI escape codes and control characters using Python (reliable)
_strip_ansi() {
    /opt/ai-temp/slither-env/bin/python3 -c "
import sys
import re
data = sys.stdin.read()
# Strip ANSI escape sequences (CSI codes)
data = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', data)
data = re.sub(r'\x1b\[[0-9]*[A-Z]', '', data)
data = re.sub(r'\x1b[<=>]', '', data)
# Strip other control characters except newlines, tabs, and carriage returns
data = ''.join(c for c in data if c == '\n' or c == '\t' or c == '\r' or ord(c) >= 32)
# Remove Thinking blocks from DeepSeek-R1
data = re.sub(r'Thinking\.\.\.\n.*?\.\.\.done thinking\.\n', '', data, flags=re.DOTALL)
data = re.sub(r'<think>.*?</think>\n?', '', data, flags=re.DOTALL)
# Remove excessive blank lines
data = re.sub(r'\n{3,}', '\n\n', data)
# Strip leading whitespace
data = data.lstrip()
sys.stdout.write(data)
"
}

ask() {
    if [ $# -lt 2 ]; then
        echo "Usage: ask <model> \"<prompt>\" [title]"
        echo ""
        echo "Available models:"
        echo "  truel1-security-check  - Vulnerability scanner"
        echo "  truel1-sm-audit        - Full audit reports"
        echo "  truel1-build           - Design new contracts"
        echo "  truel1-fix             - Fix vulnerable code"
        echo "  truel1-l1-ops          - Besu/L1 operations"
        return 1
    fi

    local model=$1
    local prompt=$2
    local title=${3:-"AI Response"}
    local clean_name=$(echo "$title" | tr '[:upper:]' '[:lower:]' | tr -c '[:alnum:]' '-' | sed 's/--*/-/g' | sed 's/^-\|-$//g')
    local timestamp=$(date +%Y%m%d-%H%M%S)
    local rawfile="/tmp/${clean_name}-${timestamp}.raw"
    local mdfile="/tmp/${clean_name}-${timestamp}.md"
    local pdfout="/opt/ai-temp/reports/${clean_name}-${timestamp}.pdf"

    echo ""
    echo "==================================="
    echo "  MODEL:  $model"
    echo "  TITLE:  $title"
    echo "  OUTPUT: $pdfout"
    echo "==================================="
    echo ""
    echo "AI thinking (this may take 2-10 minutes)..."

    local start_time=$(date +%s)

    # Instruct AI to give clean, formatted output
    local full_prompt="${prompt}

Please respond with clean markdown formatting. Use headings, bullet points, and code blocks appropriately. Provide only the final polished answer without internal reasoning notes or self-corrections."

    # Capture raw output
    ollama run "$model" "$full_prompt" > "$rawfile" 2>&1

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    if [ ! -s "$rawfile" ]; then
        echo ""
        echo "ERROR: AI produced no output (took ${duration}s)"
        echo "Try: systemctl restart ollama; then retry"
        rm -f "$rawfile"
        return 1
    fi

    local raw_size=$(wc -c < "$rawfile")

    # Clean the output using Python (reliable across all systems)
    _strip_ansi < "$rawfile" > "$mdfile"

    local md_size=$(wc -c < "$mdfile")

    if [ "$md_size" -lt 100 ]; then
        echo ""
        echo "WARNING: Very short cleaned response (${md_size} bytes from ${raw_size} raw)"
        echo "Raw file preserved at: $rawfile"
    fi

    echo ""
    echo "AI DONE in ${duration}s"
    echo "Raw: ${raw_size} bytes -> Cleaned: ${md_size} bytes"
    echo ""
    echo "Converting to PDF..."

    /opt/ai-temp/slither-env/bin/python3 /opt/ai-temp/md-to-pdf.py "$mdfile" \
        --title "$title" \
        --subtitle "AI Response" \
        --model "$model" \
        --output "$pdfout" 2>&1

    local pdf_result=$?

    if [ $pdf_result -eq 0 ] && [ -f "$pdfout" ] && [ -s "$pdfout" ]; then
        local pdf_size=$(du -h "$pdfout" | cut -f1)
        echo ""
        echo "==================================="
        echo "  SUCCESS!"
        echo "==================================="
        echo "  PDF:  $pdfout"
        echo "  Size: $pdf_size"
        echo "  View: http://l1.aucfans.com:3003/$(basename $pdfout)"
        echo ""
        # Clean up temp files
        rm -f "$rawfile" "$mdfile"
    else
        echo ""
        echo "ERROR: PDF conversion failed (exit code: $pdf_result)"
        echo "Raw output:    $rawfile"
        echo "Cleaned output: $mdfile"
        echo ""
        echo "You can manually convert with:"
        echo "  /opt/ai-temp/slither-env/bin/python3 /opt/ai-temp/md-to-pdf.py \"$mdfile\" --output /tmp/debug.pdf"
    fi
}

# Convenient aliases
alias tl-scan='ask truel1-security-check'
alias tl-audit='ask truel1-sm-audit'
alias tl-build='ask truel1-build'
alias tl-fix='ask truel1-fix'
alias tl-ops='ask truel1-l1-ops'

# Utility to clean an existing file
tl-clean() {
    if [ -z "$1" ]; then
        echo "Usage: tl-clean <input.md> [output.md]"
        return 1
    fi
    if [ ! -f "$1" ]; then
        echo "ERROR: File not found: $1"
        return 1
    fi
    local input=$1
    local output=${2:-"${input%.*}-clean.md"}
    _strip_ansi < "$input" > "$output"
    local size=$(wc -c < "$output")
    echo "Cleaned: $output ($size bytes)"
}

# Utility to preview what got cleaned
tl-diff() {
    if [ -z "$1" ]; then
        echo "Usage: tl-diff <file.raw or file.md>"
        return 1
    fi
    if [ ! -f "$1" ]; then
        echo "ERROR: File not found: $1"
        return 1
    fi
    echo "=== Original size ==="
    wc -c < "$1"
    echo ""
    echo "=== Cleaned size ==="
    _strip_ansi < "$1" | wc -c
    echo ""
    echo "=== First 500 chars of cleaned output ==="
    _strip_ansi < "$1" | head -c 500
    echo ""
    echo "..."
}

echo "TrueL1 shortcuts v3 loaded (Python-based cleaning): ask, tl-scan, tl-audit, tl-build, tl-fix, tl-ops, tl-clean, tl-diff"
