# TrueL1 AI Shortcuts
# Source this file from ~/.bashrc: source /opt/ai-temp/truel1-shortcuts.sh
# Provides: ask(), tl-scan, tl-audit, tl-build, tl-fix, tl-ops

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
    ollama run "$model" "$prompt" > "$mdfile"
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    if [ ! -s "$mdfile" ]; then
        echo ""
        echo "ERROR: AI produced no output (took ${duration}s)"
        echo "Try: systemctl restart ollama; then retry"
        return 1
    fi

    local md_size=$(wc -c < "$mdfile")
    echo ""
    echo "AI DONE in ${duration}s. Response: ${md_size} bytes"
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
        rm -f "$mdfile"
    else
        echo ""
        echo "ERROR: PDF conversion failed (exit code: $pdf_result)"
        echo "Markdown saved at: $mdfile"
        echo ""
        echo "Debug command:"
        echo "  /opt/ai-temp/slither-env/bin/python3 /opt/ai-temp/md-to-pdf.py \"$mdfile\" --output /tmp/debug.pdf"
    fi
}

alias tl-scan='ask truel1-security-check'
alias tl-audit='ask truel1-sm-audit'
alias tl-build='ask truel1-build'
alias tl-fix='ask truel1-fix'
alias tl-ops='ask truel1-l1-ops'

echo "TrueL1 shortcuts loaded: ask, tl-scan, tl-audit, tl-build, tl-fix, tl-ops"
