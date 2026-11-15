import sys, os
sys.path.insert(0, os.path.abspath("backend"))
os.chdir("backend")

from app.services.chunker import chunk_text, get_chunk_stats
from app.services.vector_store import store_chunks, search_chunks
from app.services.reranker import rerank
from app.services.rag_service import index_page, retrieve

text = """# Neural Networks

Neural networks are computing systems inspired by biological brains.

## History

The war of ideas in AI ended in 1986 when backpropagation became popular. Researchers could finally train deep models. Before that, perceptrons could only learn linear boundaries.

## Architecture

An LSTM is a recurrent unit with gates that control memory flow. LSTM networks process sequences one token at a time. LSTM cells avoid vanishing gradients through additive state updates.

The transformer removes recurrence entirely. Transformers use self-attention instead of gated memory. Self-attention lets every token attend to every other token directly.

## Applications

Machine translation was revolutionized by transformers in 2017. BERT and GPT are both transformer variants. Modern LLMs scale transformers to billions of parameters.
"""

print("=== 1. Chunking ===")
chunks = chunk_text(text)
stats = get_chunk_stats(chunks)
print(stats)
for c in chunks:
    print("-", repr(c[:90]))

print("\n=== 2. Index + Hybrid search ===")
n = store_chunks("test-session-1", chunks)
print("stored:", n)
res = search_chunks("test-session-1", "What is an LSTM?", k=5)
for r in res:
    print(f"idx={r['chunk_index']} score={r['score']}", repr(r['content'][:70]))

print("\n=== 3. Rerank ===")
final = rerank("What is an LSTM?", res, top_k=3)
for r in final:
    print(f"rerank={r['rerank_score']}", repr(r['content'][:70]))

print("\n=== 4. Full retrieve() ===")
out = retrieve("test-session-1", "How did AI history develop?", k=2)
for c in out.chunks:
    print("-", repr(c['content'][:80]))
print("SMOKE TEST PASSED")
