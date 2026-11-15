"""
eval_rag.py — Side-by-side evaluation of OLD vs NEW RAG pipeline.

OLD pipeline (simulated faithfully):
  chunking = RecursiveCharacterTextSplitter(500, 50)  [the original chunker.py]
  retrieval = dense-only similarity_search top-4      [the original search_chunks]

NEW pipeline (current code):
  chunking = semantic + structure-aware (chunker.py)
  retrieval = hybrid dense+BM25 → RRF (vector_store.py)
  rerank    = cross-encoder ms-marco-MiniLM-L-6-v2 (reranker.py)

Metrics: Recall@4, MRR@4, nDCG@4, Precision@4, latency per stage.
"""

import os
import sys
import time

sys.path.insert(0, os.path.abspath("backend"))
os.chdir("backend")

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.chunker import chunk_text as new_chunk_text
from app.services.vector_store import store_chunks, search_chunks
from app.services.reranker import rerank
from app.services.embedder import get_embeddings
from langchain_community.vectorstores import Chroma

# ------------------------------------------------------------------
# Corpus: a multi-section document (like a typical Wikipedia page)
# ------------------------------------------------------------------
DOC = """# Neural Networks

Neural networks are computing systems inspired by biological brains. They learn by adjusting weighted connections between artificial neurons.

## History

The war of ideas in AI ended in 1986 when backpropagation became popular. Researchers could finally train multi-layer models efficiently. Before that, perceptrons could only learn linear boundaries. The 1943 McCulloch-Pitts neuron model was the first mathematical abstraction of a biological neuron. Frank Rosenblatt built the first perceptron hardware in 1958 at Cornell Aeronautical Laboratory.

## Architecture

An LSTM is a recurrent unit with gates that control memory flow. LSTM networks process sequences one token at a time. LSTM cells avoid vanishing gradients through additive state updates. The forget gate decides what information to discard from the cell state. GRU networks simplify LSTM design by merging the forget and input gates.

The transformer removes recurrence entirely. Transformers use self-attention instead of gated memory. Self-attention lets every token attend to every other token directly. Multi-head attention runs several attention operations in parallel. Positional encodings inject word order information into the model.

## Training

Backpropagation computes gradients of the loss with respect to every weight. Gradient descent updates weights in the direction that reduces loss. The learning rate controls how large each weight update step is. Batch normalization stabilizes training by normalizing layer activations. Dropout randomly zeroes neurons during training to prevent overfitting. Adam optimizer combines momentum and adaptive learning rates.

## Applications

Machine translation was revolutionized by transformers in 2017. BERT and GPT are both transformer variants. Modern LLMs scale transformers to billions of parameters. Speech recognition systems use recurrent networks to model audio sequences. Convolutional networks dominate image classification benchmarks. AlphaFold used attention mechanisms to predict protein structures.

## Limitations

Large language models sometimes hallucinate facts that sound plausible. Training frontier models requires enormous compute and energy budgets. Neural networks are vulnerable to adversarial examples crafted with tiny perturbations. Models trained on biased data reproduce and amplify those biases. The black box nature of deep networks makes decisions hard to explain.
"""

# ------------------------------------------------------------------
# Gold labels: (query, gold sentence) — a chunk is relevant if it
# contains the gold sentence. Mapped per chunking scheme.
# ------------------------------------------------------------------
QUERIES = [
    ("What is an LSTM and how does it work?", "An LSTM is a recurrent unit with gates that control memory flow."),
    ("How do transformers process sequences?", "The transformer removes recurrence entirely."),
    ("What is backpropagation used for?", "Backpropagation computes gradients of the loss with respect to every weight."),
    ("Who invented the perceptron?", "Frank Rosenblatt built the first perceptron hardware in 1958 at Cornell Aeronautical Laboratory."),
    ("How do transformers avoid vanishing gradients?", "LSTM cells avoid vanishing gradients through additive state updates."),
    ("What is the learning rate?", "The learning rate controls how large each weight update step is."),
    ("What are the downsides of LLMs?", "Large language models sometimes hallucinate facts that sound plausible."),
    ("What does self-attention do?", "Self-attention lets every token attend to every other token directly."),
    ("How was machine translation changed?", "Machine translation was revolutionized by transformers in 2017."),
    ("What is dropout?", "Dropout randomly zeroes neurons during training to prevent overfitting."),
]

# ------------------------------------------------------------------


def old_chunk(text: str) -> list[str]:
    """The ORIGINAL chunker.py, verbatim parameters."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", ". ", "! ", "? ", ", ", " ", ""],
        length_function=len,
        is_separator_regex=False,
    )
    chunks = splitter.split_text(text)
    return [c.strip() for c in chunks if len(c.strip()) > 30]


def _dense_search_topk(collection: str, query: str, k: int) -> list[dict]:
    """The ORIGINAL search_chunks: dense-only similarity_search."""
    vectorstore = Chroma(
        collection_name=collection,
        embedding_function=get_embeddings(),
        persist_directory="./chroma_data",
    )
    docs = vectorstore.similarity_search(query=query, k=k)
    return [
        {"content": d.page_content, "chunk_index": d.metadata.get("chunk_index", -1)}
        for d in docs
    ]


def _delete_collection(name: str):
    import chromadb
    client = chromadb.PersistentClient(path="./chroma_data")
    try:
        client.delete_collection(name=name)
    except Exception:
        pass


def gold_relevance(chunks: list[str], gold_sentence: str) -> set[int]:
    return {i for i, c in enumerate(chunks) if gold_sentence in c}


def evaluate(chunks, retrieval_fn, label):
    """Runs all queries against a retrieval fn and computes metrics."""
    recalls, mrrs, ndcgs, precs = [], [], [], []
    latencies = []
    misses = []

    for query, gold in QUERIES:
        relevant = gold_relevance(chunks, gold)
        t0 = time.perf_counter()
        results = retrieval_fn(query, k=4)
        latencies.append((time.perf_counter() - t0) * 1000)

        # binary relevance of retrieved chunks
        rel = [1 if i in relevant else 0 for i in (r["chunk_index"] for r in results)]

        hit = sum(rel[:4])
        recalls.append(hit / len(relevant) if relevant else 0)

        # MRR
        mrr = 0.0
        for rank, r in enumerate(rel, 1):
            if r:
                mrr = 1.0 / rank
                break
        mrrs.append(mrr)

        # nDCG@4 (binary gains)
        dcg = sum(r / (1 if i == 0 else __import__("math").log2(i + 1)) for i, r in enumerate(rel))
        ideal = sorted(rel, reverse=True)
        idcg = sum(r / (1 if i == 0 else __import__("math").log2(i + 1)) for i, r in enumerate(ideal))
        ndcgs.append(dcg / idcg if idcg else 0)

        precs.append(sum(rel[:4]) / 4)
        if mrr == 0.0:
            misses.append(query)

    n = len(QUERIES)
    print(f"\n--- {label} ---")
    for m in misses:
        print(f"  MISS: {m}")
    print(f"  chunks created:   {len(chunks)}")
    print(f"  Recall@4:         {sum(recalls)/n:.3f}   ({sum(recalls)}/{n} queries)")
    print(f"  MRR@4:            {sum(mrrs)/n:.3f}")
    print(f"  nDCG@4:           {sum(ndcgs)/n:.3f}")
    print(f"  Precision@4:      {sum(precs)/n:.3f}")
    print(f"  Avg latency:      {sum(latencies)/n:.0f} ms/query")
    return {
        "chunks": len(chunks),
        "recall@4": sum(recalls) / n,
        "mrr@4": sum(mrrs) / n,
        "ndcg@4": sum(ndcgs) / n,
        "precision@4": sum(precs) / n,
        "latency_ms": sum(latencies) / n,
    }


# ------------------------------------------------------------------
print("=== OLD PIPELINE ===")
old_chunks = old_chunk(DOC)
_delete_collection("eval-old")
store_chunks("eval-old", old_chunks)
old_metrics = evaluate(
    old_chunks,
    lambda q, k: _dense_search_topk("eval-old", q, k),
    "OLD: char-splitter + dense-only top-4",
)

print("\n=== NEW PIPELINE ===")
new_chunks = new_chunk_text(DOC)
_delete_collection("eval-new")
store_chunks("eval-new", new_chunks)


def new_retrieval(q, k):
    candidates = search_chunks("eval-new", q, k=8)
    return rerank(q, candidates, top_k=k)


new_metrics = evaluate(
    new_chunks,
    new_retrieval,
    "NEW: semantic/structure chunking + hybrid + rerank",
)

# ------------------------------------------------------------------
print("\n=== DELTA (new vs old) ===")
for key in ["recall@4", "mrr@4", "ndcg@4", "precision@4", "latency_ms"]:
    d = new_metrics[key] - old_metrics[key]
    print(f"  {key:12s}: {old_metrics[key]:.3f} -> {new_metrics[key]:.3f}  ({'+' if d >= 0 else ''}{d:.3f})")
