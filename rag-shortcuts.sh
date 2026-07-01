#!/bin/bash
# TrueL1 RAG shortcuts
# Source this from ~/.bashrc:  source /opt/ai-temp/rag/rag-shortcuts.sh

RAG_PY=/opt/ai-temp/slither-env/bin/python3
RAG_DIR=/opt/ai-temp/rag

# Build (or rebuild) the audit index. Run once, and again whenever you add PDFs.
rag-build() {
    "$RAG_PY" "$RAG_DIR/rag_ingest.py"
}

# Ask a question against the indexed audits.
#   rag-ask "your question"
#   rag-ask "your question" --model deepseek-r1:70b
#   rag-ask "your question" --pdf --title "My Report"
rag-ask() {
    if [ $# -lt 1 ]; then
        echo 'Usage: rag-ask "your question" [--model deepseek-r1:70b] [--k 8] [--pdf --title "Title"]'
        return 1
    fi
    "$RAG_PY" "$RAG_DIR/rag_query.py" "$@"
}

echo "TrueL1 RAG loaded: rag-build (index the audit PDFs), rag-ask \"question\""
