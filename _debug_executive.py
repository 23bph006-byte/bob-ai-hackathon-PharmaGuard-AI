"""
Minimal reproducer for the Executive Summary button issue.
Run with: streamlit run _debug_executive.py
Then click each button and observe whether the response appears.
"""
import streamlit as st

st.set_page_config(page_title="Debug Executive Summary", layout="wide")

st.markdown("## Debug: Executive Summary Button")
st.markdown("Click each button and check if a response appears below.")

# Simulate the contexts being present
if "fake_safety" not in st.session_state:
    st.session_state["fake_safety"] = True
if "fake_regulatory" not in st.session_state:
    st.session_state["fake_regulatory"] = True

safety_ctx     = {"n_signals": 2, "total_pairs": 45} if st.session_state["fake_safety"] else None
regulatory_ctx = {"score_pct": 85.7, "missing": 4}   if st.session_state["fake_regulatory"] else None

st.write(f"safety_ctx: {'present' if safety_ctx else 'None'}")
st.write(f"regulatory_ctx: {'present' if regulatory_ctx else 'None'}")
st.write(f"session_state keys before buttons: {list(st.session_state.keys())}")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Safety Summary", disabled=(safety_ctx is None)):
        st.session_state["copilot_response"] = "SAFETY: " + str(safety_ctx)
        st.session_state["copilot_question"] = "Safety"

with col2:
    if st.button("Regulatory Summary", disabled=(regulatory_ctx is None)):
        st.session_state["copilot_response"] = "REGULATORY: " + str(regulatory_ctx)
        st.session_state["copilot_question"] = "Regulatory"

with col3:
    if st.button("Executive Summary",
                 disabled=(safety_ctx is None and regulatory_ctx is None)):
        st.session_state["copilot_response"] = (
            "EXECUTIVE: safety=" + str(safety_ctx) +
            " regulatory=" + str(regulatory_ctx)
        )
        st.session_state["copilot_question"] = "Executive"

st.markdown("---")
st.write(f"session_state keys after buttons: {list(st.session_state.keys())}")

if "copilot_response" in st.session_state:
    st.success(f"Q: {st.session_state.get('copilot_question','')}")
    st.write(st.session_state["copilot_response"])
else:
    st.info("No response yet — click a button above.")
