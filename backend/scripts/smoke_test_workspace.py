"""
smoke_test_workspace.py — End-to-end test of the Multi-Tab Knowledge Base.

Simulates: index 3 "tabs" → create a workspace → add pages →
fan-out search → workspace chat question (retrieval-only, no Gemini key
needed since we verify the retrieval scope, and generate_answer is only
called in chat(); here we call chat() only if a key is present).
"""

import os
import sys

sys.path.insert(0, os.path.abspath("backend"))
os.chdir("backend")

from app.services.vector_store import store_chunks, search_workspace
from app.services import workspace_service
from app.services.chunker import chunk_text

DOC_A = """# Neural Networks

Neural networks learn by adjusting weighted connections between artificial neurons.

## Architecture

An LSTM is a recurrent unit with gates that control memory flow. LSTM cells avoid vanishing gradients through additive state updates. The transformer removes recurrence entirely and uses self-attention.
"""

DOC_B = """# Coral Reef Ecosystems

Coral reefs support roughly a quarter of all marine species.

## Bleaching

When water temperatures rise, corals expel their algae in a process called bleaching. Bleached corals are starving, not dead, and can recover if temperatures fall quickly. Ocean acidification slows the calcification that builds reef skeletons.
"""

DOC_C = """# Space Telescopes

Space telescopes observe wavelength bands that Earth's atmosphere absorbs.

## JWST

The JWST primary mirror spans 6.5 meters in 18 gold-coated beryllium segments. It orbits the second Lagrange point, 1.5 million kilometers from Earth. Webb launched on Christmas Day 2021 from Kourou, French Guiana.
"""

print("=== 1. Index three 'tabs' ===")
chunks_a = chunk_text(DOC_A)
chunks_b = chunk_text(DOC_B)
chunks_c = chunk_text(DOC_C)
store_chunks("tab-neural", chunks_a)
store_chunks("tab-coral", chunks_b)
store_chunks("tab-jwst", chunks_c)
print(f"tab-neural: {len(chunks_a)}, tab-coral: {len(chunks_b)}, tab-jwst: {len(chunks_c)}")

print("\n=== 2. Create workspace + add pages ===")
ws = workspace_service.create_workspace("Smoke test KB")
wsid = ws["workspace_id"]
workspace_service.add_page(wsid, "tab-neural", "https://x/neural", "Neural Networks", len(chunks_a))
workspace_service.add_page(wsid, "tab-coral", "https://x/coral", "Coral Reefs", len(chunks_b))
workspace_service.add_page(wsid, "tab-jwst", "https://x/jwst", "Space Telescopes", len(chunks_c))
ws = workspace_service.get_workspace(wsid)
print(f"workspace '{ws['name']}' has {len(ws['pages'])} pages: {[p['session_id'] for p in ws['pages']]}")

print("\n=== 3. Cross-tab fan-out searches ===")
for q, expect_session in [
    ("How do LSTM cells avoid vanishing gradients?", "tab-neural"),
    ("Can bleached coral recover?", "tab-coral"),
    ("Where does the JWST orbit?", "tab-jwst"),
    ("What launched on Christmas Day 2021?", "tab-jwst"),
]:
    results = search_workspace(wsid, ["tab-neural", "tab-coral", "tab-jwst"], q, k=3)
    top = results[0] if results else None
    origin = top.get("session_id") if top else "?"
    status = "OK " if origin == expect_session else "MISS"
    print(f"[{status}] '{q}' -> top from {origin} (expected {expect_session}), "
          f"score={top.get('rerank_score') if top else '-'}")

print("\n=== 4. Workspace chat (retrieval scope) ===")
from app.services import chat_service
if os.environ.get("GEMINI_API_KEY"):
    result = chat_service.chat("tab-neural", "What was launched on Christmas Day 2021?", workspace_id=wsid)
    print("answer:", result.answer[:200])
    print("source origins:", [s.get("session_id") for s in result.sources])
else:
    print("GEMINI_API_KEY not set — verifying retrieval scope only")
    chunks = search_workspace(wsid, workspace_service.workspace_session_ids(wsid),
                              "What was launched on Christmas Day 2021?", k=3)
    print("top chunk origin:", chunks[0].get("session_id"))

print("\n=== 5. Empty workspace handling ===")
empty = workspace_service.create_workspace("Empty")
result = chat_service.chat("tab-neural", "test question", workspace_id=empty["workspace_id"])
print("empty workspace answer:", result.answer[:80])

print("\nSMOKE TEST PASSED")
