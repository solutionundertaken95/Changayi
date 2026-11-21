"""
smoke_test_agent.py — Verifies the agentic RAG loop + Code Mode sandbox.

Requires GEMINI_API_KEY (grading/rewriting/checking use Gemini).
Run: python backend/scripts/smoke_test_agent.py
"""

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.abspath("backend"))
os.chdir("backend")

from dotenv import load_dotenv
load_dotenv()

if not os.environ.get("GEMINI_API_KEY"):
    print("GEMINI_API_KEY not set — cannot run agent smoke test.")
    sys.exit(1)

from app.services.agent_service import run_agent  # noqa: E402
from app.services.code_mode import validate_script  # noqa: E402
from app.services.vector_store import store_chunks  # noqa: E402
from app.services.chunker import chunk_text  # noqa: E402
from app.services import workspace_service  # noqa: E402

# ── 0. Sandbox validator unit checks ────────────────────────────────────────
print("=== 0. Sandbox AST gate ===")
attacks = [
    ("import os", "import"),
    ("from os import path", "import"),
    ("eval('1+1')", "eval"),
    ("__builtins__", "dunder"),
    ("open('/etc/passwd')", "open"),
    ("(lambda: 0)()", "unknown fn"),
    ("while True: pass", "while"),
    ("x = '' .__class__", "dunder attr"),
]
for src, why in attacks:
    verdict = validate_script(src)
    status = "BLOCKED" if verdict else "ALLOWED!"
    print(f"  [{status}] {why:12s} {src!r}")
    assert verdict, f"Validator FAILED to block: {src}"

good = "chunks = search_page('test')\nbest = chunks[:2]\nresult = final_answer('test', best)"
assert validate_script(good) is None
print("  [PASSED ] legit script allowed")
print()

# ── 1. Index two mini-pages into a workspace ────────────────────────────────
print("=== 1. Indexing 2 pages ===")
DOC_A = """# Neural Networks
## Architecture
An LSTM is a recurrent unit with gates that control memory flow.
LSTM cells avoid vanishing gradients through additive state updates."""
DOC_B = """# Coral Reefs
## Bleaching
Bleached corals are starving, not dead, and can recover if temperatures fall quickly.
Ocean acidification slows the calcification that builds reef skeletons."""

ca, cb = chunk_text(DOC_A), chunk_text(DOC_B)
store_chunks("agent-tab-a", ca)
store_chunks("agent-tab-b", cb)
ws = workspace_service.create_workspace("AgentSmoke")
workspace_service.add_page(ws["workspace_id"], "agent-tab-a", "https://x/a", "Neural", len(ca))
workspace_service.add_page(ws["workspace_id"], "agent-tab-b", "https://x/b", "Coral", len(cb))
print(f"  indexed {len(ca)} + {len(cb)} chunks, workspace '{ws['name']}' ready")
print()

# ── 2. Happy-path agent run (single page) ───────────────────────────
print("=== 2. Agent run: happy path ===")
r = run_agent("agent-tab-a", "How do LSTM cells avoid vanishing gradients?", k=4)
for t in r.trace:
    print(f"  [{t.step:9s}] {t.detail}")
print(f"  answer: {r.answer[:120]}")
assert r.chunks and r.grounded, "expected grounded happy-path answer"
print()

# ── 3. Workspace escalation: ask about corals from the NEURAL page session ──
print("=== 3. Agent run: workspace escalation ===")
r2 = run_agent("agent-tab-a", "Can bleached coral recover?", workspace_id=ws["workspace_id"], k=4)
for t in r2.trace:
    print(f"  [{t.step:9s}] {t.detail}")
print(f"  answer: {r2.answer[:120]}")
from_bb = any(c.get("session_id") == "agent-tab-b" for c in r2.chunks)
print(f"  escalated: {r2.escalated_to_workspace}; sources from tab-b: {from_bb}")
assert r2.escalated_to_workspace or from_bb, "expected escalation or cross-tab source"
print()

# ── 4. Typo handling via rewrite ────────────────────────────────────
print("=== 4. Agent run: misspelled query ===")
r3 = run_agent("agent-tab-a", "what is the grait barier reef bleacing", workspace_id=ws["workspace_id"], k=4)
for t in r3.trace:
    print(f"  [{t.step:9s}] {t.detail}")
print(f"  rewritten: {r3.rewritten_query}")
print(f"  answer: {r3.answer[:120]}")
print()

# ── 5. Code Mode end-to-end ─────────────────────────────────────────
print("=== 5. Code Mode: one script, one round-trip ===")
from app.services.code_mode import run_research_code
answer, log = run_research_code("agent-tab-a", "How do LSTM cells avoid vanishing gradients?",
                                workspace_id=ws["workspace_id"])
print("  execution log (never seen by the model):")
for entry in log:
    print(f"    {entry}")
print(f"  answer: {answer[:150]}")
assert answer, "code mode should produce an answer"
print()
print("AGENT + CODE MODE SMOKE TEST PASSED")
