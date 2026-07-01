#!/bin/bash
# TrueL1 External Audit Reference RAG - shortcuts (v2)
# Source from ~/.bashrc:  source /opt/ai-temp/rag/rag-shortcuts.sh
#
# This is a REFERENCE tool over external third-party audit PDFs. It does not
# train a model and is not a substitute for a professional audit.

RAG_PY=/opt/ai-temp/slither-env/bin/python3
RAG_DIR=/opt/ai-temp/rag

# Build (or rebuild) the index. Re-run once to enable page citations (index v2),
# and again whenever you add or change PDFs. Does not touch Layer1 / Besu.
rag-build() {
    "$RAG_PY" "$RAG_DIR/rag_ingest.py"
}

# List indexed audits (optionally filtered) - use this to find an exact --source.
#   rag-list             (all audits)
#   rag-list AKIMOTO     (audits whose filename contains AKIMOTO)
rag-list() {
    "$RAG_PY" "$RAG_DIR/rag_query.py" --list "${1:-}"
}

# Ask a question against the indexed audits.
#   rag-ask "question"
#   rag-ask "question" --source AKIMOTO --exact     (one audit, loaded in full)
#   rag-ask "question" --model deepseek-r1:70b      (deeper review)
#   rag-ask "question" --min-score 0.3              (abstain if weakly matched)
#   rag-ask "question" --pdf --title "My Report"
rag-ask() {
    if [ $# -lt 1 ]; then
        echo 'Usage: rag-ask "question" [--source NAME [--exact]] [--model deepseek-r1:70b] [--min-score 0.3] [--pdf --title "Title"]'
        return 1
    fi
    "$RAG_PY" "$RAG_DIR/rag_query.py" "$@"
}

# Show retrieval scores for a query WITHOUT calling the model (read-only).
# Use this to calibrate a sensible --min-score threshold.
#   rag-scores "question"
#   rag-scores "question" --k 10
rag-scores() {
    if [ $# -lt 1 ]; then
        echo 'Usage: rag-scores "question" [--k 10]'
        return 1
    fi
    "$RAG_PY" "$RAG_DIR/rag_query.py" "$@" --scores-only
}

echo "TrueL1 External Audit Reference RAG (v2) loaded: rag-build, rag-list, rag-ask, rag-scores"
