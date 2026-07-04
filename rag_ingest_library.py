#!/usr/bin/env python3
"""
TrueAI Library RAG Ingest
-------------------------
Extends the audit-PDF RAG to ALSO learn the local TrueAI library: Besu docs,
Solidity docs, Foundry book, OpenZeppelin sources, and the security/multisig
best-practice guides. Indexes .md, .txt, .sol, .rst files (text) plus the
existing audit PDFs, so TrueAI can answer grounded in all of it.

Writes to a SEPARATE index dir so it doesn't disturb the audit-only index.
Run with the venv python:  /opt/ai-temp/slither-env/bin/python3 rag_ingest_library.py
"""
import os, sys, re, json, glob, time
import numpy as np
import requests
try:
    import fitz
except ImportError:
    import pymupdf as fitz

OLLAMA = "http://127.0.0.1:11434"
EMBED_MODEL = "nomic-embed-text"

# sources: audit PDFs + the whole TrueAI library docs
PDF_DIR = "/opt/ai-temp/coinsult-audits"
LIBRARY_DIR = "/mnt/ai/trueai-library"
LOCAL_DOCS = "/opt/ai-temp/trueai-l1-docs"   # your own L1 architecture docs (we create these)
INDEX_DIR = "/opt/ai-temp/rag/index-library"  # SEPARATE from the audit index

CHUNK_CHARS = 1200
CHUNK_OVERLAP = 200
EMBED_BATCH = 32

# only ingest text-like docs; skip binaries, node_modules bloat, images, tars
TEXT_EXT = (".md", ".txt", ".rst", ".sol", ".adoc")
SKIP_DIRS = ("node_modules", ".git", "test", "tests", "coverage",
             "besu-image", ".github", "dist", "build", "target")
SKIP_NAME_SUBSTR = (".tar", ".png", ".jpg", ".jar", ".gz")

def extract_pdf(path):
    try:
        doc = fitz.open(path)
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return text.strip()
    except Exception as e:
        print(f"  ! pdf failed {os.path.basename(path)}: {e}")
        return ""

def read_text(path):
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read().strip()
    except Exception:
        return ""

def chunk_text(text):
    text = re.sub(r"\n{3,}", "\n\n", text)
    chunks, start, n = [], 0, len(text)
    while start < n:
        end = min(start + CHUNK_CHARS, n)
        chunks.append(text[start:end])
        start += CHUNK_CHARS - CHUNK_OVERLAP
    return [c for c in chunks if c.strip()]

def gather_sources():
    items = []  # (source_label, text)
    # 1) audit PDFs
    for p in sorted(glob.glob(os.path.join(PDF_DIR, "*.pdf"))):
        t = extract_pdf(p)
        if t: items.append((f"audit:{os.path.basename(p)}", t))
    # 2) your own L1 architecture docs (highest value)
    if os.path.isdir(LOCAL_DOCS):
        for root, dirs, files in os.walk(LOCAL_DOCS):
            for fn in files:
                if fn.lower().endswith(TEXT_EXT):
                    t = read_text(os.path.join(root, fn))
                    if t: items.append((f"fme-l1:{fn}", t))
    # 3) the TrueAI library docs (Besu, Solidity, Foundry, OZ, security)
    if os.path.isdir(LIBRARY_DIR):
        for root, dirs, files in os.walk(LIBRARY_DIR):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fn in files:
                if any(s in fn.lower() for s in SKIP_NAME_SUBSTR):
                    continue
                if fn.lower().endswith(TEXT_EXT):
                    p = os.path.join(root, fn)
                    # tag by which library section it came from
                    rel = os.path.relpath(p, LIBRARY_DIR)
                    section = rel.split(os.sep)[0]
                    t = read_text(p)
                    if t and len(t) > 100:  # skip tiny stubs
                        items.append((f"lib/{section}:{fn}", t))
    return items

def embed_batch(texts):
    r = requests.post(f"{OLLAMA}/api/embed",
                      json={"model": EMBED_MODEL, "input": texts}, timeout=300)
    r.raise_for_status()
    return r.json()["embeddings"]

def main():
    os.makedirs(INDEX_DIR, exist_ok=True)
    print("Gathering sources (audits + your L1 docs + library)...")
    sources = gather_sources()
    print(f"  {len(sources)} documents found.")
    all_chunks, meta = [], []
    for label, text in sources:
        for ch in chunk_text(text):
            all_chunks.append(ch)
            meta.append(label)
    print(f"  {len(all_chunks)} chunks. Embedding on GPU (this can take a while)...")
    embs = []
    for i in range(0, len(all_chunks), EMBED_BATCH):
        batch = all_chunks[i:i+EMBED_BATCH]
        embs.extend(embed_batch(batch))
        if (i // EMBED_BATCH) % 20 == 0:
            print(f"    embedded {i+len(batch)}/{len(all_chunks)}")
    arr = np.array(embs, dtype=np.float32)
    np.save(os.path.join(INDEX_DIR, "embeddings.npy"), arr)
    json.dump({"chunks": all_chunks, "meta": meta},
              open(os.path.join(INDEX_DIR, "chunks.json"), "w"))
    print(f"Done. Index: {arr.shape[0]} chunks, dim {arr.shape[1] if arr.ndim>1 else 0}")
    print(f"Saved to {INDEX_DIR}")
    # source breakdown
    from collections import Counter
    kinds = Counter(m.split(":")[0].split("/")[0] for m in meta)
    print("Sources:", dict(kinds))

if __name__ == "__main__":
    main()
