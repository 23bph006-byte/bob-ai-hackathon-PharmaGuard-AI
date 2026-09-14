import streamlit as st


def render():
    # ── Hero header ────────────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="text-align:center; padding: 40px 0 20px 0;">
            <h1 style="font-size:2.8rem; color:#0d3b66; margin-bottom:6px;">💊 PharmaGuard AI</h1>
            <p style="font-size:1.15rem; color:#1a6eb5; font-weight:500;">
                AI-Powered Pharmacovigilance &amp; Regulatory Submission Copilot
            </p>
            <hr style="border:1px solid #d0e4f5; margin:24px auto; width:60%;">
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Mission statement ──────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="max-width:760px; margin:0 auto 36px auto; text-align:center; color:#444; font-size:1rem; line-height:1.7;">
            PharmaGuard AI assists pharmacovigilance professionals and regulatory teams in detecting
            drug safety signals from adverse-event data and assessing the readiness of regulatory
            submission dossiers — powered by AI.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Module cards ───────────────────────────────────────────────────────────
    st.markdown("### 🧭 Available Modules")
    st.markdown("")

    col1, col2, col3 = st.columns(3, gap="large")

    with col1:
        st.markdown(
            """
            <div class="module-card">
                <h3>🔬 Drug Safety Signal Detection</h3>
                <p>
                    Upload adverse-event reports and apply statistical signal-detection
                    methods (PRR, ROR, BCPNN) to identify potential drug safety signals.
                    Visualise disproportionality scores and prioritise signals for
                    medical review.
                </p>
                <p><strong>Status:</strong> <span style="color:#2e7d32;">✅ Available</span></p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            """
            <div class="module-card">
                <h3>📋 Regulatory Submission Readiness</h3>
                <p>
                    Check your CTD/eCTD dossier against ICH guidelines. Upload documents,
                    run automated completeness checks, and receive an AI-generated
                    readiness score with actionable recommendations before submission.
                </p>
                <p><strong>Status:</strong> <span style="color:#2e7d32;">✅ Available</span></p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            """
            <div class="module-card">
                <h3>🤖 AI Copilot</h3>
                <p>
                    AI-assisted interpretation of your safety signals and regulatory
                    readiness results. Get contextual explanations, signal prioritisation,
                    CTD gap analysis, and executive summaries — powered by IBM watsonx.ai
                    or a transparent rule-based fallback.
                </p>
                <p><strong>Status:</strong> <span style="color:#2e7d32;">✅ Available</span></p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── How it works ───────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### ⚙️ How It Works")

    step1, step2, step3 = st.columns(3, gap="medium")

    with step1:
        st.markdown(
            """
            <div style="background:#eaf3fb; border-radius:8px; padding:20px; text-align:center;">
                <div style="font-size:2rem;">📂</div>
                <strong style="color:#0d3b66;">1. Upload Data</strong>
                <p style="color:#555; font-size:0.9rem; margin-top:8px;">
                    Upload adverse-event datasets (CSV/Excel) or regulatory documents (PDF/Word).
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with step2:
        st.markdown(
            """
            <div style="background:#eaf3fb; border-radius:8px; padding:20px; text-align:center;">
                <div style="font-size:2rem;">🤖</div>
                <strong style="color:#0d3b66;">2. AI Analysis</strong>
                <p style="color:#555; font-size:0.9rem; margin-top:8px;">
                    The AI engine runs signal-detection algorithms and document compliance checks.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with step3:
        st.markdown(
            """
            <div style="background:#eaf3fb; border-radius:8px; padding:20px; text-align:center;">
                <div style="font-size:2rem;">📊</div>
                <strong style="color:#0d3b66;">3. Review Results</strong>
                <p style="color:#555; font-size:0.9rem; margin-top:8px;">
                    Review flagged signals, readiness scores, and AI-generated recommendations.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Footer ─────────────────────────────────────────────────────────────────
    st.markdown(
        """
        <div class="app-footer">
            Prototype developed for <strong>IBM BoB AI Innovation Hackathon 2026</strong>
            &nbsp;|&nbsp; Problem Statement P2 — Drug Safety Signal Detector &amp; Regulatory Submission Readiness Checker
        </div>
        """,
        unsafe_allow_html=True,
    )
