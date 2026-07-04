#!/bin/bash
# TrueAI shortcuts — source from ~/.bashrc:  source /opt/ai-temp/trueai-shortcuts.sh
TRUEAI_PY=/opt/ai-temp/slither-env/bin/python3
TRUEAI_DIR=/opt/ai-temp

# Ask TrueAI, grounded in its full library (Besu, Solidity, Foundry, OZ, security/multisig, your L1)
trueai-ask() {
    if [ $# -lt 1 ]; then
        echo 'Usage: trueai-ask "your question" [--model trueai] [--k 8]'
        return 1
    fi
    "$TRUEAI_PY" "$TRUEAI_DIR/trueai_query.py" "$@"
}
# Rebuild TrueAI's library knowledge (after adding docs to the library)
trueai-learn() {
    "$TRUEAI_PY" "$TRUEAI_DIR/rag_ingest_library.py"
}
echo "TrueAI loaded: trueai-ask \"question\"  ·  trueai-learn (rebuild library index)"
