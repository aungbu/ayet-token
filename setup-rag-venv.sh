#!/bin/bash
# TrueL1 RAG - separate virtual environment   (DEFERRED)
# =====================================================
# *** DO NOT RUN THIS YET. *** You currently have an install hold in place.
# This is provided ready for when you lift it. It installs packages.
#
# What it does: creates an isolated venv for the RAG tool so it stops sharing
# slither-env. The PDF step stays on slither-env (that is where WeasyPrint is
# installed) - rag_query.py already hardcodes slither-env's python for that
# subprocess, so only the RAG scripts themselves move to the new env.
#
# Does NOT touch Layer1 / Besu.

set -euo pipefail

ENV=/opt/ai-temp/rag-env

echo "Creating isolated RAG venv at ${ENV}..."
python3 -m venv "$ENV"
"$ENV/bin/pip" install --quiet --upgrade pip
"$ENV/bin/pip" install --quiet pymupdf numpy requests

# Point the shortcuts' interpreter at the new env. The md-to-pdf subprocess
# inside rag_query.py stays on slither-env and is unaffected.
sed -i 's#^RAG_PY=.*#RAG_PY='"$ENV"'/bin/python3#' /opt/ai-temp/rag/rag-shortcuts.sh

echo "Done. RAG now runs in ${ENV}."
echo "Reload shell functions:  source /opt/ai-temp/rag/rag-shortcuts.sh"
echo "Sanity check:            rag-list | head"
