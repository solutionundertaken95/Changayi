"""
eval_benchmark.py — Expanded retrieval benchmark (100 queries, 7 docs).

Runs an ablation matrix:
  OLD : char-splitter chunking + dense-only retrieval
  NEW-full : semantic/structure chunking + hybrid (dense+BM25+RRF) + cross-encoder rerank

Ablations on the NEW chunking (to attribute gains to each stage):
  A1: new chunking + dense-only
  A2: new chunking + dense + BM25 (RRF), no rerank
  A3: new chunking + dense + BM25 + rerank   (= NEW-full)

Metrics: Recall@4, MRR@4, nDCG@4, Precision@4, latency. Reported per
category and overall.
"""

import os
import sys
import time
import math
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))
os.environ["CHROMA_PERSIST_DIR_OVERRIDE"] = "./chroma_bench"

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.chunker import chunk_text as new_chunk_text
from app.services.vector_store import search_chunks as _prod_search, _delete_collection
from app.services.reranker import rerank
from app.services.embedder import get_embeddings
from app.services.bench_data import DOCS, EXTRA_CORPUS, QUERIES

CHROMA_DIR = "./chroma_bench"
K = 4

# ------------------------------------------------------------------
# Chunking
# ------------------------------------------------------------------


def old_chunk(text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", ". ", "! ", "? ", ", ", " ", ""],
        length_function=len,
        is_separator_regex=False,
    )
    chunks = splitter.split_text(text)
    return [c.strip() for c in chunks if len(c.strip()) > 30]


def chunk_all(docs: dict[str, str], fn) -> dict[str, list[str]]:
    return {key: fn(text) for key, text in docs.items()}


# ------------------------------------------------------------------
# Retrieval backends
# ------------------------------------------------------------------


def dense_only(_session: str, query: str, k: int) -> list[dict]:
    from langchain_community.vectorstores import Chroma

    vectorstore = Chroma(
        collection_name="bench",
        embedding_function=get_embeddings(),
        persist_directory=CHROMA_DIR,
    )
    docs = vectorstore.similarity_search(query=query, k=k)
    return [{"content": d.page_content, "chunk_index": d.metadata.get("chunk_index", -1)} for d in docs]


def hybrid(_session: str, query: str, k: int) -> list[dict]:
    return _prod_search("bench", query, k=k)


def hybrid_plus_rerank(_session: str, query: str, k: int) -> list[dict]:
    candidates = _prod_search("bench", query, k=8)
    return rerank(query, candidates, top_k=k)


def index(chunks_by_doc: dict[str, list[str]]) -> None:
    all_chunks = []
    for key, chunks in chunks_by_doc.items():
        all_chunks.extend(chunks)
    _delete_collection("bench")
    store_chunks_session("bench", all_chunks)


def store_chunks_session(session: str, chunks: list[str]) -> int:
    """Store all chunks in one collection (cross-doc retrieval)."""
    import chromadb
    from langchain_community.vectorstores import Chroma
    from app.config import settings

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    try:
        client.delete_collection(name=session)
    except Exception:
        pass

    Chroma.from_texts(
        texts=chunks,
        embedding=get_embeddings(),
        metadatas=[{"chunk_index": i, "session_id": session} for i in range(len(chunks))],
        collection_name=session,
        persist_directory=CHROMA_DIR,
    )
    return len(chunks)


# ------------------------------------------------------------------
# Relevance: a chunk is relevant if it contains the gold sentence
# ------------------------------------------------------------------


def build_gold_index(chunks_by_doc: dict[str, list[str]]) -> dict[str, set[int]]:
    """doc_key -> set of global chunk indices containing that doc's text."""
    # We need global indices: chunks from all docs concatenated
    global_chunks: list[tuple[str, int]] = []  # (doc_key, local_idx)
    idx = 0
    layout = {}
    for key, chunks in chunks_by_doc.items():
        layout[key] = (idx, idx + len(chunks))
        idx += len(chunks)
    return layout


def gold_positions(layout: dict, gold_sentence: str, doc_key: str, all_chunks: list[str]) -> set[int]:
    lo, hi = layout[doc_key]
    return {i for i in range(lo, hi) if gold_sentence in all_chunks[i]}


# ------------------------------------------------------------------
# Metrics
# ------------------------------------------------------------------


def metrics_for_run(queries, retrieval_fn, layout, all_chunks):
    recalls, mrrs, ndcgs, precs = [], [], [], []
    latencies = []
    per_category = {}

    for query, gold, doc_key, category in queries:
        relevant = gold_positions(layout, gold, doc_key, all_chunks)
        t0 = time.perf_counter()
        results = retrieval_fn("bench", query, K)
        latencies.append((time.perf_counter() - t0) * 1000)

        rel = [1 if r["chunk_index"] in relevant else 0 for r in results]

        hit = sum(rel)
        recalls.append(hit / len(relevant) if relevant else 0)

        mrr = 0.0
        for rank, r in enumerate(rel, 1):
            if r:
                mrr = 1.0 / rank
                break
        mrrs.append(mrr)

        dcg = sum(r / (1 if i == 0 else math.log2(i + 1)) for i, r in enumerate(rel))
        ideal = sorted(rel, reverse=True)
        idcg = sum(r / (1 if i == 0 else math.log2(i + 1)) for i, r in enumerate(ideal))
        ndcgs.append(dcg / idcg if idcg else 0)
        precs.append(sum(rel) / K)

        per_category.setdefault(category, []).append((recalls[-1], mrr, ndcgs[-1], precs[-1]))

    n = len(queries)
    overall = {
        "recall@4": sum(recalls) / n,
        "mrr@4": sum(mrrs) / n,
        "ndcg@4": sum(ndcgs) / n,
        "precision@4": sum(precs) / n,
        "latency_ms": sum(latencies) / n,
    }
    cats = {
        c: {
            "recall@4": sum(x[0] for x in v) / len(v),
            "mrr@4": sum(x[1] for x in v) / len(v),
            "ndcg@4": sum(x[2] for x in v) / len(v),
            "precision@4": sum(x[3] for x in v) / len(v),
            "n": len(v),
        }
        for c, v in per_category.items()
    }
    return overall, cats


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


def run_config(label, chunk_fn, retrieval_fn, queries):
    print(f"\n{'='*70}\n{label}\n{'='*70}")

    doc_chunks = chunk_all(DOCS, chunk_fn)
    noise_chunks = chunk_all(EXTRA_CORPUS, chunk_fn)
    all_by_doc = {**doc_chunks, **noise_chunks}

    # Flatten for global indexing and relevance lookup
    all_chunks: list[str] = []
    for key in list(DOCS.keys()) + list(EXTRA_CORPUS.keys()):
        all_chunks.extend(all_by_doc[key])
    layout = build_gold_index(all_by_doc)

    index(all_by_doc)

    overall, cats = metrics_for_run(queries, retrieval_fn, layout, all_chunks)

    print(f"  chunks: {len(all_chunks)}  |  queries: {len(queries)}")
    print(f"  Recall@4     : {overall['recall@4']:.3f}")
    print(f"  MRR@4        : {overall['mrr@4']:.3f}")
    print(f"  nDCG@4       : {overall['ndcg@4']:.3f}")
    print(f"  Precision@4  : {overall['precision@4']:.3f}")
    print(f"  Latency      : {overall['latency_ms']:.0f} ms/query")
    print("  --- by category ---")
    for cat, m in cats.items():
        print(
            f"  {cat:12s} n={m['n']:3d}  R@4={m['recall@4']:.3f}  MRR={m['mrr@4']:.3f}  nDCG={m['ndcg@4']:.3f}"
        )

    return {"label": label, "chunks": len(all_chunks), "overall": overall, "categories": cats}


def main():
    queries = QUERIES
    print(f"Benchmark: {len(queries)} queries, {len(DOCS)} docs + {len(EXTRA_CORPUS)} noise docs")

    results = []

    # OLD pipeline
    results.append(run_config("OLD: char-splitter + dense-only", old_chunk, dense_only, queries))

    # NEW pipeline + ablations
    results.append(run_config("A1 NEW-chunks: dense-only", new_chunk_text, dense_only, queries))
    results.append(run_config("A2 NEW-chunks: hybrid (dense+BM25)", new_chunk_text, hybrid, queries))
    results.append(
        run_config("A3 NEW-chunks: hybrid + rerank  [FULL NEW]", new_chunk_text, hybrid_plus_rerank, queries)
    )

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    header = f"{'Config':45s} {'R@4':>6s} {'MRR':>6s} {'nDCG':>6s} {'P@4':>6s} {'ms':>7s}"
    print(header)
    for r in results:
        o = r["overall"]
        print(
            f"{r['label']:45s} {o['recall@4']:6.3f} {o['mrr@4']:6.3f} {o['ndcg@4']:6.3f} "
            f"{o['precision@4']:6.3f} {o['latency_ms']:7.0f}"
        )

    with open("bench_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\nSaved to bench_results.json")


if __name__ == "__main__":
    main()
