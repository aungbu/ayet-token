# TrueL1 AI Shortcuts v2 - With ANSI stripping and improved prompts
# Source: source /opt/ai-temp/truel1-shortcuts.sh

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

    # Run ollama with a prompt suffix that discourages self-editing artifacts
    local full_prompt="${prompt}

Please provide a clean, well-formatted final response. Do not include internal reasoning steps, self-corrections, or draft edits. Present only the polished final answer with clear headings and proper markdown formatting."

    # Save raw output, then strip ANSI codes and control characters
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

    # Clean the output:
    # 1. Strip ANSI escape sequences (colors, cursor movement)
    # 2. Strip control characters except newlines and tabs
    # 3. Remove "Thinking..." blocks if present
    # 4. Remove leading/trailing whitespace
    sed -e 's/\x1b\[[0-9;]*[a-zA-Z]//g' \
        -e 's/\x1b\[[0-9]*[A-Z]//g' \
        -e 's/\x1b[<=>]//g' \
        -e 's/[\x00-\x08\x0b-\x1f\x7f]//g' \
        "$rawfile" > "$mdfile"

    # Remove "Thinking..." and "...done thinking." markers from DeepSeek-R1
    sed -i '/^Thinking\.\.\.$/,/^\.\.\.done thinking\.$/d' "$mdfile"
    sed -i '/^<think>$/,/^<\/think>$/d' "$mdfile"

    # Remove any leading empty lines
    sed -i '/./,$!d' "$mdfile"

    local md_size=$(wc -c < "$mdfile")

    if [ "$md_size" -lt 100 ]; then
        echo ""
        echo "WARNING: Very short response (${md_size} bytes) - may not be complete"
    fi

    echo ""
    echo "AI DONE in ${duration}s. Response: ${md_size} bytes (cleaned)"
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
        # Keep the .md file for reference (helpful for debugging)
        # Comment the next line if you want to keep .md files:
        rm -f "$rawfile" "$mdfile"
    else
        echo ""
        echo "ERROR: PDF conversion failed (exit code: $pdf_result)"
        echo "Raw markdown saved at: $mdfile"
    fi
}

# Convenient aliases
alias tl-scan='ask truel1-security-check'
alias tl-audit='ask truel1-sm-audit'
alias tl-build='ask truel1-build'
alias tl-fix='ask truel1-fix'
alias tl-ops='ask truel1-l1-ops'

# Utility to clean an existing markdown file if it has terminal codes
tl-clean() {
    if [ -z "$1" ]; then
        echo "Usage: tl-clean <input.md> [output.md]"
        return 1
    fi
    local input=$1
    local output=${2:-"${input%.md}-clean.md"}
    sed -e 's/\x1b\[[0-9;]*[a-zA-Z]//g' \
        -e 's/\x1b\[[0-9]*[A-Z]//g' \
        -e 's/\x1b[<=>]//g' \
        -e 's/[\x00-\x08\x0b-\x1f\x7f]//g' \
        "$input" > "$output"
    echo "Cleaned: $output"
}

echo "TrueL1 shortcuts v2 loaded (ANSI-stripped): ask, tl-scan, tl-audit, tl-build, tl-fix, tl-ops, tl-clean"
