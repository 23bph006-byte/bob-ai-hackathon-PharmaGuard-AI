"""
Regulatory Submission Readiness Checker — PharmaGuard AI
=========================================================
Implements:
  - Built-in ICH CTD (Modules 1–5) checklist
  - Interactive Present / Missing / Not Applicable marking
  - CSV checklist upload and validation
  - Readiness percentage calculation (excluding N/A items)
  - Module-wise readiness breakdown
  - Missing-document identification and grouping
  - Automated contextual recommendations
  - Bar chart visualisation by module

Regulatory note
---------------
This tool implements the ICH M4 Common Technical Document (CTD) structure.
Module 1 is region-specific (not part of the common CTD).
Modules 2–5 form the internationally harmonised CTD.

DISCLAIMER: This prototype provides an educational CTD/eCTD readiness screening
based on the checklist supplied by the user. It does not constitute regulatory
advice, official dossier validation, or a determination of submission acceptance.
Requirements vary by regulatory authority, product type, and submission pathway.
"""

import io

import pandas as pd
import streamlit as st

# ── Constants ──────────────────────────────────────────────────────────────────

STATUS_PRESENT  = "Present"
STATUS_MISSING  = "Missing"
STATUS_NA       = "Not Applicable"
VALID_STATUSES  = {STATUS_PRESENT, STATUS_MISSING, STATUS_NA}

FOOTER_HTML = """
<div class="app-footer">
    Prototype developed for <strong>IBM BoB AI Innovation Hackathon 2026</strong>
    &nbsp;|&nbsp; Problem Statement P2 — Drug Safety Signal Detector &amp; Regulatory Submission Readiness Checker
</div>
"""

# ── Recommendations map ────────────────────────────────────────────────────────
# Maps a fragment of the document name (lowercase) to a recommendation string.
RECOMMENDATIONS: dict[str, str] = {
    "application form":               "Complete and submit the required application form for the target regulatory authority.",
    "prescribing information":        "Prepare the Summary of Product Characteristics (SmPC) or Prescribing Information in the authority-specific format.",
    "labelling":                      "Provide specimen labelling including all required text, symbols, and barcodes per local requirements.",
    "administrative":                 "Include all required administrative documents such as cover letters, authorisation letters, and fee schedules.",
    "quality overall summary":        "Prepare the Quality Overall Summary (QOS) in line with ICH M4Q guidance.",
    "nonclinical overview":           "Prepare a concise integrated nonclinical overview summarising pharmacology, PK, and toxicology findings.",
    "clinical overview":              "Prepare a Clinical Overview summarising the benefit–risk profile of the product.",
    "nonclinical written":            "Prepare nonclinical written and tabulated summaries for pharmacology, PK, and toxicology study reports.",
    "clinical summary":               "Prepare a detailed Clinical Summary of all clinical data in Modules 5.2–5.6.",
    "drug substance":                 "Include complete drug substance information: description, manufacture, characterisation, and control.",
    "drug product":                   "Include drug product information: composition, manufacture, control of excipients, and finished product specifications.",
    "manufacturing process":          "Document the complete manufacturing process description, process controls, and batch records.",
    "control of materials":           "List all raw materials, starting materials, reagents, and solvents with specifications and sourcing.",
    "process validation":             "Provide process validation and/or evaluation data demonstrating consistent manufacture.",
    "specifications":                 "Define specifications for the drug substance and drug product with justification of limits.",
    "analytical procedures":          "Include validated analytical procedures used for testing the drug substance and drug product.",
    "stability data":                 "Provide stability data supporting the proposed shelf life and storage conditions per ICH Q1A(R2).",
    "pharmacology":                   "Include all relevant pharmacology study reports (primary, secondary, safety pharmacology).",
    "pharmacokinetic":                "Include pharmacokinetic study reports covering absorption, distribution, metabolism, and excretion.",
    "toxicology":                     "Include toxicology study reports (single-dose, repeat-dose) required for the target clinical indication.",
    "genotoxicity":                   "Include genotoxicity studies (Ames test, chromosomal aberration, in vivo micronucleus) if applicable.",
    "reproductive":                   "Include reproductive and developmental toxicity studies if required for the target population.",
    "clinical pharmacology":          "Include clinical pharmacology reports (PK in humans, PD, drug-drug interaction studies).",
    "bioavailability":                "Include bioavailability and/or bioequivalence study reports as required by the submission type.",
    "efficacy":                       "Include all controlled clinical trial reports demonstrating efficacy for the intended indication.",
    "safety study":                   "Include integrated safety study reports, including adverse event data and safety surveillance reports.",
    "literature":                     "Compile relevant published literature references in required format (e.g. ICH M4E).",
}

# ══════════════════════════════════════════════════════════════════════════════
# CTD checklist definition
# ══════════════════════════════════════════════════════════════════════════════

def get_ctd_checklist() -> list[dict]:
    """
    Return the built-in ICH CTD checklist as a list of dicts.
    Each item has keys: Module, Document, Default_Status
    """
    items = [
        # Module 1 — Administrative (region-specific)
        ("Module 1", "Application form"),
        ("Module 1", "Prescribing information (SmPC/PI)"),
        ("Module 1", "Labelling information"),
        ("Module 1", "Administrative documents"),
        # Module 2 — CTD Summaries
        ("Module 2", "Quality Overall Summary (QOS)"),
        ("Module 2", "Nonclinical Overview"),
        ("Module 2", "Clinical Overview"),
        ("Module 2", "Nonclinical written and tabulated summaries"),
        ("Module 2", "Clinical Summary"),
        # Module 3 — Quality
        ("Module 3", "Drug substance (active pharmaceutical ingredient) information"),
        ("Module 3", "Drug product (finished dosage form) information"),
        ("Module 3", "Manufacturing process description"),
        ("Module 3", "Control of materials"),
        ("Module 3", "Process validation data"),
        ("Module 3", "Specifications (drug substance)"),
        ("Module 3", "Specifications (drug product)"),
        ("Module 3", "Analytical procedures and validation"),
        ("Module 3", "Stability data (drug substance)"),
        ("Module 3", "Stability data (drug product)"),
        # Module 4 — Nonclinical
        ("Module 4", "Pharmacology studies"),
        ("Module 4", "Pharmacokinetic studies"),
        ("Module 4", "Toxicology studies (single dose)"),
        ("Module 4", "Toxicology studies (repeat dose)"),
        ("Module 4", "Genotoxicity studies"),
        ("Module 4", "Reproductive toxicity studies"),
        # Module 5 — Clinical
        ("Module 5", "Clinical pharmacology reports"),
        ("Module 5", "Bioavailability and bioequivalence studies"),
        ("Module 5", "Efficacy study reports"),
        ("Module 5", "Safety study reports"),
        ("Module 5", "Literature references"),
    ]
    return [{"Module": m, "Document": d} for m, d in items]


# ══════════════════════════════════════════════════════════════════════════════
# Pure calculation functions
# ══════════════════════════════════════════════════════════════════════════════

def validate_csv(df: pd.DataFrame) -> list[str]:
    """Return validation error strings. Empty list = valid."""
    errors = []
    required = {"Module", "Document", "Status"}
    missing = required - set(df.columns)
    if missing:
        errors.append(f"Missing required column(s): **{', '.join(sorted(missing))}**")
        return errors
    if df.empty:
        errors.append("The uploaded file contains no data rows.")
        return errors
    invalid = set(df["Status"].str.strip().unique()) - VALID_STATUSES
    if invalid:
        errors.append(
            f"Invalid Status values found: **{', '.join(sorted(invalid))}**.  \n"
            f"Allowed values are: `Present`, `Missing`, `Not Applicable`"
        )
    return errors


def calculate_readiness(df: pd.DataFrame) -> dict:
    """
    Calculate overall readiness score, excluding N/A items.

    Returns dict with keys:
      score_pct, present, missing, not_applicable, total_applicable
    """
    applicable = df[df["Status"] != STATUS_NA]
    present    = int((applicable["Status"] == STATUS_PRESENT).sum())
    missing    = int((applicable["Status"] == STATUS_MISSING).sum())
    total_app  = len(applicable)
    not_app    = int((df["Status"] == STATUS_NA).sum())
    score      = (present / total_app * 100) if total_app > 0 else 0.0

    return {
        "score_pct":      round(score, 1),
        "present":        present,
        "missing":        missing,
        "not_applicable": not_app,
        "total_applicable": total_app,
    }


def module_wise_readiness(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a DataFrame with per-module readiness percentages.

    Columns: Module, Present, Missing, Not_Applicable, Total_Applicable, Readiness_Pct
    """
    rows = []
    for module in sorted(df["Module"].unique()):
        sub = df[df["Module"] == module]
        app = sub[sub["Status"] != STATUS_NA]
        pres = int((app["Status"] == STATUS_PRESENT).sum())
        miss = int((app["Status"] == STATUS_MISSING).sum())
        na   = int((sub["Status"] == STATUS_NA).sum())
        tot  = len(app)
        pct  = round(pres / tot * 100, 1) if tot > 0 else 0.0
        rows.append({
            "Module":           module,
            "Present":          pres,
            "Missing":          miss,
            "Not_Applicable":   na,
            "Total_Applicable": tot,
            "Readiness_Pct":    pct,
        })
    return pd.DataFrame(rows)


def get_missing_items(df: pd.DataFrame) -> pd.DataFrame:
    """Return only rows where Status == Missing."""
    return df[df["Status"] == STATUS_MISSING].copy().reset_index(drop=True)


def generate_recommendation(document: str) -> str:
    """
    Look up a recommendation for the given document name.
    Falls back to a generic recommendation if no specific match is found.
    """
    doc_lower = document.lower()
    # Sort by keyword length descending so more specific keys match before shorter ones
    # e.g. "stability data" matches before "drug product" for "Stability data (drug product)"
    for keyword, recommendation in sorted(RECOMMENDATIONS.items(), key=lambda kv: len(kv[0]), reverse=True):
        if keyword in doc_lower:
            return recommendation
    return (
        f"Review the documentation requirements for '{document}' "
        "with reference to ICH M4 guidelines and target authority requirements."
    )


def build_analysis_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build the full section-wise analysis table with Recommendation column.
    """
    out = df.copy()
    out["Recommendation"] = out.apply(
        lambda r: generate_recommendation(r["Document"])
        if r["Status"] == STATUS_MISSING
        else ("—" if r["Status"] == STATUS_PRESENT else "Not required for this submission"),
        axis=1,
    )
    return out


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


def _score_box(score: float) -> str:
    if score >= 90:
        colour, label = "#2e7d32", "High Readiness"
    elif score >= 75:
        colour, label = "#e67e00", "Moderate Readiness"
    else:
        colour, label = "#c0392b", "Needs Attention"

    return (
        f'<div style="background:#f7f8fa;border:2px solid {colour};border-radius:12px;'
        f'padding:28px 24px;text-align:center;max-width:320px;margin:0 auto;">'
        f'<div style="font-size:3rem;font-weight:800;color:{colour};">{score}%</div>'
        f'<div style="font-size:1.1rem;font-weight:600;color:{colour};margin-top:4px;">{label}</div>'
        f'<div style="font-size:0.8rem;color:#888;margin-top:8px;">Prototype readiness score — not an official regulatory determination</div>'
        f'</div>'
    )


def _status_badge(status: str) -> str:
    if status == STATUS_PRESENT:
        return '<span style="background:#e8f5e9;color:#2e7d32;padding:2px 10px;border-radius:12px;font-size:0.82rem;font-weight:600;">✅ Present</span>'
    if status == STATUS_MISSING:
        return '<span style="background:#fff3cd;color:#856404;padding:2px 10px;border-radius:12px;font-size:0.82rem;font-weight:600;">⚠️ Missing</span>'
    return '<span style="background:#f0f0f0;color:#555;padding:2px 10px;border-radius:12px;font-size:0.82rem;font-weight:600;">— N/A</span>'


# ══════════════════════════════════════════════════════════════════════════════
# Interactive checklist builder
# ══════════════════════════════════════════════════════════════════════════════

def _render_interactive_checklist() -> pd.DataFrame | None:
    """
    Render the interactive Module-by-Module checklist.
    Returns a DataFrame with Module, Document, Status columns,
    or None if the user has not interacted yet.
    """
    checklist = get_ctd_checklist()
    rows = []

    modules = sorted(set(item["Module"] for item in checklist))
    module_labels = {
        "Module 1": "Module 1 — Administrative & Prescribing Information *(region-specific)*",
        "Module 2": "Module 2 — CTD Summaries",
        "Module 3": "Module 3 — Quality",
        "Module 4": "Module 4 — Nonclinical Study Reports",
        "Module 5": "Module 5 — Clinical Study Reports",
    }

    for module in modules:
        with st.expander(module_labels.get(module, module), expanded=(module == "Module 1")):
            module_items = [i for i in checklist if i["Module"] == module]
            for item in module_items:
                doc   = item["Document"]
                key   = f"checklist_{module}_{doc}"
                # Use a unique session-state-friendly key
                status = st.radio(
                    doc,
                    options=[STATUS_PRESENT, STATUS_MISSING, STATUS_NA],
                    index=1,              # default: Missing
                    horizontal=True,
                    key=key,
                )
                rows.append({"Module": module, "Document": doc, "Status": status})

    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# Results rendering
# ══════════════════════════════════════════════════════════════════════════════

def _render_results(df: pd.DataFrame) -> None:
    """Render all result sections for a given checklist DataFrame."""

    # ── Readiness Score ────────────────────────────────────────────────────────
    st.markdown("---")
    _section("🎯 4. Readiness Score")

    stats = calculate_readiness(df)

    st.markdown(_score_box(stats["score_pct"]), unsafe_allow_html=True)
    st.markdown("")

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(_info_box("Present",          str(stats["present"]),          "#2e7d32"), unsafe_allow_html=True)
    c2.markdown(_info_box("Missing",          str(stats["missing"]),          "#c0392b"), unsafe_allow_html=True)
    c3.markdown(_info_box("Not Applicable",   str(stats["not_applicable"]),   "#555"),    unsafe_allow_html=True)
    c4.markdown(_info_box("Total Applicable", str(stats["total_applicable"]), "#0d3b66"), unsafe_allow_html=True)

    # ── Module-wise Readiness ──────────────────────────────────────────────────
    st.markdown("---")
    _section("📊 5. Module-wise Readiness")

    mod_df = module_wise_readiness(df)

    # Bar chart
    chart_data = mod_df[["Module", "Readiness_Pct"]].set_index("Module")
    st.bar_chart(chart_data, use_container_width=True, height=300)

    # Table
    display_mod = mod_df.rename(columns={
        "Present":          "✅ Present",
        "Missing":          "⚠️ Missing",
        "Not_Applicable":   "— N/A",
        "Total_Applicable": "Applicable Total",
        "Readiness_Pct":    "Readiness %",
    })
    st.dataframe(display_mod, use_container_width=True, hide_index=True)

    # ── Section-wise Analysis Table ────────────────────────────────────────────
    st.markdown("---")
    _section("📋 6. Section-wise Analysis")

    analysis = build_analysis_table(df)

    # Style the Status column
    def _style_status(val: str) -> str:
        if val == STATUS_PRESENT:
            return "background-color:#e8f5e9;color:#2e7d32;"
        if val == STATUS_MISSING:
            return "background-color:#fff3cd;color:#856404;font-weight:600;"
        return "color:#888;"

    styled = analysis.style.map(_style_status, subset=["Status"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # ── Missing / Attention Required ───────────────────────────────────────────
    st.markdown("---")
    _section("🚨 7. Missing / Attention Required")

    missing_df = get_missing_items(df)

    if missing_df.empty:
        st.success(
            "✅ No missing items detected in the current checklist. "
            "Verify that all documents are complete and review with your regulatory affairs team before submission."
        )
    else:
        st.warning(
            f"**{len(missing_df)} item(s) require attention.** "
            "Items marked 'Missing' are grouped by CTD module below."
        )
        for module in sorted(missing_df["Module"].unique()):
            mod_missing = missing_df[missing_df["Module"] == module]
            st.markdown(f"**{module}**")
            for _, row in mod_missing.iterrows():
                st.markdown(f"- ⚠️ {row['Document']}")
            st.markdown("")

    # ── Recommendations ────────────────────────────────────────────────────────
    st.markdown("---")
    _section("💡 8. Recommendations")

    if missing_df.empty:
        st.info(
            "No specific recommendations — no missing items identified. "
            "Ensure all documents are complete, current, and in the required format for your target authority."
        )
    else:
        st.markdown(
            "The following recommendations are generated based on the missing items in your checklist. "
            "These are **general educational suggestions only** and do not constitute regulatory advice."
        )
        for _, row in missing_df.iterrows():
            rec = generate_recommendation(row["Document"])
            with st.expander(f"⚠️ {row['Module']} — {row['Document']}"):
                st.markdown(f"📌 {rec}")

    # ── Download full analysis ─────────────────────────────────────────────────
    st.markdown("")
    csv_out = analysis.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download Full Analysis as CSV",
        data=csv_out,
        file_name="ctd_readiness_analysis.csv",
        mime="text/csv",
    )


# ══════════════════════════════════════════════════════════════════════════════
# Main render function (called from app.py)
# ══════════════════════════════════════════════════════════════════════════════

def render() -> None:

    # ── Page header ────────────────────────────────────────────────────────────
    st.markdown(
        """
        <h2 style="color:#0d3b66;">📋 Regulatory Submission Readiness Checker</h2>
        <p style="color:#555;font-size:1rem;">
            Assess the completeness of your CTD/eCTD regulatory dossier against the
            ICH M4 Common Technical Document structure.
        </p>
        <hr style="border:1px solid #d0e4f5;">
        """,
        unsafe_allow_html=True,
    )

    # ── Prominent disclaimer ───────────────────────────────────────────────────
    st.warning(
        "**Disclaimer:** This prototype provides an educational CTD/eCTD readiness screening "
        "based on the checklist supplied by the user. It does **not** constitute regulatory advice, "
        "official dossier validation, or a determination of submission acceptance. "
        "Requirements vary by regulatory authority, product type, and submission pathway.",
        icon=None,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 1 — Submission Type / Basic Information
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    _section("📝 1. Submission Information")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        submission_type = st.selectbox(
            "Submission Type",
            ["New Drug Application (NDA)", "Abbreviated NDA (ANDA)", "Marketing Authorisation Application (MAA)",
             "New Drug Submission (NDS)", "Investigational New Drug (IND)", "Other"],
        )
    with col_b:
        authority = st.selectbox(
            "Target Regulatory Authority",
            ["FDA (USA)", "EMA (European Union)", "CDSCO (India)", "MHRA (UK)",
             "Health Canada", "TGA (Australia)", "WHO Prequalification", "Other"],
        )
    with col_c:
        product_name = st.text_input("Product / Drug Name (optional)", placeholder="e.g. Amoxicillin 500 mg Capsules")

    st.markdown(
        "<div style='background:#eaf3fb;border-left:4px solid #1a6eb5;padding:12px 16px;"
        "border-radius:0 6px 6px 0;font-size:0.9rem;color:#333;margin-top:8px;'>"
        "<strong>About the CTD structure:</strong> The ICH M4 Common Technical Document (CTD) "
        "is an internationally harmonised format for regulatory submissions. "
        "<strong>Module 1</strong> is region-specific (administrative documents). "
        "<strong>Modules 2–5</strong> are the common international CTD covering summaries, "
        "quality, nonclinical, and clinical information respectively."
        "</div>",
        unsafe_allow_html=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 2 — Choose input method
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    _section("🗂️ 2. Checklist Input Method")

    method = st.radio(
        "How would you like to provide your checklist?",
        ["Option A — Interactive Checklist", "Option B — Upload CSV Checklist"],
        horizontal=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # OPTION A — Interactive Checklist
    # ══════════════════════════════════════════════════════════════════════════
    if method == "Option A — Interactive Checklist":

        st.markdown("---")
        _section("✅ 3. CTD Checklist")

        st.markdown(
            "For each document below, select **Present**, **Missing**, or **Not Applicable**.  \n"
            "Items marked **Not Applicable** are excluded from the readiness score calculation."
        )
        st.caption(
            "⚠️ This is a prototype readiness checklist, not a complete regulatory submission requirements list."
        )

        st.markdown("")
        checklist_df = _render_interactive_checklist()

        st.markdown("")
        if st.button("📊 Calculate Readiness Score", type="primary"):
            st.session_state["readiness_df"]     = checklist_df
            st.session_state["readiness_source"] = "interactive"

    # ══════════════════════════════════════════════════════════════════════════
    # OPTION B — CSV Upload
    # ══════════════════════════════════════════════════════════════════════════
    else:
        st.markdown("---")
        _section("📂 3. Upload Checklist CSV")

        # Demo download
        with open("data/demo_ctd_checklist.csv", "rb") as f:
            demo_bytes = f.read()

        col_dl, _ = st.columns([2, 5])
        with col_dl:
            st.download_button(
                "⬇️ Download Demo Checklist CSV",
                data=demo_bytes,
                file_name="demo_ctd_checklist.csv",
                mime="text/csv",
                help="Download a synthetic demo checklist to test the module.",
            )

        st.caption(
            "📄 Demo checklist is **synthetic demonstration data — not a real submission record.** "
            "Required columns: `Module`, `Document`, `Status`  \n"
            f"Allowed Status values: `{STATUS_PRESENT}` · `{STATUS_MISSING}` · `{STATUS_NA}`"
        )

        st.markdown("")
        uploaded = st.file_uploader(
            "Upload your CTD checklist CSV",
            type=["csv"],
            help="CSV must contain columns: Module, Document, Status",
        )

        if uploaded is None:
            st.info("👆 Upload a checklist CSV above, or download the demo file first.")
            st.markdown(FOOTER_HTML, unsafe_allow_html=True)
            return

        try:
            csv_df = pd.read_csv(uploaded)
        except Exception as exc:
            st.error(f"Could not read the CSV file: {exc}")
            return

        # Normalise
        csv_df.columns = csv_df.columns.str.strip()
        for col in ["Module", "Document", "Status"]:
            if col in csv_df.columns:
                csv_df[col] = csv_df[col].astype(str).str.strip()

        errs = validate_csv(csv_df)
        if errs:
            for e in errs:
                st.error(e)
            st.markdown(
                "**Expected CSV format:**\n"
                "```\nModule,Document,Status\n"
                "Module 1,Application form,Present\n"
                "Module 3,Stability data (drug product),Missing\n"
                "Module 4,Genotoxicity studies,Not Applicable\n```"
            )
            return

        st.success(f"✅ Checklist loaded: {len(csv_df)} items across {csv_df['Module'].nunique()} modules.")
        st.session_state["readiness_df"]     = csv_df
        st.session_state["readiness_source"] = "csv"

    # ══════════════════════════════════════════════════════════════════════════
    # Results — shown whenever readiness_df is in session state
    # ══════════════════════════════════════════════════════════════════════════
    if "readiness_df" in st.session_state:
        _render_results(st.session_state["readiness_df"])

    # ── Footer ─────────────────────────────────────────────────────────────────
    st.markdown(FOOTER_HTML, unsafe_allow_html=True)
