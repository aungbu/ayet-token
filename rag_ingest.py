#!/usr/bin/env python3
"""
TrueL1 RAG Ingest
-----------------
Reads every Coinsult audit PDF, extracts its text, splits it into overlapping
chunks, embeds each chunk with nomic-embed-text via the local Ollama API, and
saves a searchable NumPy index. No vector database, no running service - just
two files on disk. Re-run this any time you add new PDFs to the source folder.
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


def extract_text(path):
    try:
        doc = fitz.open(path)
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return text.strip()
    except Exception as e:
        print(f"  ! extract failed for {os.path.basename(path)}: {e}")
        return ""


def chunk_text(text):
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

    print(f"Found {len(pdfs)} PDFs. Extracting text + chunking...")
    records = []
    skipped = 0
    for i, path in enumerate(pdfs, 1):
        text = extract_text(path)
        if not text:
            skipped += 1
            continue
        tok = token_name(path)
        for j, c in enumerate(chunk_text(text)):
            records.append(
                {"text": c, "source": os.path.basename(path), "token": tok, "idx": j}
            )
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

    dt = int(time.time() - t0)
    n_sources = len(set(r["source"] for r in records))
    print(f"Done in {dt}s. Index saved to {INDEX_DIR}")
    print(f"  embeddings.npy shape: {arr.shape}")
    print(f"  chunks indexed:       {len(records)}")
    print(f"  audits indexed:       {n_sources}")


if __name__ == "__main__":
    main()
