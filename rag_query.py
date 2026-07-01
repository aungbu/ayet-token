#!/usr/bin/env python3
"""
TrueL1 RAG Query
----------------
Answers a question using ONLY the indexed Coinsult audit excerpts. Embeds your
question, finds the most similar chunks by cosine similarity, and feeds them to
a local Ollama model as grounded context. Prints which audits it drew from so
you can verify (and so the model isn't hallucinating).
"""
import os
import sys
import json
import argparse
import subprocess
import datetime

import numpy as np
import requests

OLLAMA = "http://127.0.0.1:11434"
EMBED_MODEL = "nomic-embed-text"
INDEX_DIR = "/opt/ai-temp/rag/index"
REPORTS_DIR = "/opt/ai-temp/reports"
MDPDF = "/opt/ai-temp/md-to-pdf.py"
PYBIN = "/opt/ai-temp/slither-env/bin/python3"

SYSTEM = (
    "You are a senior smart-contract security auditor. Answer the question using "
    "ONLY the audit excerpts provided by the user. Ground every claim in those "
    "excerpts and cite the source audit filenames you used. If the excerpts do "
    "not contain enough information to answer, say so plainly instead of guessing."
)


def embed_one(text):
    try:
        r = requests.post(
            f"{OLLAMA}/api/embed",
            json={"model": EMBED_MODEL, "input": [text]},
            timeout=120,
        )
        r.raise_for_status()
        embs = r.json().get("embeddings")
        if embs:
            return np.array(embs[0], dtype=np.float32)
    except Exception:
        pass
    r = requests.post(
        f"{OLLAMA}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=120,
    )
    r.raise_for_status()
    return np.array(r.json()["embedding"], dtype=np.float32)


def load_index():
    emb_path = os.path.join(INDEX_DIR, "embeddings.npy")
    chunk_path = os.path.join(INDEX_DIR, "chunks.json")
    if not (os.path.exists(emb_path) and os.path.exists(chunk_path)):
        print(f"No index in {INDEX_DIR}. Run rag_ingest.py (rag-build) first.")
        sys.exit(1)
    emb = np.load(emb_path)
    with open(chunk_path) as f:
        chunks = json.load(f)
    return emb, chunks


def retrieve(question, emb, chunks, k):
    q = embed_one(question)
    n = np.linalg.norm(q) or 1.0
    q = q / n
    sims = emb @ q
    top = np.argsort(-sims)[:k]
    return [(chunks[i], float(sims[i])) for i in top]


def generate(model, question, context):
    prompt = f"=== AUDIT EXCERPTS ===\n{context}\n\n=== QUESTION ===\n{question}"
    payload = {"model": model, "system": SYSTEM, "prompt": prompt, "stream": False}
    r = requests.post(f"{OLLAMA}/api/generate", json=payload, timeout=1800)
    r.raise_for_status()
    return r.json().get("response", "").strip()


def make_pdf(title, question, model, answer, sources):
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    safe = "".join(c if c.isalnum() else "-" for c in title.lower()).strip("-")
    mdfile = f"/tmp/{safe}-{ts}.md"
    pdfout = f"{REPORTS_DIR}/{safe}-{ts}.pdf"
    md = (
        f"# {title}\n\n**Question:** {question}\n\n**Model:** {model}\n\n---\n\n"
        f"{answer}\n\n---\n\n## Sources Retrieved\n\n"
        + "\n".join(f"- {s}" for s in sources)
    )
    with open(mdfile, "w") as f:
        f.write(md)
    subprocess.run(
        [PYBIN, MDPDF, mdfile, "--title", title, "--subtitle",
         "RAG Audit Query", "--model", model, "--output", pdfout]
    )
    if os.path.exists(mdfile):
        os.remove(mdfile)
    return pdfout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--model", default="qwen2.5-coder:32b",
                    help="generation model (use deepseek-r1:70b for deeper analysis)")
    ap.add_argument("--k", type=int, default=6, help="number of excerpts to retrieve")
    ap.add_argument("--pdf", action="store_true", help="also save a PDF report")
    ap.add_argument("--title", default="Audit Knowledge Query")
    args = ap.parse_args()

    emb, chunks = load_index()
    n_sources = len(set(c["source"] for c in chunks))
    print(f"Index: {len(chunks)} chunks from {n_sources} audits.")
    print(f"Retrieving top {args.k} excerpts...")
    hits = retrieve(args.question, emb, chunks, args.k)

    context_parts, sources = [], []
    for ch, score in hits:
        context_parts.append(f"[Source: {ch['source']} | {ch['token']}]\n{ch['text']}")
        if ch["source"] not in sources:
            sources.append(ch["source"])
    context = "\n\n".join(context_parts)

    print("Retrieved from:")
    for s in sources:
        print(f"  - {s}")
    print(f"Asking {args.model} (grounded in the excerpts above)...")
    answer = generate(args.model, args.question, context)

    print("\n" + "=" * 64)
    print(answer)
    print("=" * 64)
    print("\nSources used (verify these):")
    for s in sources:
        print(f"  - {s}")

    if args.pdf:
        pdfout = make_pdf(args.title, args.question, args.model, answer, sources)
        if os.path.exists(pdfout):
            print(f"\nPDF:  {pdfout}")
            print(f"View: http://l1.aucfans.com:3003/{os.path.basename(pdfout)}")


if __name__ == "__main__":
    main()
