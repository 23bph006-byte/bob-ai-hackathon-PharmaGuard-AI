import streamlit as st

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PharmaGuard AI",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Shared CSS ──────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
        /* Sidebar nav */
        section[data-testid="stSidebar"] {
            background-color: #0d3b66;
        }
        section[data-testid="stSidebar"] * {
            color: #e8f4fd !important;
        }

        /* Hide default Streamlit footer */
        footer { visibility: hidden; }

        /* Main background */
        .main { background-color: #f5f8fc; }

        /* Card styling */
        .module-card {
            background: #ffffff;
            border: 1px solid #d0e4f5;
            border-left: 5px solid #0d6efd;
            border-radius: 8px;
            padding: 24px 28px;
            margin-bottom: 16px;
        }
        .module-card h3 { color: #0d3b66; margin-top: 0; }
        .module-card p  { color: #444; }

        /* Footer */
        .app-footer {
            margin-top: 60px;
            padding: 14px;
            text-align: center;
            font-size: 13px;
            color: #6c757d;
            border-top: 1px solid #dee2e6;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Sidebar navigation ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💊 PharmaGuard AI")
    st.markdown("---")
    page = st.radio(
        "Navigation",
        [
            "🏠 Home",
            "🔬 Drug Safety Signal Detection",
            "📋 Regulatory Submission Readiness",
            "🤖 AI Copilot",
        ],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown(
        "<small style='color:#a8c8e8'>IBM BoB AI Innovation Hackathon 2026<br>Team: B.Pharm Division</small>",
        unsafe_allow_html=True,
    )

# ── Page routing ────────────────────────────────────────────────────────────────
if page == "🏠 Home":
    from pages.home import render
    render()
elif page == "🔬 Drug Safety Signal Detection":
    from pages.signal_detection import render
    render()
elif page == "📋 Regulatory Submission Readiness":
    from pages.submission_readiness import render
    render()
elif page == "🤖 AI Copilot":
    from pages.ai_copilot import render
    render()
