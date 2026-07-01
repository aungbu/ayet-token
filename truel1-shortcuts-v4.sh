#!/bin/bash
# TrueL1 AI Shortcuts v4
# Uses the Ollama HTTP API (not `ollama run`) so NO terminal spinner/cursor
# codes ever reach the file. For DeepSeek-R1 models the API keeps the model's
# reasoning in a separate `thinking` field, so `.response` is already clean.

ask() {
    if [ $# -lt 2 ]; then
        echo "Usage: ask <model> \"<prompt>\" [title]"
        echo ""
        echo "Models: truel1-security-check, truel1-sm-audit,"
        echo "        truel1-build, truel1-fix, truel1-l1-ops"
        return 1
    fi

    local model="$1"
    local prompt="$2"
    local title="${3:-AI Response}"

    local clean_name
    clean_name=$(echo "$title" | tr '[:upper:]' '[:lower:]' \
        | tr -c '[:alnum:]' '-' | sed 's/-\+/-/g; s/^-//; s/-$//')
    local ts
    ts=$(date +%Y%m%d-%H%M%S)
    local mdfile="/tmp/${clean_name}-${ts}.md"
    local pdfout="/opt/ai-temp/reports/${clean_name}-${ts}.pdf"

    echo "==================================="
    echo "  MODEL:  $model"
    echo "  TITLE:  $title"
    echo "  OUTPUT: $pdfout"
    echo "==================================="
    echo ""
    echo "Asking AI via API (2-10 min for 70B models)..."

    local start end dur
    start=$(date +%s)

    # Compact JSON via jq (safe escaping) -> API -> extract only .response
    jq -cn --arg m "$model" --arg p "$prompt" \
        '{model:$m, prompt:$p, stream:false}' \
      | curl -s --max-time 1800 -X POST \
            http://127.0.0.1:11434/api/generate \
            -H "Content-Type: application/json" \
            --data-binary @- \
      | jq -r '.response // empty' > "$mdfile"

    end=$(date +%s)
    dur=$((end - start))

    if [ ! -s "$mdfile" ]; then
        echo ""
        echo "ERROR: empty response after ${dur}s."
        echo "Check:  systemctl status ollama"
        echo "        curl -s http://127.0.0.1:11434/api/tags | jq ."
        return 1
    fi

    echo "AI done in ${dur}s ($(wc -c < "$mdfile") bytes)."
    echo "Converting to PDF..."

    /opt/ai-temp/slither-env/bin/python3 /opt/ai-temp/md-to-pdf.py "$mdfile" \
        --title "$title" --subtitle "AI Response" \
        --model "$model" --output "$pdfout"

    if [ -s "$pdfout" ]; then
        echo ""
        echo "==================================="
        echo "  SUCCESS"
        echo "==================================="
        echo "  PDF:  $pdfout"
        echo "  Size: $(du -h "$pdfout" | cut -f1)"
        echo "  View: http://l1.aucfans.com:3003/$(basename "$pdfout")"
        echo ""
        rm -f "$mdfile"
    else
        echo ""
        echo "ERROR: PDF conversion failed. Raw markdown kept at: $mdfile"
    fi
}

alias tl-scan='ask truel1-security-check'
alias tl-audit='ask truel1-sm-audit'
alias tl-build='ask truel1-build'
alias tl-fix='ask truel1-fix'
alias tl-ops='ask truel1-l1-ops'

echo "TrueL1 shortcuts v4 loaded (API-based, clean output): ask, tl-scan, tl-audit, tl-build, tl-fix, tl-ops"
