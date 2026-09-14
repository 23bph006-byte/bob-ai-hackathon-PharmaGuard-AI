"""
Smoke-test for ai_copilot.py — tests context builders and all fallback paths.
All tests run without a Streamlit session (pure Python) by injecting mock
session_state via a lightweight shim.
"""
import sys, types
sys.path.insert(0, ".")

# ── Minimal Streamlit shim so we can import pages without a running server ─────
_ss: dict = {}

class _FakeSecrets:
    def get(self, key, default=None): return default

class _FakeST(types.ModuleType):
    session_state = _ss

    # Silence every st.* call used at module level
    def set_page_config(self, **kw): pass
    def markdown(self, *a, **kw): pass
    def warning(self, *a, **kw): pass
    def info(self, *a, **kw): pass
    def success(self, *a, **kw): pass
    def error(self, *a, **kw): pass
    def caption(self, *a, **kw): pass
    def expander(self, *a, **kw):
        import contextlib
        @contextlib.contextmanager
        def _ctx(): yield
        return _ctx()
    def columns(self, *a, **kw): return [self]*max(a[0] if a else 1, 1)
    def __enter__(self): return self
    def __exit__(self, *a): pass
    @property
    def secrets(self): return _FakeSecrets()

_fake_st = _FakeST("streamlit")
sys.modules["streamlit"] = _fake_st

import pandas as pd
from pages.ai_copilot import (
    build_safety_context,
    build_regulatory_context,
    _fallback_safety_summary,
    _fallback_regulatory_summary,
    _fallback_top_signal_explanation,
    _fallback_signal_prioritisation,
    _fallback_ctd_priorities,
    _fallback_explain_prr,
    _fallback_combined_summary,
    _fallback_executive_summary,
    _detect_ai_provider,
    query_ai,
    _build_llm_context_block,
)

# ── Helper: inject mock safety results into session_state ──────────────────────
def _inject_safety():
    _ss["signal_results"] = pd.DataFrame([
        {"Drug": "Atorvastatin", "Adverse_Event": "Myopathy",
         "a": 5, "b": 7, "c": 1, "d": 87,
         "PRR": 36.667, "Chi_Square": 30.757, "Signal_Status": "⚠️ Potential Signal"},
        {"Drug": "Metformin", "Adverse_Event": "Diarrhoea",
         "a": 4, "b": 21, "c": 0, "d": 75,
         "PRR": 26.769, "Chi_Square": 20.890, "Signal_Status": "⚠️ Potential Signal"},
        {"Drug": "Warfarin", "Adverse_Event": "Headache",
         "a": 1, "b": 8, "c": 7, "d": 84,
         "PRR": 1.5,    "Chi_Square": 0.4,    "Signal_Status": "✅ No Signal"},
    ])

def _inject_regulatory():
    _ss["readiness_df"] = pd.DataFrame([
        {"Module": "Module 1", "Document": "Application form",              "Status": "Present"},
        {"Module": "Module 1", "Document": "Prescribing information",       "Status": "Present"},
        {"Module": "Module 3", "Document": "Manufacturing process",         "Status": "Present"},
        {"Module": "Module 3", "Document": "Process validation data",       "Status": "Missing"},
        {"Module": "Module 3", "Document": "Stability data (drug product)", "Status": "Missing"},
        {"Module": "Module 4", "Document": "Genotoxicity studies",          "Status": "Not Applicable"},
        {"Module": "Module 5", "Document": "Safety study reports",          "Status": "Missing"},
        {"Module": "Module 5", "Document": "Efficacy study reports",        "Status": "Present"},
    ])

# ══════════════════════════════════════════════════════════════════════════════

# 1. No context -> both builders return None
_ss.clear()
assert build_safety_context()     is None, "Safety ctx should be None with no data"
assert build_regulatory_context() is None, "Regulatory ctx should be None with no data"
print("1. Empty session_state -> both contexts None  PASS")

# 2. Safety context builds correctly
_inject_safety()
s_ctx = build_safety_context()
assert s_ctx is not None
assert s_ctx["total_pairs"] == 3
assert s_ctx["n_signals"]   == 2
assert s_ctx["top_signals"][0]["Drug"] == "Atorvastatin"
print(f"2. Safety context: {s_ctx['total_pairs']} pairs, {s_ctx['n_signals']} signals  PASS")

# 3. Regulatory context builds correctly
_inject_regulatory()
r_ctx = build_regulatory_context()
assert r_ctx is not None
assert r_ctx["missing"] == 3
assert "Module 3" in r_ctx["missing_by_module"]
print(f"3. Regulatory context: score={r_ctx['score_pct']}%, {r_ctx['missing']} missing  PASS")

# 4. Fallback safety summary contains key numbers
txt = _fallback_safety_summary(s_ctx)
assert "Atorvastatin" in txt
assert "36.667" in txt or "36.667" in txt.replace(",", ".")
print("4. Fallback safety summary contains top signal  PASS")

# 5. Fallback regulatory summary contains score
txt = _fallback_regulatory_summary(r_ctx)
assert str(r_ctx["score_pct"]) in txt
print("5. Fallback regulatory summary contains score  PASS")

# 6. Fallback top signal explanation
txt = _fallback_top_signal_explanation(s_ctx)
assert "Atorvastatin" in txt
assert "Myopathy"     in txt
assert "PRR"          in txt
print("6. Fallback top signal explanation  PASS")

# 7. Fallback signal prioritisation
txt = _fallback_signal_prioritisation(s_ctx)
assert "Atorvastatin" in txt
print("7. Fallback signal prioritisation  PASS")

# 8. Fallback CTD priorities
txt = _fallback_ctd_priorities(r_ctx)
assert "Module 3" in txt or "Process validation" in txt
print("8. Fallback CTD priorities  PASS")

# 9. Fallback PRR explanation
txt = _fallback_explain_prr(s_ctx)
assert "PRR" in txt
assert "Proportional" in txt
print("9. Fallback PRR explanation  PASS")

# 10. Combined summary backward-compat delegate still works
txt = _fallback_combined_summary(s_ctx, r_ctx)
assert "Drug Safety" in txt or "Drug" in txt
assert "Regulatory" in txt or "Readiness" in txt
print("10. Combined summary (backward-compat delegate)  PASS")

# 11. Fallback provider detection (no env vars set during test)
import os
os.environ.pop("WATSONX_API_KEY",  None)
os.environ.pop("WATSONX_PROJECT_ID", None)
os.environ.pop("OPENAI_API_KEY",   None)
provider = _detect_ai_provider()
assert provider == "fallback", f"Expected fallback, got {provider}"
print(f"11. Provider detection (no keys): '{provider}'  PASS")

# 12. query_ai routes to fallback and returns a string
resp, mode = query_ai("Summarise the current safety signal analysis.",
                      s_ctx, r_ctx, "fallback")
assert isinstance(resp, str) and len(resp) > 50
assert mode == "Rule-based fallback"
print(f"12. query_ai -> fallback, {len(resp)} chars  PASS")

# 13. query_ai PRR question
resp, mode = query_ai("Explain the PRR result in simple terms.", s_ctx, r_ctx, "fallback")
assert "PRR" in resp
print(f"13. query_ai PRR question  PASS")

# 14. query_ai CTD gaps question
resp, mode = query_ai("What are the most important CTD gaps?", s_ctx, r_ctx, "fallback")
assert "Module" in resp
print(f"14. query_ai CTD gaps question  PASS")

# 15. LLM context block includes actual numbers
block = _build_llm_context_block(s_ctx, r_ctx)
assert "Atorvastatin" in block
assert str(r_ctx["score_pct"]) in block
print(f"15. LLM context block includes actual data  PASS")

# 16. No signal fallback (empty dataset)
_ss["signal_results"] = pd.DataFrame(columns=["Drug","Adverse_Event","a","b","c","d","PRR","Chi_Square","Signal_Status"])
empty_ctx = build_safety_context()
assert empty_ctx is not None
assert empty_ctx["n_signals"] == 0
txt = _fallback_safety_summary(empty_ctx)
assert "No drug" in txt or "No combinations" in txt.lower() or "no drug" in txt.lower()
print("16. No-signal edge case  PASS")

# ── NEW TESTS for executive summary fix ────────────────────────────────────────

# 17. _fallback_executive_summary produces all 4 required sections
_inject_safety()
_inject_regulatory()
s_ctx = build_safety_context()
r_ctx = build_regulatory_context()
exec_txt = _fallback_executive_summary(s_ctx, r_ctx)
assert "Executive Summary"          in exec_txt, "Missing title"
assert "Drug Safety Overview"       in exec_txt, "Missing section 1"
assert "Regulatory Readiness"       in exec_txt, "Missing section 2"
assert "Key Priorities"             in exec_txt, "Missing section 3"
assert "Important Limitations"      in exec_txt, "Missing section 4"
assert "Atorvastatin"               in exec_txt, "Missing top signal drug"
assert str(r_ctx["score_pct"])      in exec_txt, "Missing readiness score"
print(f"17. Executive summary: 4 sections, actual data present  PASS")

# 18. Executive summary with only safety context (no regulatory)
exec_txt2 = _fallback_executive_summary(s_ctx, None)
assert "Drug Safety Overview"  in exec_txt2
assert "No regulatory"         in exec_txt2.lower() or "not available" in exec_txt2.lower() or "readiness data" in exec_txt2.lower()
assert "Important Limitations" in exec_txt2
print("18. Executive summary with safety-only context  PASS")

# 19. Executive summary with only regulatory context (no safety)
exec_txt3 = _fallback_executive_summary(None, r_ctx)
assert "Regulatory Readiness"  in exec_txt3
assert "No safety"             in exec_txt3.lower() or "not available" in exec_txt3.lower() or "safety analysis" in exec_txt3.lower()
assert "Important Limitations" in exec_txt3
print("19. Executive summary with regulatory-only context  PASS")

# 20. query_ai routes "Generate an executive summary of both analyses." to executive summary
resp, mode = query_ai("Generate an executive summary of both analyses.", s_ctx, r_ctx, "fallback")
assert "Executive Summary"     in resp, f"Expected 'Executive Summary' in response, got: {resp[:200]}"
assert "Drug Safety Overview"  in resp
assert "Key Priorities"        in resp
assert mode == "Rule-based fallback"
print(f"20. query_ai executive summary routing: {len(resp)} chars  PASS")

# 21. Executive summary with both contexts None produces graceful output
exec_txt4 = _fallback_executive_summary(None, None)
assert "Executive Summary"     in exec_txt4
assert "Important Limitations" in exec_txt4
print("21. Executive summary with no context: graceful output  PASS")

print()
print("All 21 tests passed.")
