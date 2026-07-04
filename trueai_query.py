#!/usr/bin/env python3
"""
TrueAI query — asks a question grounded in a chosen RAG index (default: the
TrueAI library index that includes Besu, Solidity, Foundry, OpenZeppelin and
security/multisig guides, plus the FME L1 architecture doc and audit corpus).
Prints the sources it used so answers are verifiable.
Invoke with the venv python (needs numpy):
  /opt/ai-temp/slither-env/bin/python3 trueai_query.py "question" [--model trueai] [--index DIR] [--k 8]
"""
import os, sys, json, argparse, numpy as np, requests

OLLAMA = "http://127.0.0.1:11434"
EMBED_MODEL = "nomic-embed-text"
DEFAULT_INDEX = "/opt/ai-temp/rag/index-library"

SYSTEM = (
    "You are TrueAI, built by George at FME, Inc., running on ai.truel1.com. "
    "You are a blockchain and tokenomics assistant specializing in Hyperledger Besu "
    "Layer 1, Solidity, token deployment, and security (multisig, timelocks, safe "
    "patterns). Answer the question using the provided reference excerpts. Ground your "
    "answer in them and cite the source labels you used. Favor safe patterns: multisig "
    "(Gnosis Safe) for admin/owner roles, TimelockController for privileged operations, "
    "role separation, and audit-before-deploy. If the excerpts do not contain enough to "
    "answer, say so and suggest the customer consult the FME team. Never output real "
    "private keys. Be clear and practical for non-experts."
)

def embed_one(text):
    r = requests.post(f"{OLLAMA}/api/embed",
                      json={"model": EMBED_MODEL, "input": [text]}, timeout=120)
    r.raise_for_status()
    return np.array(r.json()["embeddings"][0], dtype=np.float32)

def load_index(index_dir):
    emb = np.load(os.path.join(index_dir, "embeddings.npy"))
    data = json.load(open(os.path.join(index_dir, "chunks.json")))
    chunks = data["chunks"]
    meta = data.get("meta", [""] * len(chunks))
    return emb, chunks, meta

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--model", default="trueai")
    ap.add_argument("--index", default=DEFAULT_INDEX)
    ap.add_argument("--k", type=int, default=8)
    args = ap.parse_args()

    if not os.path.exists(os.path.join(args.index, "embeddings.npy")):
        print(f"No index at {args.index}. Run rag_ingest_library.py first.")
        sys.exit(1)

    emb, chunks, meta = load_index(args.index)
    print(f"Index: {len(chunks)} chunks. Retrieving top {args.k}...")
    q = embed_one(args.question)
    # cosine similarity
    denom = (np.linalg.norm(emb, axis=1) * np.linalg.norm(q) + 1e-8)
    sims = emb @ q / denom
    top = np.argsort(-sims)[:args.k]

    srcs = []
    ctx = []
    for i in top:
        lbl = meta[i] if i < len(meta) else "?"
        srcs.append(lbl)
        ctx.append(f"[source: {lbl}]\n{chunks[i]}")
    print("Retrieved from:")
    for s in dict.fromkeys(srcs):
        print(f"  - {s}")
    print(f"Asking {args.model} (grounded in the excerpts above)...\n")
    print("=" * 64)

    prompt = (f"Reference excerpts:\n\n" + "\n\n---\n\n".join(ctx) +
              f"\n\nQuestion: {args.question}")
    r = requests.post(f"{OLLAMA}/api/generate",
                      json={"model": args.model, "system": SYSTEM,
                            "prompt": prompt, "stream": False},
                      timeout=600)
    r.raise_for_status()
    out = r.json()
    # deepseek-r1 style returns thinking + response; print response
    print(out.get("response", "").strip())
    print("=" * 64)
    print("\nSources used (verify these):")
    for s in dict.fromkeys(srcs):
        print(f"  - {s}")
    print("\nTrueAI — built by George at FME, Inc. · ai.truel1.com · guidance, not a certified audit.")

if __name__ == "__main__":
    main()
