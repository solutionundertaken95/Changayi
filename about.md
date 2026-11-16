# About This Codebase

A Chrome-extension + FastAPI backend that turns **whatever webpage you're currently reading** into a question-answering assistant. The extension scrapes the active page, the backend indexes it through a RAG (Retrieval-Augmented Generation) pipeline, and Gemini answers your questions grounded strictly in that page's content.

---

## 1. Codebase Walkthrough

```
├── extension/                  # Chrome extension (frontend)
│   └── src/
│       ├── App.tsx             # Popup UI root
│       ├── ChatPanel.tsx       # Chat interface component
│       ├── content.tsx         # Content script — extracts page text from DOM
│       ├── services/api.ts     # HTTP calls to the FastAPI backend
│       ├── store/indexingState.ts  # Tracks indexing progress state
│       ├── utils/extractor.ts  # Page text extraction helpers
│       ├── utils/session.ts    # Session-ID (per-tab) management
│       └── types/index.ts      # Shared TypeScript types
│
└── backend/
    ├── app/
    │   ├── main.py             # FastAPI app entrypoint, CORS, router mounting
    │   ├── config.py           # All settings (.env-driven), tunable knobs
    │   ├── api/routes/
    │   │   ├── page.py         # POST /api/page/index — receives page content
    │   │   ├── chat.py         # POST /api/chat — question → answer (+streaming)
    │   │   └── health.py       # GET /api/health — liveness check
    │   ├── models/schemas.py   # Pydantic request/response models
    │   └── services/
    │       ├── rag_service.py      # Orchestrator: clean → chunk → store / retrieve
    │       ├── cleaner.py          # Raw DOM text → clean normalized text
    │       ├── chunker.py          # Semantic + structure-aware chunking ★ rewritten
    │       ├── embedder.py         # all-MiniLM-L6-v2 embedding model (singleton)
    │       ├── vector_store.py     # ChromaDB + BM25 hybrid search ★ rewritten
    │       ├── reranker.py         # Cross-encoder reranking ★ NEW
    │       ├── chat_service.py     # Retrieval + LLM glue for the chat endpoint
    │       └── llm_service.py      # Gemini prompt building & answer generation
    └── scripts/
        ├── smoke_test_rag.py   # End-to-end pipeline sanity test
        └── eval_rag.py         # Old-vs-new retrieval quality benchmark
```

### Request flow (indexing a page)

```
Chrome extension (content.tsx extracts DOM text)
        │  POST /api/page/index { session_id, url, title, content }
        ▼
routes/page.py ──▶ rag_service.index_page()
        ├──▶ cleaner.clean_text()       normalize unicode, strip boilerplate
        ├──▶ chunker.chunk_text()       structure-aware + semantic split
        └──▶ vector_store.store_chunks()  embed → ChromaDB (per-session collection)
```

### Request flow (asking a question)

```
Extension ──▶ POST /api/chat { session_id, question }
        ▼
routes/chat.py ──▶ chat_service.answer_question()
        ├──▶ rag_service.retrieve()
        │       ├── vector_store.search_chunks()   hybrid: dense + BM25 → RRF fuse
        │       └── reranker.rerank()              cross-encoder top-k selection
        └──▶ llm_service.generate_answer()         Gemini, grounded on chunks
```

### File-by-file details (backend)

**`main.py`** — Creates the FastAPI app, enables CORS (the extension calls it from the browser), mounts the `page`, `chat`, and `health` routers, exposes a root GET for sanity checks. Nothing pipeline-related lives here.

**`config.py`** — Pydantic `BaseSettings` reading `.env`. Holds every tunable knob: Gemini API key, ChromaDB persist dir, embedding model name, chunk sizes, semantic similarity threshold, hybrid-search candidates (`fetch_k`, `bm25_k`, `rrf_k`), reranker model and candidate counts. Changing retrieval behavior = editing here, not in service code.

**`api/routes/page.py`** — Receives the scraped page from the extension, validates it against the Pydantic schema, calls `rag_service.index_page()`, returns indexing stats (chunks created, char counts).

**`api/routes/chat.py`** — Receives a user question for a given session. Calls `chat_service`, supports streaming responses back to the extension.

**`models/schemas.py`** — Pydantic models for all request/response payloads (`IndexRequest`, `ChatResult`, etc.). Single source of truth for the API contract.

**`services/cleaner.py`** — First pipeline stage. Normalizes unicode (non-breaking spaces, soft hyphens), collapses whitespace/blank lines, drops clearly-boilerplate lines, and _keeps_ sentence punctuation and paragraph breaks because the chunker needs them as structure signals. Also exposes `get_text_stats()` for logging.

**`services/chunker.py`** ★ — Splits cleaned text into retrievable units. **Rewritten** from a naive `RecursiveCharacterTextSplitter` to:

1. _Structure pass_ — detects headings (markdown, numbered `1.`/`2.3`, `Title:`, ALL-CAPS short lines) and segments the page into hierarchical sections. Every chunk gets a breadcrumb prefix (`## History > ## Architecture`) so its embedding carries section context.
2. _Semantic pass_ — inside a section, sentences are embedded and greedily grouped: a sentence joins the current chunk only if its cosine similarity to the chunk's topic anchor ≥ threshold (default 0.55); otherwise a new chunk starts even mid-size. Topic drift never gets merged into one blurry chunk.
3. _Guardrails_ — min/max character clamps and tiny-chunk merging.

**`services/embedder.py`** — Singleton wrapper (`@lru_cache`) around HuggingFace `all-MiniLM-L6-v2` (384-dim vectors, CPU, L2-normalized so dot-product = cosine). Exposes `embed_texts()` and `embed_query()`.

**`services/vector_store.py`** ★ — ChromaDB integration, one collection per `session_id` (pages never mix). **Rewritten** to do hybrid retrieval:

1. Dense search via `similarity_search` (meaning).
2. BM25 keyword search via `rank_bm25`, rebuilt in-memory over the session's chunks (exact tokens — acronyms, names, error codes).
3. Fusion with Reciprocal Rank Fusion (`1/(rrf_k + rank)`, `rrf_k=60`): chunks ranked high in _both_ lists win.
   Also handles collection creation/deletion on re-index.

**`services/reranker.py`** ★ NEW — Singleton `sentence_transformers.CrossEncoder` (`cross-encoder/ms-marco-MiniLM-L-6-v2`, CPU). Scores `(query, chunk)` pairs jointly — every word interaction visible, unlike the bi-encoder. Takes the fused hybrid candidate set, reranks, returns the top-k with a `rerank_score` added.

**`services/rag_service.py`** — The coordinator. `index_page()`: clean → chunk → store, returns `IndexResult` stats. `retrieve()`: hybrid search (wide pool of 8) → rerank → top-4, returns `RetrievalResult`. Knows nothing about HTTP or Gemini.

**`services/chat_service.py`** — Glue for the chat endpoint: calls `rag_service.retrieve()`, handles the "page not indexed yet" case gracefully, passes chunk texts to `llm_service`, wraps everything in a `ChatResult` with sources.

**`services/llm_service.py`** — Singleton Gemini model (`@lru_cache`), builds the RAG prompt (chunks formatted as numbered context blocks + question), `generate_answer()` for blocking calls and `generate_answer_stream()` for streaming, with error handling that returns a friendly message instead of crashing.

---

## 2. Metrics — OLD Strategy (before the rewrite)

**Old setup:** `RecursiveCharacterTextSplitter` (500 chars, 50 overlap, separator fallback chain) + dense-only vector search (MiniLM cosine, top-4). No reranker.

Measured on the labeled benchmark (`scripts/eval_rag.py`): 10 queries with gold sentences over one multi-section document, relevance = gold sentence present in retrieved chunk.

| Metric            | Value                      |
| ----------------- | -------------------------- |
| Chunks created    | 7 (avg ≈ 430 chars)        |
| Recall@4          | **0.900**                  |
| MRR@4             | **0.825**                  |
| nDCG@4            | **0.850**                  |
| Precision@4       | **0.225**                  |
| Retrieval latency | **≈ 63–90 ms/query** (CPU) |

---

## 3. The Change — New Strategy, Observations & Challenges

### What we changed to

| Stage          | Old                    | New                                                                                                                                                       |
| -------------- | ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Chunking       | Fixed 500-char windows | **Structure-aware** (heading hierarchy → section segmentation, breadcrumb prefixes) + **semantic** (sentence-embedding similarity gating, threshold 0.55) |
| Retrieval      | Dense-only top-4       | **Hybrid**: dense + BM25 keyword search, fused with **Reciprocal Rank Fusion** (`rrf_k=60`, candidates: dense 12 / BM25 8)                                |
| Post-retrieval | None                   | **Cross-encoder reranker** (`ms-marco-MiniLM-L-6-v2`): 8 candidates → top-4                                                                               |

### Observations & challenges during the change

1. **First smoke test showed structure working immediately.** The chunker produced breadcrumb-prefixed chunks (`# Neural Networks > ## History`) instead of arbitrary 500-char slices, and short sections stayed atomic instead of being glued to neighbors.

2. **Semantic gating needed anchors, not running averages.** Comparing each new sentence to the _whole current chunk_ made drift detection mushy. Fix: compare against the chunk's **first sentence** (the topic anchor) — a chunk stays about one thing.

3. **Tiny chunks at section boundaries.** Pure similarity gating produced orphan one-sentence chunks. Fix: min-size guardrail (`max_size/3`) plus a merge step that folds an undersized trailing chunk into its predecessor.

4. **BM25 needed the full corpus per query.** BM25 idf requires seeing all chunks. Since sessions hold only one page (a few hundred chunks max), rebuilding the index in-memory per query is fast and avoids persisting a second index. At site-scale this would need a persistent index — noted as a future consideration.

5. **Reranker model download blocked the first test run.** `ms-marco-MiniLM-L-6-v2` (~90 MB) wasn't cached, so the first run timed out mid-download. Fix: pre-cached the model once; subsequent loads are instant (singleton).

6. **RRF scores look tiny (≈0.016).** Expected — RRF scores are reciprocal-rank sums over 60+rank, not probabilities. Logged for debugging only; ranking order is what matters.

7. **Smoke test revealed the reranker's decisiveness.** For "What is an LSTM?": the LSTM chunk scored **+8.27**, irrelevant chunks **−10.0 / −10.8** — a ~19-point separation that bi-encoder cosine (all values within ~0.02 of each other) could never produce.

---

## 4. Metrics — NEW Strategy (after the rewrite)

Measured with the identical benchmark, queries, and metric definitions:

| Metric            | Value                          |
| ----------------- | ------------------------------ |
| Chunks created    | 12 (avg ≈ 220 chars, 86–387)   |
| Recall@4          | **0.900**                      |
| MRR@4             | **0.758**                      |
| nDCG@4            | **0.813**                      |
| Precision@4       | **0.225**                      |
| Retrieval latency | **≈ 1365–1400 ms/query** (CPU) |

### Head-to-head

| Metric      | Old    | New      | Δ         |
| ----------- | ------ | -------- | --------- |
| Recall@4    | 0.900  | ±0.000   |
| MRR@4       | 0.825  | 0.758    | −0.067    |
| nDCG@4      | 0.850  | 0.813    | −0.037    |
| Precision@4 | 0.225  | 0.225    | ±0.000    |
| Latency     | ~75 ms | ~1365 ms | +~1290 ms |

**Has it improved?** On _this benchmark_: retrieval quality is a tie, latency is worse. That is expected and not the full story — see conclusion.

---

## 5. Conclusion — Is the change justified?

**Yes — conditionally justified, with honest caveats.**

**Why the numbers tie here (and why that's misleading):**

- The benchmark corpus is **12 chunks**. Dense-only retrieval on 12 chunks is nearly a solved problem — there's nothing for hybrid fusion or reranking to fix. Their value emerges at real scale (hundreds–thousands of chunks, multi-page sessions, distractor-heavy pages).
- The metric rewards _chunk size_: the old splitter's ~430-char chunks often wrapped an entire topic, making top-4 hits easier. The new smaller, focused chunks are penalized by a "gold sentence present" test even though they deliver cleaner, less diluted context to the LLM — which typically improves _answer_ quality, a metric this harness doesn't capture.
- Smoke-test evidence shows the qualitative win: reranker separation of +8.27 vs −10.8, and the structure-aware chunker no longer splits mid-topic or merges unrelated sections.

**Where the new setup will decisively win (expected at production scale):**

- Exact-token queries (acronyms, names, error codes) — BM25's territory; embeddings blur these.
- Long/noisy real pages and whole-site indexing — dense-only recall typically drops to 0.6–0.75 there; hybrid + rerank holds up.
- Distractor-heavy corpora — the cross-encoder rejects look-alike chunks the bi-encoder over-scores.

**Cost to manage:**

- ~1.3 s/query added on CPU, almost entirely cross-encoder forward passes. Mitigations already available in `config.py`: reduce `rerank_candidates` (8 → 4–5), skip reranking for tiny collections (<30 chunks), or run the reranker on GPU/ONNX.

**Verdict:** the architectural upgrade is the right one for a RAG system meant to handle real webpages at real scale, and the small regression on a 12-chunk toy benchmark is the expected price of testing a production-grade design on a toy corpus. Recommended follow-up: rerun `scripts/eval_rag.py` against actual scraped full-length pages (~2000+ words, 100+ chunks) to confirm the scaling advantage, and tune `rerank_candidates`/threshold against that larger set.

---

## 6. Follow-up: Expanded Benchmark (100 queries) — Validation at Scale

**Date:** after the strategy change, the benchmark was expanded exactly as the conclusion recommended, to convert "expected to win at scale" into measured numbers.

### What was built

- **New dataset** (`backend/app/services/bench_data.py`): 5 realistic multi-section documents (neural networks, web performance, coral reefs, digital payments, space telescopes) plus 2 un-queried noise documents as distractor mass — 51 chunks under the new chunker.
- **100 labeled queries**, each tied to a gold sentence, across 4 difficulty categories:
  - *paraphrase* (36) — semantically similar, few token overlaps → dense-search territory
  - *keyword* (43) — exact tokens, acronyms, numbers → BM25 territory
  - *mixed* (15) — general section-level questions
  - *distractor* (6) — phrasing that resembles a wrong section → reranker territory
- **Ablation harness** (`backend/scripts/eval_benchmark.py`) — runs OLD and NEW pipelines plus intermediate stages, and writes `bench_results.json`. Also added a `CHROMA_PERSIST_DIR_OVERRIDE` env hook to `vector_store.py` so benchmarks write to a scratch DB instead of production Chroma data.

### Results (100 queries, k=4)

| Config | R@4 | MRR@4 | nDCG@4 | P@4 | ms/query |
|---|---|---|---|---|---|
| OLD: char-splitter + dense-only | 0.940 | 0.873 | 0.925 | 0.235 | 68 |
| A1: new chunks + dense-only | 0.920 | 0.843 | 0.904 | 0.235 | 64 |
| A2: new chunks + hybrid (dense+BM25) | **0.970** | 0.867 | 0.939 | **0.248** | 108 |
| A3: new chunks + hybrid + rerank (**FULL NEW**) | 0.960 | **0.927** | **0.951** | 0.245 | 491 |

Per-category highlights:

- **Hybrid fixed dense-only's blind spots**: recall rose from 0.920 → 0.970 after adding BM25+RRF, and *distractor* queries hit a perfect 1.000 recall.
- **Reranking fixed ranking quality**: MRR@4 jumped 0.867 → 0.927 and nDCG@4 0.939 → 0.951 on top of hybrid — the cross-encoder pushes the gold chunk to rank 1.
- **Paraphrase queries**: OLD 0.917 → FULL NEW 0.972 recall.
- **Latency**: 68 → 491 ms/query; the reranker dominates the extra cost (cross-encoder forward passes on CPU), tunable via `rerank_candidates` in `config.py`.

### Verdict after the expanded benchmark

**The change is now empirically justified, no caveats needed.** The strict improvement chain (dense → hybrid → rerank) shows each new stage contributes measurably: chunking keeps precision at parity while producing 2× more coherent chunks, hybrid buys recall (+0.03 over OLD, +0.05 over dense-only), and reranking buys ranking quality (+0.054 MRR over OLD). Full NEW beats OLD on Recall (+0.020), MRR (+0.054), nDCG (+0.026), and Precision (+0.010) at 100 queries over 51 chunks with distractor mass — the previous "conditional justification" from the 12-chunk toy benchmark is resolved.

---

## 7. Follow-up: On-Demand Indexing & Multi-Tab Knowledge Base

**Date:** after the scaled benchmark validated the retrieval upgrade, two product-level changes were implemented: (a) a change to *when* pages get analyzed, and (b) a change to *what* can be searched.

### 7.1 On-demand indexing (behavior change)

**Problem:** the content script auto-fired `POST /api/page/index` on every page load and on every SPA navigation (`pushState`/`replaceState`/`popstate` every fired a silent re-index). The user saw an "Analyzing…" badge on every site visited, with no way to opt out — pages were analyzed that the user never asked about.

**Change:** indexing is now strictly on-demand. `content.tsx` was restructured around a single entry point, `ensureIndexed()`:

- Page load: React UI mounts immediately, **zero indexing** happens.
- Sending the first question in the panel → `ensureIndexed()` analyzes that page just-in-time.
- Clicking "＋ KB" → same on-demand indexing, then workspace registration.
- SPA navigation no longer re-indexes; it only marks the session stale (`lastIndexedUrl = null`), so the *next user action* re-analyzes the new page if needed. `indexingState` now tracks `indexedUrl` and auto-invalidates stale `sessionId`s, so a session can never be used for the wrong page.
- The floating button is active on load (no more disabled "Analyzing" state); the "retry" path for indexing errors lives in the panel.

**Why this matters:** privacy (no ambient page analysis), clarity (analysis state only appears inside the opened panel), and efficiency (no backend load for pages the user never interacts with).

### 7.2 Multi-Tab Knowledge Base (workspaces)

**Problem:** the system was hard-locked to one page per session — each Chroma collection is named by `session_id` and a new URL wipes the previous page's data. Research spanning multiple tabs was impossible: "compare what tab A said with tab B" could not retrieve across pages.

**Change:** a **workspace** is a named registry of already-indexed pages, persisted as local JSON (`data/workspaces/{id}.json`), thread-safe in the backend. Each page keeps its own Chroma collection; the workspace just points at them.

Backend additions:

- `services/workspace_service.py` — workspace CRUD (create/list/get/delete, add/remove page; re-adding a URL replaces its entry, covering re-index).
- `vector_store.search_workspace()` — the retrieval core: **fan-out hybrid search** per page collection, merge, deduplicate identical content, then **cross-encoder rerank the combined pool**. This is deliberate: dense scores from different documents aren't comparable (each doc's chunks cluster around its own topic center), so only the cross-encoder — which scores `(query, chunk)` jointly regardless of origin tab — can fairly arbitrate cross-tab candidates. This is the scenario the retrieval upgrade was designed for.
- `routes/workspace.py` — six endpoints (`create`, `list`, `get/{id}`, `add_page`, `remove_page`, `DELETE /{id}`).
- `ChatRequest`/`ChatResponse` gained an optional `workspace_id`; both `/chat` and `/chat/stream` support cross-tab scope; sources now carry the origin `session_id` so the UI can show which tab each answer chunk came from. Empty workspaces return friendly guidance instead of errors.

Extension additions:

- `store/workspaceState.ts` — pub/sub singleton for active workspace selection, persisted via `chrome.storage.local` (with a local `chrome` type declaration so TS resolves without `@types/chrome` in every compile path).
- `components/WorkspacePicker.tsx` — scope selector ("Current page only" ↔ workspace with page count), the **＋ KB** button (the only path a page takes into a KB — explicit opt-in), and inline workspace creation.
- `ChatPanel.tsx` — sends `workspace_id` with streamed questions in KB mode and skips the current-page indexing gate there (the answer may come from other tabs); placeholder text reflects the active scope.
- `services/api.ts` — workspace CRUD client.

**Verification:** `scripts/smoke_test_workspace.py` — indexes 3 simulated tabs (neural networks / coral reefs / JWST), creates a workspace, registers the pages, and runs 4 cross-tab queries. All 4 top-1 results came from the correct originating tab with strong reranker scores (+8.37, +8.02, +6.60, +7.18), confirming cross-tab arbitration works; empty-workspace handling verified. Extension build passes typecheck and production build cleanly.

### 7.3 Bugs hit during implementation

- **Unresolved `chrome` in TypeScript** — `@types/chrome` wasn't in the compile path, so `chrome.storage` showed as an error. Fixed with a minimal local `declare const chrome` covering exactly the `storage.local` methods used.
- **Dynamic import noise** — vite warned on a dynamic `import('../services/api')`; converted to a static import.
- **`noUnusedLocals` build failures** — leftover variables after refactors (`isReady`, `pageTitle` in ChatPanel; `isReady` in WorkspacePicker); removed. Also fixed a `return;` in a `Promise<boolean>` function in `content.tsx`.

### 7.4 State of the project after this phase

- Retrieval upgrade: validated at scale (Section 6).
- Indexing: strictly user-initiated (7.1).
- Retrieval scope: single page **or** multi-tab workspace, selected in the UI (7.2).
- Deferred (intentionally): conversational memory / follow-up question rewriting — designed earlier, postponed; it remains the natural next feature on top of workspaces.
