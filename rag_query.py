#!/usr/bin/env python3
"""
TrueL1 External Audit Reference RAG - Query  (v2)
-------------------------------------------------
Answers questions using ONLY the indexed EXTERNAL audit excerpts. This is a
REFERENCE tool over public third-party audit reports - it does not train a
model, it is not a trained auditor, and it is not a substitute for a
professional audit.

v2 changes:
  * exact / single-audit source filtering        (--source, --exact)
  * whole-audit loading when scope is one report  (no lossy top-k drop)
  * abstain threshold: weak retrieval returns nothing, not a guess (--min-score)
  * page-number citations  [file.pdf, p.N]        (when the index has page data)
  * interpretation-fidelity prompt: quote the source line + status verbatim
    before interpreting, preserving negations like "can NOT become a honeypot"
  * inspection helpers: --list, --show-scores, --scores-only
"""
import os
import sys
import json
import argparse
import subprocess
import datetime
from collections import defaultdict

import numpy as np
import requests

OLLAMA = "http://127.0.0.1:11434"
EMBED_MODEL = "nomic-embed-text"
INDEX_DIR = "/opt/ai-temp/rag/index"
REPORTS_DIR = "/opt/ai-temp/reports"
MDPDF = "/opt/ai-temp/md-to-pdf.py"
PYBIN = "/opt/ai-temp/slither-env/bin/python3"  # WeasyPrint lives here; keep for PDF

SYSTEM = (
    "You are a research assistant helping a human auditor review EXTERNAL "
    "third-party audit reports. Use ONLY the audit excerpts provided by the "
    "user. Follow these rules exactly:\n"
    "1. For every finding or claim, FIRST quote the exact sentence from the "
    "excerpts (in quotation marks) together with its stated status or severity "
    "verbatim, THEN give your interpretation. Never paraphrase a severity.\n"
    "2. Preserve negations precisely. If the source says a check 'can not' or "
    "'cannot' happen (e.g. 'Contract can not become a honeypot'), that is a "
    "PASS - do not report it as a risk.\n"
    "3. Cite each point as [filename, p.N] using the page number shown in the "
    "excerpt header. If no page is shown, cite [filename].\n"
    "4. If the excerpts do not contain enough information, say so plainly. Do "
    "not use outside knowledge and do not guess.\n"
    "You are summarizing someone else's audit, not certifying the contract."
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
    has_pages = any("page" in c for c in chunks[:50])
    return emb, chunks, has_pages


def cite(ch, has_pages):
    if has_pages and "page" in ch:
        return f"{ch['source']}, p.{ch['page']}"
    return ch["source"]


def select_indices(chunks, source, exact):
    """Return (indices, distinct_sources) after applying the source filter."""
    if not source:
        return list(range(len(chunks))), sorted(set(c["source"] for c in chunks))
    s = source.lower()
    if exact:
        keep = [
            i for i, c in enumerate(chunks)
            if c["source"].lower() == s
            or os.path.splitext(c["source"])[0].lower() == s
        ]
        matched = sorted(set(chunks[i]["source"] for i in keep))
        if len(matched) != 1:
            cand = sorted(set(c["source"] for c in chunks if s in c["source"].lower()))
            print(f"--exact '{source}' matched {len(matched)} audit(s); need exactly 1.")
            if cand:
                print("Candidates (narrow your term):")
                for c in cand[:15]:
                    print(f"  - {c}")
            sys.exit(1)
        return keep, matched
    keep = [i for i, c in enumerate(chunks) if s in c["source"].lower()]
    if not keep:
        print(f"No audits match --source '{source}'. Try: rag-list {source}")
        sys.exit(1)
    matched = sorted(set(chunks[i]["source"] for i in keep))
    return keep, matched


def rank_topk(question, emb, indices, k):
    idxs = np.array(indices)
    q = embed_one(question)
    q = q / (np.linalg.norm(q) or 1.0)
    sims = emb[idxs] @ q
    order = np.argsort(-sims)[:k]
    return [(int(idxs[o]), float(sims[o])) for o in order]


def generate(model, question, context):
    prompt = f"=== AUDIT EXCERPTS ===\n{context}\n\n=== QUESTION ===\n{question}"
    payload = {"model": model, "system": SYSTEM, "prompt": prompt, "stream": False}
    r = requests.post(f"{OLLAMA}/api/generate", json=payload, timeout=1800)
    r.raise_for_status()
    return r.json().get("response", "").strip()


def fmt_sources(chunks, chosen, has_pages):
    """Aggregate chosen chunk indices into 'file (pp. 2, 3, 5)' lines."""
    pages = defaultdict(set)
    order = []
    for i in chosen:
        src = chunks[i]["source"]
        if src not in order:
            order.append(src)
        if has_pages and "page" in chunks[i]:
            pages[src].add(chunks[i]["page"])
    lines = []
    for src in order:
        ps = sorted(pages[src])
        lines.append(f"{src} (pp. {', '.join(str(p) for p in ps)})" if ps else src)
    return lines


def make_pdf(title, question, model, answer, src_lines):
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    safe = "".join(c if c.isalnum() else "-" for c in title.lower()).strip("-")
    mdfile = f"/tmp/{safe}-{ts}.md"
    pdfout = f"{REPORTS_DIR}/{safe}-{ts}.pdf"
    srcs = "\n".join(f"- {s}" for s in src_lines)
    md = (
        f"# {title}\n\n**Question:** {question}\n\n**Model:** {model}\n\n"
        f"*Reference over external third-party audit reports - not a "
        f"professional audit.*\n\n---\n\n{answer}\n\n---\n\n"
        f"## Sources Retrieved\n\n{srcs}"
    )
    with open(mdfile, "w") as f:
        f.write(md)
    subprocess.run(
        [PYBIN, MDPDF, mdfile, "--title", title, "--subtitle",
         "External Audit Reference (RAG)", "--model", model, "--output", pdfout]
    )
    if os.path.exists(mdfile):
        os.remove(mdfile)
    return pdfout


def do_list(chunks, term):
    counts = defaultdict(int)
    for c in chunks:
        counts[c["source"]] += 1
    items = sorted(counts.items())
    if term:
        t = term.lower()
        items = [(s, n) for s, n in items if t in s.lower()]
    header = f"{len(items)} audit(s)" + (f" matching '{term}'" if term else "")
    print(header + ":")
    for s, n in items:
        print(f"  {n:4d} chunks  {s}")


def main():
    ap = argparse.ArgumentParser(
        description="Query the external audit reference index (RAG v2).")
    ap.add_argument("question", nargs="?", default=None)
    ap.add_argument("--model", default="qwen2.5-coder:32b",
                    help="generation model (deepseek-r1:70b for deeper review)")
    ap.add_argument("--k", type=int, default=6,
                    help="excerpts to retrieve when scope spans multiple audits")
    ap.add_argument("--source", default=None,
                    help="restrict to audits whose filename contains this substring")
    ap.add_argument("--exact", action="store_true",
                    help="require --source to resolve to exactly one audit filename")
    ap.add_argument("--max-chunks", type=int, default=40,
                    help="cap when loading a whole single audit (default 40)")
    ap.add_argument("--min-score", type=float, default=0.0,
                    help="abstain if best retrieval score < this (0=off; calibrate "
                         "with rag-scores before enabling)")
    ap.add_argument("--show-scores", action="store_true",
                    help="print retrieval scores alongside the answer")
    ap.add_argument("--scores-only", action="store_true",
                    help="print retrieval scores and exit WITHOUT calling the model")
    ap.add_argument("--list", nargs="?", const="", default=None, metavar="TERM",
                    help="list indexed audits (optionally filtered) and exit")
    ap.add_argument("--pdf", action="store_true", help="also save a PDF report")
    ap.add_argument("--title", default="External Audit Reference Query")
    args = ap.parse_args()

    emb, chunks, has_pages = load_index()

    # --list: inspection only, no model call
    if args.list is not None:
        do_list(chunks, args.list)
        return

    if not args.question:
        ap.error("a question is required (or use --list)")

    n_sources = len(set(c["source"] for c in chunks))
    page_note = "page citations on" if has_pages else "no page data (re-index for p.N)"
    print(f"Index: {len(chunks)} chunks / {n_sources} audits ({page_note}).")

    indices, matched = select_indices(chunks, args.source, args.exact)

    want_scores = args.show_scores or args.scores_only

    if len(matched) == 1:
        # Single audit in scope: load it whole, in reading order. No ranking loss.
        chosen = sorted(indices, key=lambda i: (chunks[i].get("page", 0),
                                                chunks[i].get("idx", 0)))
        capped = len(chosen) > args.max_chunks
        if capped:
            chosen = chosen[: args.max_chunks]
        print(f"Scope: single audit '{matched[0]}' -> loading {len(chosen)} "
              f"chunk(s) in full" + (" (capped)" if capped else "") + ".")
        if want_scores:
            print("Single-audit scope: no ranking scores; chunks in reading order:")
            for i in chosen:
                print(f"  {cite(chunks[i], has_pages)}")
        if args.scores_only:
            return
    else:
        scope = "all audits" if not args.source else f"{len(matched)} audits"
        print(f"Scope: {scope} -> retrieving top {args.k} excerpt(s).")
        ranked = rank_topk(args.question, emb, indices, args.k)
        if want_scores:
            print("Retrieval scores (cosine):")
            for i, sc in ranked:
                print(f"  {sc:.3f}  {cite(chunks[i], has_pages)}")
        if args.scores_only:
            return
        best = ranked[0][1] if ranked else 0.0
        if args.min_score > 0 and best < args.min_score:
            print(f"\nBest retrieval score {best:.3f} < --min-score "
                  f"{args.min_score:.3f}. Nothing clears the relevance threshold, "
                  f"so not answering (no evidence, no claim).")
            return
        chosen = [i for i, _ in ranked]

    context = "\n\n".join(
        f"[Source: {cite(chunks[i], has_pages)} | {chunks[i]['token']}]\n{chunks[i]['text']}"
        for i in chosen
    )
    src_lines = fmt_sources(chunks, chosen, has_pages)

    print("Grounded in:")
    for s in src_lines:
        print(f"  - {s}")
    print(f"Asking {args.model}...")
    answer = generate(args.model, args.question, context)

    print("\n" + "=" * 64)
    print(answer)
    print("=" * 64)
    print("\nSources used (verify these):")
    for s in src_lines:
        print(f"  - {s}")

    if args.pdf:
        pdfout = make_pdf(args.title, args.question, args.model, answer, src_lines)
        if os.path.exists(pdfout):
            print(f"\nPDF:  {pdfout}")
            print(f"View: http://l1.aucfans.com:3003/{os.path.basename(pdfout)}")


if __name__ == "__main__":
    main()
