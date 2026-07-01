#!/bin/bash
# TrueL1 RAG v2 - pinned deploy   (REVIEW FIRST, run only when you're ready)
# ==========================================================================
# Downloads the three v2 scripts from ONE specific reviewed commit (not the
# moving 'main' branch) and verifies each file's sha256 before installing.
# Nothing is written unless every hash matches. Does NOT touch Layer1 / Besu
# and installs NO packages.
#
# STEPS:
#   1. Upload rag_ingest.py, rag_query.py, rag-shortcuts.sh to your repo and
#      commit them (upload the files unchanged so the hashes below match).
#   2. Paste the commit's full 40-char SHA into COMMIT= below.
#   3. Review this script. Then run it:  bash deploy-rag-v2.sh
#   4. After it finishes, reload the shell functions:
#        source /opt/ai-temp/rag/rag-shortcuts.sh
#   5. (Optional, when ready) enable page citations by re-indexing:  rag-build

set -euo pipefail

REPO="aungbu/ayet-token"
COMMIT="PUT_REVIEWED_40_CHAR_COMMIT_SHA_HERE"
DEST="/opt/ai-temp/rag"
BASE="https://raw.githubusercontent.com/${REPO}/${COMMIT}"

# Expected sha256 of each v2 file (hashes of the reviewed artifacts).
EXPECT_ingest="abe67cc6e0e3d5e72f9d806be254479c9a2a7e245df1b19e58698ca7ab2b1386"
EXPECT_query="7754518b095f9b86335ebc2cf48ef2b07030c900c5a43b84f53b33f212bce77c"
EXPECT_shortcuts="7983b490a3e34ead1e40ab27f9b898748d79c6ebb884046695ea8069c112f2f0"

if [ "$COMMIT" = "PUT_REVIEWED_40_CHAR_COMMIT_SHA_HERE" ]; then
    echo "Set COMMIT= to your reviewed commit SHA first. Aborting."
    exit 1
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

verify() {  # $1 = filename, $2 = expected sha256
    curl -fsSL "${BASE}/$1" -o "${tmp}/$1"
    got="$(sha256sum "${tmp}/$1" | awk '{print $1}')"
    if [ "$got" != "$2" ]; then
        echo "SHA256 MISMATCH for $1"
        echo "  got:  $got"
        echo "  want: $2"
        echo "Aborting. Nothing installed."
        exit 1
    fi
    echo "  ok  $1  (${got:0:12}...)"
}

echo "Downloading v2 from commit ${COMMIT:0:12}... and verifying hashes:"
verify "rag_ingest.py"    "$EXPECT_ingest"
verify "rag_query.py"     "$EXPECT_query"
verify "rag-shortcuts.sh" "$EXPECT_shortcuts"

echo "All hashes verified. Installing to ${DEST}..."
cp "${tmp}/rag_ingest.py"    "${DEST}/rag_ingest.py"
cp "${tmp}/rag_query.py"     "${DEST}/rag_query.py"
cp "${tmp}/rag-shortcuts.sh" "${DEST}/rag-shortcuts.sh"

echo
echo "v2 installed. Query-side improvements are active immediately."
echo "Reload shell functions:  source ${DEST}/rag-shortcuts.sh"
echo "Enable page citations (optional, re-embeds the index): rag-build"
