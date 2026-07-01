#!/usr/bin/env python3
"""
TrueL1 External Audit Reference RAG - Ingest  (v2, page-aware)
-------------------------------------------------------------
Reads every external audit PDF, extracts text PAGE BY PAGE, splits each page
into overlapping chunks, embeds each chunk with nomic-embed-text via the local
Ollama API, and saves a searchable NumPy index. Each chunk records the page it
came from so answers can cite [file.pdf, p.N]. No vector database, no running
service - just files on disk. Re-run any time you add or change PDFs.

Note: this is a REFERENCE index over public third-party reports. It does not
train a model and is not a substitute for a professional audit.
"""
import os
import sys
import re
import json
import glob
import time

import numpy as np
import requests

try:
    import fitz  # PyMuPDF
except ImportError:
    import pymupdf as fitz

OLLAMA = "http://127.0.0.1:11434"
EMBED_MODEL = "nomic-embed-text"
PDF_DIR = "/opt/ai-temp/coinsult-audits"
INDEX_DIR = "/opt/ai-temp/rag/index"
CHUNK_CHARS = 1200
CHUNK_OVERLAP = 200
EMBED_BATCH = 32
INDEX_VERSION = 2


def extract_pages(path):
    """Return [(page_number, text), ...], 1-indexed, skipping empty pages."""
    try:
        doc = fitz.open(path)
        pages = []
        for i, page in enumerate(doc, 1):
            t = page.get_text().strip()
            if t:
                pages.append((i, t))
        doc.close()
        return pages
    except Exception as e:
        print(f"  ! extract failed for {os.path.basename(path)}: {e}")
        return []


def chunk_text(text):
    """Sliding-window chunks within a single page's text."""
    text = re.sub(r"\n{3,}", "\n\n", text)
    chunks = []
    start, n = 0, len(text)
    while start < n:
        end = min(start + CHUNK_CHARS, n)
        piece = text[start:end].strip()
        if len(piece) > 50:
            chunks.append(piece)
        if end == n:
            break
        start = end - CHUNK_OVERLAP
    return chunks


def token_name(path):
    base = os.path.basename(path)
    base = re.sub(r"^Coinsult_", "", base)
    base = re.sub(r"_0x[0-9a-fA-F].*?_Audit\.pdf$", "", base)
    base = re.sub(r"_Audit\.pdf$", "", base)
    base = re.sub(r"\.pdf$", "", base)
    return base.replace("_", " ").strip() or os.path.basename(path)


def embed_texts(texts):
    """Batch embed via /api/embed; fall back to legacy /api/embeddings."""
    try:
        r = requests.post(
            f"{OLLAMA}/api/embed",
            json={"model": EMBED_MODEL, "input": texts},
            timeout=600,
        )
        r.raise_for_status()
        embs = r.json().get("embeddings")
        if embs and len(embs) == len(texts):
            return embs
    except Exception:
        pass
    out = []
    for t in texts:
        r = requests.post(
            f"{OLLAMA}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": t},
            timeout=120,
        )
        r.raise_for_status()
        out.append(r.json()["embedding"])
    return out


def main():
    pdfs = sorted(glob.glob(os.path.join(PDF_DIR, "*.pdf")))
    if not pdfs:
        print(f"No PDFs found in {PDF_DIR}")
        sys.exit(1)

    print(f"Found {len(pdfs)} PDFs. Extracting text page-by-page + chunking...")
    records = []
    skipped = 0
    for i, path in enumerate(pdfs, 1):
        pages = extract_pages(path)
        if not pages:
            skipped += 1
            continue
        tok = token_name(path)
        idx = 0
        for pno, ptext in pages:
            for c in chunk_text(ptext):
                records.append({
                    "text": c,
                    "source": os.path.basename(path),
                    "token": tok,
                    "page": pno,
                    "idx": idx,
                })
                idx += 1
        if i % 25 == 0 or i == len(pdfs):
            print(f"  {i}/{len(pdfs)} PDFs -> {len(records)} chunks so far")

    print(f"Extracted {len(records)} chunks ({skipped} PDFs skipped/empty).")
    if not records:
        print("Nothing to embed. Are these PDFs text-based (not scanned images)?")
        sys.exit(1)

    print(f"Embedding {len(records)} chunks with {EMBED_MODEL} on the GPU...")
    vectors = []
    t0 = time.time()
    for b in range(0, len(records), EMBED_BATCH):
        batch = [r["text"] for r in records[b : b + EMBED_BATCH]]
        vectors.extend(embed_texts(batch))
        done = min(b + EMBED_BATCH, len(records))
        print(f"  embedded {done}/{len(records)}", end="\r")
    print()

    arr = np.array(vectors, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    arr = arr / norms  # normalize so cosine == dot product

    os.makedirs(INDEX_DIR, exist_ok=True)
    np.save(os.path.join(INDEX_DIR, "embeddings.npy"), arr)
    with open(os.path.join(INDEX_DIR, "chunks.json"), "w") as f:
        json.dump(records, f)
    with open(os.path.join(INDEX_DIR, "index_meta.json"), "w") as f:
        json.dump(
            {
                "version": INDEX_VERSION,
                "chunks": len(records),
                "audits": len(set(r["source"] for r in records)),
                "has_pages": True,
            },
            f,
        )

    dt = int(time.time() - t0)
    n_sources = len(set(r["source"] for r in records))
    print(f"Done in {dt}s. Index saved to {INDEX_DIR}")
    print(f"  embeddings.npy shape: {arr.shape}")
    print(f"  chunks indexed:       {len(records)}")
    print(f"  audits indexed:       {n_sources}")
    print(f"  page citations:       enabled (index v{INDEX_VERSION})")


if __name__ == "__main__":
    main()
