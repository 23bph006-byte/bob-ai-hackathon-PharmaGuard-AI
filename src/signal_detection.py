"""
Drug Safety Signal Detection — PharmaGuard AI
==============================================
Implements:
  - CSV upload and validation
  - 2×2 contingency table construction
  - PRR (Proportional Reporting Ratio) calculation
  - Chi-square statistic for signal screening
  - Automated sweep across all drug–event pairs
  - Visualisation of top signals

Statistical note
----------------
PRR = [a/(a+b)] / [c/(c+d)]
  a = drug + event       b = drug + other events
  c = other drugs + event  d = other drugs + other events

Evans (2001) screening criteria (EMA/MHRA standard):
  PRR ≥ 2  AND  a ≥ 3  AND  chi-square ≥ 4

This is a screening tool. Disproportionate reporting does NOT
establish a causal relationship between drug and adverse event.
"""

import math
import io

import pandas as pd
import streamlit as st

# ── Constants ──────────────────────────────────────────────────────────────────
REQUIRED_COLUMNS = {"Drug", "Adverse_Event"}
OPTIONAL_COLUMNS = ["Patient_ID", "Age", "Sex", "Seriousness"]

PRR_THRESHOLD     = 2.0
COUNT_THRESHOLD   = 3        # minimum value of a
CHI2_THRESHOLD    = 4.0

FOOTER_HTML = """
<div class="app-footer">
    Prototype developed for <strong>IBM BoB AI Innovation Hackathon 2026</strong>
    &nbsp;|&nbsp; Problem Statement P2 — Drug Safety Signal Detector &amp; Regulatory Submission Readiness Checker
</div>
"""

# ══════════════════════════════════════════════════════════════════════════════
# Pure calculation functions (no Streamlit calls — easy to test)
# ══════════════════════════════════════════════════════════════════════════════

def validate_dataframe(df: pd.DataFrame) -> list[str]:
    """Return a list of error strings; empty list means the data is valid."""
    errors = []
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        errors.append(f"Missing required column(s): **{', '.join(sorted(missing))}**")
    if df.empty:
        errors.append("The uploaded file contains no data rows.")
    return errors


def build_contingency(df: pd.DataFrame, drug: str, event: str) -> dict:
    """
    Build a 2×2 contingency table for the given drug–event pair.

    Returns a dict with keys: a, b, c, d, n
    """
    drug_mask  = df["Drug"]          == drug
    event_mask = df["Adverse_Event"] == event

    a = int((drug_mask  &  event_mask).sum())   # drug  + event
    b = int((drug_mask  & ~event_mask).sum())   # drug  + other
    c = int((~drug_mask &  event_mask).sum())   # other + event
    d = int((~drug_mask & ~event_mask).sum())   # other + other

    return {"a": a, "b": b, "c": c, "d": d, "n": a + b + c + d}


def calculate_prr(a: int, b: int, c: int, d: int) -> float | None:
    """
    PRR = [a/(a+b)] / [c/(c+d)]

    Returns None when the denominator is zero (undefined).
    """
    denom_drug  = a + b
    denom_other = c + d

    if denom_drug == 0 or denom_other == 0 or c == 0:
        return None

    p_drug  = a / denom_drug
    p_other = c / denom_other

    if p_other == 0:
        return None

    return p_drug / p_other


def calculate_chi2(a: int, b: int, c: int, d: int) -> float | None:
    """
    Yates-uncorrected chi-square for a 2×2 table.

    χ² = n(ad − bc)² / [(a+b)(c+d)(a+c)(b+d)]

    Returns None when any marginal is zero.
    """
    n = a + b + c + d
    row1 = a + b
    row2 = c + d
    col1 = a + c
    col2 = b + d

    if row1 == 0 or row2 == 0 or col1 == 0 or col2 == 0 or n == 0:
        return None

    numerator   = n * ((a * d - b * c) ** 2)
    denominator = row1 * row2 * col1 * col2

    if denominator == 0:
        return None

    return numerator / denominator


def meets_screening_criteria(a: int, prr: float | None, chi2: float | None) -> bool:
    """Evans (2001) three-way screening: PRR ≥ 2, a ≥ 3, χ² ≥ 4."""
    if prr is None or chi2 is None:
        return False
    return prr >= PRR_THRESHOLD and a >= COUNT_THRESHOLD and chi2 >= CHI2_THRESHOLD


def run_signal_sweep(df: pd.DataFrame) -> pd.DataFrame:
    """
    Iterate over every (Drug, Adverse_Event) pair present in df.
    Return a DataFrame of results sorted by PRR descending.
    """
    pairs = df.groupby(["Drug", "Adverse_Event"]).size().reset_index(name="count")

    rows = []
    for _, row in pairs.iterrows():
        drug  = row["Drug"]
        event = row["Adverse_Event"]
        ct    = build_contingency(df, drug, event)
        prr   = calculate_prr(ct["a"], ct["b"], ct["c"], ct["d"])
        chi2  = calculate_chi2(ct["a"], ct["b"], ct["c"], ct["d"])
        signal = meets_screening_criteria(ct["a"], prr, chi2)

        rows.append({
            "Drug":          drug,
            "Adverse_Event": event,
            "a":             ct["a"],
            "b":             ct["b"],
            "c":             ct["c"],
            "d":             ct["d"],
            "PRR":           round(prr,  3) if prr  is not None else None,
            "Chi_Square":    round(chi2, 3) if chi2 is not None else None,
            "Signal_Status": "⚠️ Potential Signal" if signal else "✅ No Signal",
        })

    result = pd.DataFrame(rows)
    # Sort: signals first, then by PRR descending
    result["_is_signal"] = result["Signal_Status"].str.startswith("⚠️")
    result = result.sort_values(["_is_signal", "PRR"], ascending=[False, False])
    result = result.drop(columns=["_is_signal"]).reset_index(drop=True)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# UI helpers
# ══════════════════════════════════════════════════════════════════════════════

def _section(title: str) -> None:
    st.markdown(f"### {title}")


def _info_box(label: str, value: str, colour: str = "#0d3b66") -> str:
    return (
        f'<div style="background:#eaf3fb;border-radius:8px;padding:16px 20px;text-align:center;">'
        f'<div style="font-size:1.8rem;font-weight:700;color:{colour};">{value}</div>'
        f'<div style="color:#555;font-size:0.85rem;margin-top:4px;">{label}</div>'
        f'</div>'
    )


def _render_contingency_table(a: int, b: int, c: int, d: int, drug: str, event: str) -> None:
    table_html = f"""
    <table style="border-collapse:collapse;width:100%;font-size:0.95rem;">
      <thead>
        <tr>
          <th style="padding:10px;background:#0d3b66;color:#fff;border:1px solid #ccc;"></th>
          <th style="padding:10px;background:#0d3b66;color:#fff;border:1px solid #ccc;">{event}</th>
          <th style="padding:10px;background:#0d3b66;color:#fff;border:1px solid #ccc;">Other Events</th>
          <th style="padding:10px;background:#0d3b66;color:#fff;border:1px solid #ccc;">Row Total</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td style="padding:10px;font-weight:600;background:#e8f4fd;border:1px solid #ccc;">{drug}</td>
          <td style="padding:10px;background:#fff3cd;border:1px solid #ccc;text-align:center;font-weight:700;">a = {a}</td>
          <td style="padding:10px;background:#ffffff;border:1px solid #ccc;text-align:center;">b = {b}</td>
          <td style="padding:10px;background:#f0f0f0;border:1px solid #ccc;text-align:center;">{a+b}</td>
        </tr>
        <tr>
          <td style="padding:10px;font-weight:600;background:#e8f4fd;border:1px solid #ccc;">Other Drugs</td>
          <td style="padding:10px;background:#ffffff;border:1px solid #ccc;text-align:center;">c = {c}</td>
          <td style="padding:10px;background:#ffffff;border:1px solid #ccc;text-align:center;">d = {d}</td>
          <td style="padding:10px;background:#f0f0f0;border:1px solid #ccc;text-align:center;">{c+d}</td>
        </tr>
        <tr>
          <td style="padding:10px;font-weight:600;background:#e8f4fd;border:1px solid #ccc;">Column Total</td>
          <td style="padding:10px;background:#f0f0f0;border:1px solid #ccc;text-align:center;">{a+c}</td>
          <td style="padding:10px;background:#f0f0f0;border:1px solid #ccc;text-align:center;">{b+d}</td>
          <td style="padding:10px;background:#d6eaf8;border:1px solid #ccc;text-align:center;font-weight:700;">{a+b+c+d}</td>
        </tr>
      </tbody>
    </table>
    """
    st.markdown(table_html, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Main render function (called from app.py)
# ══════════════════════════════════════════════════════════════════════════════

def render() -> None:

    # ── Page header ────────────────────────────────────────────────────────────
    st.markdown(
        """
        <h2 style="color:#0d3b66;">🔬 Drug Safety Signal Detection</h2>
        <p style="color:#555;font-size:1rem;">
            Identify potential drug safety signals from spontaneous adverse-event reports
            using statistical disproportionality analysis (PRR + chi-square screening).
        </p>
        <hr style="border:1px solid #d0e4f5;">
        """,
        unsafe_allow_html=True,
    )

    st.warning(
        "⚠️ **Pharmacovigilance screening tool only.** "
        "Results indicate statistical disproportionality in the uploaded dataset "
        "and do NOT establish a causal relationship between a drug and an adverse event. "
        "All findings must be reviewed by a qualified pharmacovigilance professional.",
        icon=None,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 1 — Upload Data
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    _section("📂 1. Upload Data")

    # Demo data download
    with open("data/demo_adverse_events.csv", "rb") as f:
        demo_bytes = f.read()

    col_dl, col_spacer = st.columns([2, 5])
    with col_dl:
        st.download_button(
            label="⬇️ Download Demo Dataset",
            data=demo_bytes,
            file_name="demo_adverse_events.csv",
            mime="text/csv",
            help="Download a synthetic demo dataset to test the module.",
        )

    st.caption(
        "🔬 Demo dataset is **synthetic demonstration data — not real patient data.** "
        "Contains 100 fictitious adverse-event reports for 9 common drugs."
    )

    st.markdown("")
    uploaded_file = st.file_uploader(
        "Upload your adverse-event CSV file",
        type=["csv"],
        help="Required columns: Drug, Adverse_Event. Optional: Patient_ID, Age, Sex, Seriousness",
    )

    # ── Load data ──────────────────────────────────────────────────────────────
    if uploaded_file is None:
        st.info("👆 Upload a CSV file above to begin, or download the demo dataset first.")
        st.markdown(FOOTER_HTML, unsafe_allow_html=True)
        return

    try:
        df = pd.read_csv(uploaded_file)
    except Exception as exc:
        st.error(f"Could not read the CSV file: {exc}")
        return

    # Strip whitespace from column names and string values
    df.columns = df.columns.str.strip()
    for col in ["Drug", "Adverse_Event"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # ── Validate ───────────────────────────────────────────────────────────────
    errors = validate_dataframe(df)
    if errors:
        for err in errors:
            st.error(err)
        st.markdown("**Expected CSV format:**")
        st.code("Patient_ID,Drug,Adverse_Event,Age,Sex,Seriousness\nP001,Atorvastatin,Myopathy,58,M,Yes", language="csv")
        return

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 2 — Dataset Overview
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    _section("📊 2. Dataset Overview")

    total_reports  = len(df)
    unique_drugs   = df["Drug"].nunique()
    unique_events  = df["Adverse_Event"].nunique()

    c1, c2, c3 = st.columns(3)
    c1.markdown(_info_box("Total Reports",          str(total_reports)), unsafe_allow_html=True)
    c2.markdown(_info_box("Unique Drugs",           str(unique_drugs),   "#1a6eb5"), unsafe_allow_html=True)
    c3.markdown(_info_box("Unique Adverse Events",  str(unique_events),  "#2e7d32"), unsafe_allow_html=True)

    st.markdown("")
    with st.expander("🔍 View uploaded data table"):
        st.dataframe(df, use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3 — Drug / Event Selection
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    _section("🎯 3. Drug / Event Selection")
    st.markdown(
        "Select a drug and an adverse event to compute the 2×2 contingency table and PRR."
    )

    drug_list  = sorted(df["Drug"].unique().tolist())
    event_list = sorted(df["Adverse_Event"].unique().tolist())

    sel_col1, sel_col2 = st.columns(2)
    with sel_col1:
        selected_drug = st.selectbox("Select Drug", drug_list)
    with sel_col2:
        selected_event = st.selectbox("Select Adverse Event", event_list)

    ct = build_contingency(df, selected_drug, selected_event)
    a, b, c, d = ct["a"], ct["b"], ct["c"], ct["d"]

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 4 — 2×2 Contingency Table
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    _section("🔢 4. 2×2 Contingency Table")

    _render_contingency_table(a, b, c, d, selected_drug, selected_event)

    st.markdown("")
    st.markdown(
        "<small style='color:#666;'>"
        "<b>a</b> = reports with selected drug <em>and</em> selected adverse event &nbsp;|&nbsp; "
        "<b>b</b> = reports with selected drug and <em>other</em> adverse events &nbsp;|&nbsp; "
        "<b>c</b> = reports with <em>other</em> drugs and selected adverse event &nbsp;|&nbsp; "
        "<b>d</b> = reports with other drugs and other adverse events"
        "</small>",
        unsafe_allow_html=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 5 — PRR Analysis
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    _section("📐 5. PRR Analysis")

    prr  = calculate_prr(a, b, c, d)
    chi2 = calculate_chi2(a, b, c, d)
    signal = meets_screening_criteria(a, prr, chi2)

    # Metric display
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("PRR",        f"{prr:.3f}"  if prr  is not None else "N/A")
    m2.metric("Chi-Square", f"{chi2:.3f}" if chi2 is not None else "N/A")
    m3.metric("Count (a)",  str(a))
    m4.metric(
        "Signal Status",
        "⚠️ Potential Signal" if signal else ("✅ No Signal" if prr is not None else "—")
    )

    # Screening criteria table
    st.markdown("")
    crit_rows = [
        ("PRR ≥ 2",    f"{prr:.3f}"  if prr  is not None else "N/A", prr  is not None and prr  >= PRR_THRESHOLD),
        ("a ≥ 3",      str(a),                                         a   >= COUNT_THRESHOLD),
        ("χ² ≥ 4",    f"{chi2:.3f}" if chi2 is not None else "N/A", chi2 is not None and chi2 >= CHI2_THRESHOLD),
    ]

    crit_html = """
    <table style="border-collapse:collapse;width:60%;font-size:0.9rem;margin-top:8px;">
      <thead>
        <tr>
          <th style="padding:8px 14px;background:#0d3b66;color:#fff;border:1px solid #ccc;text-align:left;">Criterion</th>
          <th style="padding:8px 14px;background:#0d3b66;color:#fff;border:1px solid #ccc;text-align:center;">Observed</th>
          <th style="padding:8px 14px;background:#0d3b66;color:#fff;border:1px solid #ccc;text-align:center;">Met?</th>
        </tr>
      </thead>
      <tbody>
    """
    for criterion, observed, met in crit_rows:
        tick  = "✅" if met else "❌"
        bg    = "#e8f5e9" if met else "#fff3f3"
        crit_html += (
            f'<tr style="background:{bg};">'
            f'<td style="padding:8px 14px;border:1px solid #ccc;">{criterion}</td>'
            f'<td style="padding:8px 14px;border:1px solid #ccc;text-align:center;">{observed}</td>'
            f'<td style="padding:8px 14px;border:1px solid #ccc;text-align:center;">{tick}</td>'
            f'</tr>'
        )
    crit_html += "</tbody></table>"
    st.markdown(crit_html, unsafe_allow_html=True)

    # Interpretation
    st.markdown("")
    if prr is None:
        st.info(
            "**PRR cannot be calculated** for this combination because one or more marginal counts "
            "are zero (not enough data). Try a different drug–event pair or upload a larger dataset."
        )
    elif signal:
        st.success(
            f"**Potential signal detected** for *{selected_drug}* → *{selected_event}*.  \n"
            f"This combination shows disproportionate reporting in the provided dataset based on "
            f"Evans (2001) screening criteria (PRR ≥ {PRR_THRESHOLD}, a ≥ {COUNT_THRESHOLD}, χ² ≥ {CHI2_THRESHOLD}).  \n\n"
            "This finding should be reviewed by a qualified pharmacovigilance professional. "
            "It does **not** establish a causal relationship between the drug and the adverse event."
        )
    else:
        st.info(
            f"**No signal detected** for *{selected_drug}* → *{selected_event}* "
            "under the current screening criteria. "
            "This does not exclude a clinically relevant safety concern — "
            "screening thresholds are one of several pharmacovigilance tools."
        )

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 6 — Automated Signal Detection
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    _section("🚨 6. Automated Signal Detection")

    st.markdown(
        "Click the button below to analyse **all** drug–adverse event combinations "
        f"in the uploaded dataset using Evans (2001) screening criteria "
        f"(PRR ≥ {PRR_THRESHOLD}, a ≥ {COUNT_THRESHOLD}, χ² ≥ {CHI2_THRESHOLD})."
    )

    if st.button("🔍 Detect Safety Signals", type="primary"):
        with st.spinner("Analysing all drug–event combinations…"):
            results_df = run_signal_sweep(df)

        st.session_state["signal_results"] = results_df

    # Show results if they exist in session state
    if "signal_results" in st.session_state:
        results_df = st.session_state["signal_results"]

        n_signals = int(results_df["Signal_Status"].str.startswith("⚠️").sum())
        n_total   = len(results_df)

        res_c1, res_c2 = st.columns(2)
        res_c1.markdown(
            _info_box("Drug–Event Pairs Analysed", str(n_total)),
            unsafe_allow_html=True,
        )
        res_c2.markdown(
            _info_box("Potential Signals Detected", str(n_signals), "#c0392b"),
            unsafe_allow_html=True,
        )

        st.markdown("")

        # Colour code the Signal_Status column
        def highlight_signal(val: str) -> str:
            if val.startswith("⚠️"):
                return "background-color:#fff3cd;color:#856404;font-weight:600;"
            return ""

        styled = results_df.style.map(highlight_signal, subset=["Signal_Status"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # CSV download of results
        csv_bytes = results_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download Results as CSV",
            data=csv_bytes,
            file_name="signal_detection_results.csv",
            mime="text/csv",
        )

        # ══════════════════════════════════════════════════════════════════════
        # SECTION 7 — Signal Visualisation
        # ══════════════════════════════════════════════════════════════════════
        st.markdown("---")
        _section("📈 7. Signal Visualisation")

        # Only plot pairs where PRR is available
        plot_df = results_df.dropna(subset=["PRR"]).copy()

        if plot_df.empty:
            st.info("No calculable PRR values available for visualisation.")
        else:
            # Take top 15 by PRR
            top_n = min(15, len(plot_df))
            top_df = plot_df.head(top_n).copy()
            top_df["Label"] = top_df["Drug"] + " → " + top_df["Adverse_Event"]

            # Build a simple Streamlit bar chart via st.bar_chart
            # (uses Altair internally — no extra import needed)
            chart_data = (
                top_df[["Label", "PRR"]]
                .set_index("Label")
                .sort_values("PRR", ascending=True)   # ascending so longest bar is on top
            )

            st.markdown(
                f"**Top {top_n} Drug–Event Pairs by PRR** "
                f"<span style='font-size:0.85rem;color:#666;'>"
                f"(dashed line at PRR = {PRR_THRESHOLD} — screening threshold)</span>",
                unsafe_allow_html=True,
            )

            st.bar_chart(chart_data, use_container_width=True, height=420)

            st.caption(
                f"Horizontal dashed threshold line (PRR = {PRR_THRESHOLD}) is a reference — "
                "pairs above it are not automatically signals unless ALL three criteria are met."
            )

            # ── Interpretation section ─────────────────────────────────────
            st.markdown("---")
            _section("📝 8. Interpretation")

            signal_rows = results_df[results_df["Signal_Status"].str.startswith("⚠️")]

            if signal_rows.empty:
                st.info(
                    "No drug–event combinations met all three screening criteria in the uploaded dataset.  \n"
                    "Consider uploading a larger dataset or adjusting the screening thresholds."
                )
            else:
                st.markdown(
                    "The following combinations met **all three** Evans (2001) screening criteria "
                    "and are flagged as **potential signals**:"
                )
                for _, row in signal_rows.iterrows():
                    with st.expander(
                        f"⚠️ {row['Drug']} → {row['Adverse_Event']}  "
                        f"(PRR = {row['PRR']}, a = {row['a']})"
                    ):
                        st.markdown(
                            f"**Drug:** {row['Drug']}  \n"
                            f"**Adverse Event:** {row['Adverse_Event']}  \n"
                            f"**Reports (a):** {row['a']}  \n"
                            f"**PRR:** {row['PRR']}  \n"
                            f"**Chi-Square:** {row['Chi_Square']}  \n\n"
                            "---\n"
                            f"This combination shows disproportionate reporting in the provided dataset "
                            f"based on Evans (2001) statistical screening criteria "
                            f"(PRR ≥ {PRR_THRESHOLD}, a ≥ {COUNT_THRESHOLD}, χ² ≥ {CHI2_THRESHOLD}).  \n\n"
                            "**This finding should be reviewed by a pharmacovigilance professional "
                            "and does not establish a causal relationship between the drug and the adverse event.**  \n\n"
                            "Next steps typically include: causality assessment, literature review, "
                            "benefit–risk evaluation, and regulatory reporting if applicable."
                        )

    # ── Footer ─────────────────────────────────────────────────────────────────
    st.markdown(FOOTER_HTML, unsafe_allow_html=True)
