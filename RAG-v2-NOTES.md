# TrueL1 External Audit Reference RAG — v2 notes

**What this is:** a retrieval tool over 415 public third-party audit PDFs that
helps a human reviewer find precedent fast. It does **not** train a model on
those audits, it does **not** produce audits, and it is **not** a substitute
for a professional audit. Frame it that way wherever it's referenced.

## What changed in v2 (mapped to the agreed list)

1. **Exact / single-audit source filtering** — `--source` still matches by
   substring; `--exact` now requires it to resolve to exactly one filename and
   errors with candidates otherwise. `rag-list [term]` shows what's indexed
   (with chunk counts) so you can pick the right name. *(query-side, no re-index)*

2. **Page-number citations** — every answer cites `[file.pdf, p.N]`, and the
   source list aggregates to `file.pdf (pp. 2, 3, 5)`. This is the **only**
   change that needs a rebuild: ingest now chunks page-by-page and stores a
   `page` on each chunk. Until you run `rag-build`, v2 runs on your current
   index and simply omits `p.N`. *(index-side, one re-embed ≈ 100s)*

3. **No-evidence threshold** — `--min-score X` abstains (no model call, no
   answer) when the best retrieval score is below `X`. **Default is 0 (off)**
   deliberately — calibrate first with `rag-scores "query"`, which prints
   cosine scores without calling the model, then pick a floor. *(query-side)*

4. **Separate venv** — provided as `setup-rag-venv.sh`, **marked deferred / do
   not run** (it installs packages). The PDF step stays pinned to slither-env
   inside `rag_query.py`, so only the RAG scripts move envs. *(deferred)*

5. **Two-tier models** — default `qwen2.5-coder:32b` for fast reference; add
   `--model deepseek-r1:70b` for deeper review. Note: passing a custom model
   still overrides its Modelfile SYSTEM with the RAG prompt below, so
   `truel1-sm-audit-v2` in RAG mode behaves as "Qwen-with-more-brain + RAG
   discipline." If you want it to differ, bake the RAG discipline into its
   Modelfile. *(query-side)*

6. **Pin to a commit SHA** — `deploy-rag-v2.sh` downloads from one specific
   commit (not `main`) and verifies each file's sha256 before installing.
   Reference hashes are pre-filled; you supply the commit SHA. *(process)*

**Plus the root-cause fix — interpretation fidelity.** The honeypot error
wasn't bad retrieval; the model flipped "can *not* become a honeypot" (a pass)
into a HIGH-RISK finding. The v2 system prompt now requires the model to quote
the exact source sentence and its stated status verbatim *before* interpreting,
and to preserve negations. Paired with page citations, a misread is obvious at
a glance.

## Reference hashes (sha256 of the v2 files)

```
rag_ingest.py     abe67cc6e0e3d5e72f9d806be254479c9a2a7e245df1b19e58698ca7ab2b1386
rag_query.py      7754518b095f9b86335ebc2cf48ef2b07030c900c5a43b84f53b33f212bce77c
rag-shortcuts.sh  7983b490a3e34ead1e40ab27f9b898748d79c6ebb884046695ea8069c112f2f0
```

(If your editor or GitHub rewrites line endings on upload, the hashes won't
match — upload the files unchanged; `raw.githubusercontent.com` serves the
exact committed bytes.)

## Deploy procedure (when you're ready — nothing here runs now)

1. Review `rag-v2.diff` (full unified diff vs what's on the server).
2. Upload the three `.py`/`.sh` files to `aungbu/ayet-token`, commit, copy the
   40-char commit SHA.
3. Put that SHA in `deploy-rag-v2.sh`, confirm the hashes above, review, run it.
4. Reload: `source /opt/ai-temp/rag/rag-shortcuts.sh`.
5. Optional, when you want page cites: `rag-build` (re-embeds ~6.3k chunks,
   ~100s, GPU only, does not touch Besu).

## New/changed commands

```
rag-list                       # list all indexed audits + chunk counts
rag-list AKIMOTO               # filter that list
rag-ask "q" --source NAME --exact   # one audit, loaded in full (no top-k loss)
rag-ask "q" --min-score 0.30   # abstain if weakly matched
rag-scores "q"                 # print retrieval scores only (calibration)
rag-ask "q" --model deepseek-r1:70b --pdf --title "Deep Review"
```

## Calibrating `--min-score`

Run `rag-scores` on a few real questions and a few nonsense ones. Real,
on-topic queries should score noticeably higher than gibberish; set the floor
in the gap between them. Start conservative (a low floor) so you don't get
false refusals, then tighten if confabulation slips through.
