"""
AI Copilot — PharmaGuard AI
============================
Context-aware AI assistant that interprets results produced by the two existing
PharmaGuard AI modules (Drug Safety Signal Detection and Regulatory Submission
Readiness) and provides understandable explanations, prioritisation, and
executive summaries.

AI Provider strategy
--------------------
The copilot tries providers in this order:
  1. IBM watsonx.ai  — if WATSONX_API_KEY + WATSONX_PROJECT_ID env vars are set
  2. OpenAI          — if OPENAI_API_KEY env var is set
  3. Rule-based fallback — always available, clearly labelled

No API key is ever hard-coded. All credentials come from environment variables
(or Streamlit secrets). The app runs fully offline in fallback mode.

Fallback mode
-------------
The fallback engine reads the actual numeric results from session_state and
produces deterministic, template-based text explanations — it does NOT pretend
to be an LLM.

DISCLAIMER
----------
AI-generated content is for educational and analytical assistance only.
It does not establish causality, replace pharmacovigilance expert review,
provide medical advice, or constitute regulatory advice.
"""

import os
import textwrap

import pandas as pd
import streamlit as st

# ── Constants ──────────────────────────────────────────────────────────────────

FOOTER_HTML = """
<div class="app-footer">
    Prototype developed for <strong>IBM BoB AI Innovation Hackathon 2026</strong>
    &nbsp;|&nbsp; Problem Statement P2 — Drug Safety Signal Detector &amp; Regulatory Submission Readiness Checker
</div>
"""

DISCLAIMER = (
    "⚠️ **AI Disclaimer:** AI-generated content is for educational and analytical assistance only. "
    "It does **not** establish causality, replace pharmacovigilance expert review, "
    "provide medical advice, or constitute regulatory advice."
)

SUGGESTED_QUESTIONS = [
    "Summarise the current safety signal analysis.",
    "Which safety signal should be reviewed first?",
    "Explain the PRR result in simple terms.",
    "Why was the top signal flagged?",
    "Summarise the regulatory readiness assessment.",
    "What are the most important CTD gaps?",
    "Which regulatory gaps should be addressed first?",
    "What does the PRR value tell us about drug safety?",
]


# ══════════════════════════════════════════════════════════════════════════════
# Context builders — read session_state populated by the other two modules
# ══════════════════════════════════════════════════════════════════════════════

def build_safety_context() -> dict | None:
    """
    Build a structured safety context dict from signal_results in session_state.
    Returns None if no signal analysis has been run yet.
    """
    if "signal_results" not in st.session_state:
        return None

    df: pd.DataFrame = st.session_state["signal_results"].copy()

    signals = df[df["Signal_Status"].str.startswith("⚠️")].copy()
    no_signal = df[~df["Signal_Status"].str.startswith("⚠️")].copy()

    top_signals = (
        signals.dropna(subset=["PRR"])
        .sort_values("PRR", ascending=False)
        .head(5)
        .to_dict(orient="records")
    )

    return {
        "total_pairs":      len(df),
        "n_signals":        len(signals),
        "n_no_signal":      len(no_signal),
        "top_signals":      top_signals,
        "all_signals":      signals.to_dict(orient="records"),
        "df":               df,
    }


def build_regulatory_context() -> dict | None:
    """
    Build a structured regulatory context dict from readiness_df in session_state.
    Returns None if no readiness assessment has been run yet.
    """
    if "readiness_df" not in st.session_state:
        return None

    from pages.submission_readiness import (
        calculate_readiness,
        module_wise_readiness,
        get_missing_items,
        STATUS_MISSING,
    )

    df: pd.DataFrame = st.session_state["readiness_df"].copy()
    stats   = calculate_readiness(df)
    mod_df  = module_wise_readiness(df)
    missing = get_missing_items(df)

    # Group missing items by module
    missing_by_module: dict[str, list[str]] = {}
    for _, row in missing.iterrows():
        missing_by_module.setdefault(row["Module"], []).append(row["Document"])

    return {
        "score_pct":         stats["score_pct"],
        "present":           stats["present"],
        "missing":           stats["missing"],
        "not_applicable":    stats["not_applicable"],
        "total_applicable":  stats["total_applicable"],
        "module_df":         mod_df,
        "missing_by_module": missing_by_module,
        "missing_items":     missing.to_dict(orient="records"),
    }


def _readiness_label(score: float) -> str:
    if score >= 90:
        return "High Readiness"
    elif score >= 75:
        return "Moderate Readiness"
    return "Needs Attention"


# ══════════════════════════════════════════════════════════════════════════════
# Rule-based fallback engine
# ══════════════════════════════════════════════════════════════════════════════

def _fallback_safety_summary(ctx: dict) -> str:
    lines = [
        "**Drug Safety Signal Analysis — Summary**",
        "",
        f"- **Drug–event pairs analysed:** {ctx['total_pairs']}",
        f"- **Potential signals detected:** {ctx['n_signals']}",
        f"- **Pairs with no signal:** {ctx['n_no_signal']}",
        "",
    ]

    if ctx["n_signals"] == 0:
        lines.append(
            "No drug–event combinations in the current dataset met all three Evans (2001) "
            "screening criteria (PRR ≥ 2, a ≥ 3, χ² ≥ 4). "
            "This does not exclude clinically relevant safety concerns — "
            "disproportionality screening is one of several pharmacovigilance tools."
        )
    else:
        lines.append(f"**Top potential signals (sorted by PRR):**")
        lines.append("")
        for i, sig in enumerate(ctx["top_signals"], 1):
            lines.append(
                f"{i}. **{sig['Drug']}** → **{sig['Adverse_Event']}**  "
                f"(PRR = {sig['PRR']}, χ² = {sig['Chi_Square']}, a = {sig['a']})"
            )
        lines.append("")
        lines.append(
            "**Important limitations:**  \n"
            "- These results reflect statistical disproportionality within the uploaded dataset only.  \n"
            "- A potential signal does **not** establish a causal relationship.  \n"
            "- All signals require review by a qualified pharmacovigilance professional.  \n"
            "- The dataset is limited in size; real-world databases (FAERS, VigiBase) contain millions of reports."
        )
    return "\n".join(lines)


def _fallback_regulatory_summary(ctx: dict) -> str:
    label = _readiness_label(ctx["score_pct"])
    lines = [
        "**Regulatory Submission Readiness — Summary**",
        "",
        f"- **Overall readiness score:** {ctx['score_pct']}% — *{label}*",
        f"- **Present:** {ctx['present']}  |  **Missing:** {ctx['missing']}  |  **Not Applicable:** {ctx['not_applicable']}",
        f"- **Total applicable components:** {ctx['total_applicable']}",
        "",
        "**Module-wise readiness:**",
        "",
    ]

    mod_df = ctx["module_df"]
    for _, row in mod_df.iterrows():
        bar = "█" * int(row["Readiness_Pct"] / 10) + "░" * (10 - int(row["Readiness_Pct"] / 10))
        lines.append(f"- {row['Module']}: {row['Readiness_Pct']}% `{bar}`")

    lines.append("")
    if not ctx["missing_by_module"]:
        lines.append("✅ No missing items detected.")
    else:
        lines.append("**Missing components by module:**")
        lines.append("")
        for module, docs in sorted(ctx["missing_by_module"].items()):
            lines.append(f"*{module}:*")
            for doc in docs:
                lines.append(f"  - {doc}")
        lines.append("")
        lines.append(
            "**Important limitations:**  \n"
            "- This score is based solely on the checklist you provided and is not an official regulatory determination.  \n"
            "- Requirements vary by regulatory authority, product type, and submission pathway.  \n"
            "- Consult a qualified regulatory affairs professional before submission."
        )
    return "\n".join(lines)


def _fallback_top_signal_explanation(ctx: dict) -> str:
    if not ctx["top_signals"]:
        return "No potential signals were detected in the current dataset under the configured screening criteria."

    sig = ctx["top_signals"][0]
    drug, event = sig["Drug"], sig["Adverse_Event"]
    prr, chi2, a = sig["PRR"], sig["Chi_Square"], sig["a"]
    b, c, d = sig.get("b", "?"), sig.get("c", "?"), sig.get("d", "?")

    lines = [
        f"**Explanation: {drug} → {event}**",
        "",
        f"This drug–event combination shows the **highest PRR ({prr})** in the current dataset "
        f"and meets all three Evans (2001) screening criteria.",
        "",
        "**What the statistics mean:**",
        "",
        f"- **PRR = {prr}:** Among all reports in the dataset, the proportion that mention "
        f"*{event}* is approximately **{prr}× higher** for *{drug}* than for all other drugs combined. "
        f"A PRR ≥ 2 is the first screening threshold.",
        f"- **Chi-square = {chi2}:** This measures whether the association is statistically "
        f"unlikely to be due to chance alone. A value ≥ 4 (roughly equivalent to p < 0.05) "
        f"is the third criterion.",
        f"- **a = {a}:** There are {a} reports in the dataset containing both *{drug}* and "
        f"*{event}*. A minimum of 3 reports is required to consider a signal.",
        "",
        "**2×2 table:**",
        f"- a (drug + event) = {a}  |  b (drug + other events) = {b}",
        f"- c (other drugs + event) = {c}  |  d (other drugs + other events) = {d}",
        "",
        "**Interpretation:**",
        f"The combination *{drug}* → *{event}* shows **disproportionate reporting** "
        "in the analysed dataset based on the selected statistical screening criteria. "
        "This is a **potential safety signal** that warrants further pharmacovigilance assessment. "
        "**This finding does not establish a causal relationship** between the drug and the adverse event.",
    ]
    return "\n".join(lines)


def _fallback_signal_prioritisation(ctx: dict) -> str:
    if ctx["n_signals"] == 0:
        return "No potential signals detected — no prioritisation required."

    lines = [
        "**Signal Prioritisation (analytical aid — not a clinical risk assessment)**",
        "",
        "The following potential signals are ranked by PRR. "
        "Higher PRR and higher report count (a) are general indicators of stronger statistical association "
        "within this dataset. This is **not** a clinical severity ranking.",
        "",
    ]
    for i, sig in enumerate(ctx["all_signals"][:10], 1):
        prr_val = sig.get("PRR") or "N/A"
        chi2_val = sig.get("Chi_Square") or "N/A"
        lines.append(
            f"{i}. **{sig['Drug']}** → **{sig['Adverse_Event']}**  "
            f"| PRR = {prr_val} | χ² = {chi2_val} | Reports (a) = {sig['a']}"
        )

    lines += [
        "",
        "**Prioritisation considerations:**",
        "- Combinations with higher PRR and higher report counts (a) may be reviewed earlier.",
        "- Serious adverse events (if flagged in the dataset) should be reviewed promptly.",
        "- All signals require expert causality assessment — statistical screening is the first step only.",
    ]
    return "\n".join(lines)


def _fallback_ctd_priorities(ctx: dict) -> str:
    if not ctx["missing_by_module"]:
        return (
            "No missing items were identified in the current checklist. "
            "Review all items with your regulatory affairs team to confirm completeness."
        )

    # Simple heuristic: Module 3 (Quality) and Module 5 (Clinical) gaps are often
    # most time-consuming to resolve, so surface them first.
    PRIORITY_ORDER = ["Module 3", "Module 5", "Module 4", "Module 2", "Module 1"]

    lines = [
        "**CTD Gap Prioritisation (educational analytical aid only)**",
        "",
        f"There are **{ctx['missing']} missing item(s)** across "
        f"{len(ctx['missing_by_module'])} CTD module(s).",
        "",
        "The following areas are suggested for early review based on typical submission "
        "preparation timelines. Requirements vary by authority and product type — "
        "consult a regulatory affairs professional.",
        "",
    ]

    rank = 1
    # Show in priority order first
    for mod in PRIORITY_ORDER:
        if mod in ctx["missing_by_module"]:
            lines.append(f"**Priority {rank} — {mod}** (missing {len(ctx['missing_by_module'][mod])} item(s)):")
            for doc in ctx["missing_by_module"][mod]:
                lines.append(f"  - Consider reviewing: {doc}")
            lines.append("")
            rank += 1

    # Any modules not in the priority list
    for mod, docs in sorted(ctx["missing_by_module"].items()):
        if mod not in PRIORITY_ORDER:
            lines.append(f"**Priority {rank} — {mod}:**")
            for doc in docs:
                lines.append(f"  - Consider reviewing: {doc}")
            lines.append("")
            rank += 1

    lines.append(
        "_This prioritisation is a prototype analytical aid and does not constitute "
        "regulatory advice or guarantee submission acceptance._"
    )
    return "\n".join(lines)


def _fallback_explain_prr(ctx: dict) -> str:
    if not ctx["top_signals"]:
        return "No potential signals with calculable PRR values are available in the current dataset."

    sig = ctx["top_signals"][0]
    prr = sig["PRR"]
    lines = [
        "**What is PRR?**",
        "",
        "The **Proportional Reporting Ratio (PRR)** is a disproportionality measure used in "
        "spontaneous adverse-event signal detection (Evans et al., 2001; used by the EMA/MHRA).",
        "",
        "**Formula:**  `PRR = [a/(a+b)] / [c/(c+d)]`",
        "",
        "Where:  \n"
        "- `a` = reports with the drug of interest *and* the adverse event of interest  \n"
        "- `b` = reports with the drug of interest *and* other adverse events  \n"
        "- `c` = reports with other drugs *and* the adverse event of interest  \n"
        "- `d` = reports with other drugs *and* other adverse events",
        "",
        "**In plain language:**",
        "PRR compares how often an adverse event appears in reports about one drug versus "
        "how often it appears in reports about all other drugs in the database. "
        f"A PRR of **{prr}** for **{sig['Drug']} → {sig['Adverse_Event']}** means this adverse event "
        f"is reported approximately {prr}× more frequently for this drug than for the overall comparison group.",
        "",
        "**Screening threshold:**",
        "The Evans (2001) criterion requires PRR ≥ 2, ≥ 3 co-reports (a), and χ² ≥ 4 "
        "for a combination to be flagged as a potential signal.",
        "",
        "**Limitation:** PRR is sensitive to database size and composition. "
        "It does not account for confounding, indication bias, or reporting quality.",
    ]
    return "\n".join(lines)


def _fallback_combined_summary(s_ctx: dict | None, r_ctx: dict | None) -> str:
    """Kept for backward compatibility — delegates to the executive summary."""
    return _fallback_executive_summary(s_ctx, r_ctx)


def _fallback_executive_summary(s_ctx: dict | None, r_ctx: dict | None) -> str:
    """
    Purpose-built executive summary with four explicit sections:
      1. Drug Safety Overview
      2. Regulatory Readiness Overview
      3. Key Priorities
      4. Important Limitations

    Builds each section independently so a failure in one does not
    silently suppress the others. All data comes directly from the
    context dicts — nothing is invented.
    """
    sections: list[str] = []

    # ── Title ──────────────────────────────────────────────────────────────────
    sections.append("## PharmaGuard AI — Executive Summary")
    sections.append("")

    # ── Section 1: Drug Safety Overview ───────────────────────────────────────
    sections.append("### 1. Drug Safety Overview")
    sections.append("")
    if s_ctx is None:
        sections.append(
            "_No safety analysis data available. "
            "Go to **Drug Safety Signal Detection**, upload a dataset, and click "
            "**Detect Safety Signals** first._"
        )
    else:
        sections.append(
            f"- **Drug–event pairs analysed:** {s_ctx['total_pairs']}"
        )
        sections.append(
            f"- **Potential signals detected:** {s_ctx['n_signals']}"
        )
        sections.append(
            f"- **Pairs with no signal:** {s_ctx['n_no_signal']}"
        )
        if s_ctx["n_signals"] == 0:
            sections.append("")
            sections.append(
                "No combinations met the Evans (2001) screening criteria "
                "(PRR ≥ 2, a ≥ 3, chi-square ≥ 4) in the current dataset."
            )
        else:
            sections.append("")
            sections.append("**Top potential signals (by PRR):**")
            sections.append("")
            for i, sig in enumerate(s_ctx["top_signals"], 1):
                prr  = sig.get("PRR",        "N/A")
                chi2 = sig.get("Chi_Square", "N/A")
                a    = sig.get("a",          "?")
                sections.append(
                    f"{i}. **{sig['Drug']}** - **{sig['Adverse_Event']}** "
                    f"| PRR = {prr} | Chi-sq = {chi2} | Reports (a) = {a}"
                )
    sections.append("")

    # ── Section 2: Regulatory Readiness Overview ───────────────────────────────
    sections.append("### 2. Regulatory Readiness Overview")
    sections.append("")
    if r_ctx is None:
        sections.append(
            "_No regulatory readiness data available. "
            "Go to **Regulatory Submission Readiness**, complete or upload a checklist, "
            "and calculate a readiness score first._"
        )
    else:
        label = _readiness_label(r_ctx["score_pct"])
        sections.append(f"- **Overall readiness score:** {r_ctx['score_pct']}% — {label}")
        sections.append(
            f"- **Present:** {r_ctx['present']}  |  "
            f"**Missing:** {r_ctx['missing']}  |  "
            f"**Not Applicable:** {r_ctx['not_applicable']}"
        )
        sections.append(f"- **Applicable components:** {r_ctx['total_applicable']}")
        sections.append("")
        sections.append("**Module-wise readiness:**")
        sections.append("")
        for _, row in r_ctx["module_df"].iterrows():
            pct = row["Readiness_Pct"]
            filled  = int(pct / 10)
            empty   = 10 - filled
            bar     = "+" * filled + "-" * empty   # ASCII-safe bar
            sections.append(f"- {row['Module']}: {pct}%  [{bar}]")
        if r_ctx["missing_by_module"]:
            sections.append("")
            sections.append("**Missing components:**")
            sections.append("")
            for mod, docs in sorted(r_ctx["missing_by_module"].items()):
                sections.append(f"*{mod}:*")
                for doc in docs:
                    sections.append(f"  - {doc}")
    sections.append("")

    # ── Section 3: Key Priorities ──────────────────────────────────────────────
    sections.append("### 3. Key Priorities")
    sections.append("")
    priorities: list[str] = []

    if s_ctx and s_ctx["n_signals"] > 0:
        top = s_ctx["top_signals"][0]
        priorities.append(
            f"**Safety:** Review the top-ranked potential signal "
            f"({top['Drug']} - {top['Adverse_Event']}, PRR = {top.get('PRR','N/A')}) "
            "with a qualified pharmacovigilance professional."
        )

    if r_ctx and r_ctx["missing_by_module"]:
        # Highlight the module with the most missing items
        worst_mod = max(r_ctx["missing_by_module"], key=lambda m: len(r_ctx["missing_by_module"][m]))
        n_missing = len(r_ctx["missing_by_module"][worst_mod])
        priorities.append(
            f"**Regulatory:** Address {n_missing} missing item(s) in {worst_mod} "
            "(typically one of the most time-consuming areas to complete)."
        )

    if not priorities:
        sections.append(
            "No specific priorities identified — no signals detected and no missing CTD items. "
            "Review all results with your team before submission."
        )
    else:
        for p in priorities:
            sections.append(f"- {p}")
    sections.append("")

    # ── Section 4: Important Limitations ──────────────────────────────────────
    sections.append("### 4. Important Limitations")
    sections.append("")
    sections.append(
        "- Statistical signal detection (PRR / chi-square) identifies disproportionate "
        "reporting patterns only. It does **not** establish causality."
    )
    sections.append(
        "- The CTD readiness score is based solely on the checklist you provided "
        "and is not an official regulatory determination."
    )
    sections.append(
        "- Requirements vary by regulatory authority, product type, and submission pathway."
    )
    sections.append(
        "- All findings must be reviewed by qualified pharmacovigilance and "
        "regulatory affairs professionals before any action is taken."
    )

    return "\n".join(sections)


# ══════════════════════════════════════════════════════════════════════════════
# AI Provider — IBM watsonx.ai or OpenAI, with fallback
# ══════════════════════════════════════════════════════════════════════════════

def _detect_ai_provider() -> str:
    """
    Return 'watsonx', 'openai', or 'fallback' based on available env vars.
    Credentials must NEVER be hard-coded here.
    """
    if os.environ.get("WATSONX_API_KEY") and os.environ.get("WATSONX_PROJECT_ID"):
        return "watsonx"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    # Also check Streamlit secrets (st.secrets is available at runtime)
    try:
        if st.secrets.get("WATSONX_API_KEY") and st.secrets.get("WATSONX_PROJECT_ID"):
            return "watsonx"
        if st.secrets.get("OPENAI_API_KEY"):
            return "openai"
    except Exception:
        pass
    return "fallback"


def _get_secret(key: str) -> str | None:
    """Read a secret from env vars first, then Streamlit secrets."""
    val = os.environ.get(key)
    if val:
        return val
    try:
        return st.secrets.get(key)
    except Exception:
        return None


# Default Frankfurt (eu-de) endpoint — override with WATSONX_URL secret/env var.
_WATSONX_DEFAULT_URL      = "https://eu-de.ml.cloud.ibm.com"
# IBM Granite 3 8B Instruct — verified available in Frankfurt (eu-de) region.
_WATSONX_DEFAULT_MODEL_ID = "ibm/granite-3-8b-instruct"
# watsonx.ai REST API version
_WATSONX_API_VERSION      = "2023-05-29"


def _call_watsonx(prompt: str, system: str) -> str:
    """
    Call IBM watsonx.ai text generation (REST) endpoint.

    Authentication: IBM Cloud IAM — API key exchanged for a short-lived
    bearer token. The API key is read from the WATSONX_API_KEY secret/env
    var and is NEVER logged, printed, or exposed in the UI.

    Required secrets/env vars:
      WATSONX_API_KEY    — IBM Cloud API key (never hard-coded)
      WATSONX_PROJECT_ID — watsonx.ai project ID (never hard-coded)

    Optional secrets/env vars (defaults shown):
      WATSONX_URL        — https://eu-de.ml.cloud.ibm.com  (Frankfurt)
      WATSONX_MODEL_ID   — ibm/granite-3-8b-instruct
    """
    import requests  # part of Streamlit's dependency tree; no extra install

    api_key    = _get_secret("WATSONX_API_KEY")
    project_id = _get_secret("WATSONX_PROJECT_ID")
    base_url   = (_get_secret("WATSONX_URL") or _WATSONX_DEFAULT_URL).rstrip("/")
    model_id   = _get_secret("WATSONX_MODEL_ID") or _WATSONX_DEFAULT_MODEL_ID

    # ── Step 1: exchange API key for IAM bearer token ─────────────────────────
    # The IAM endpoint is global — region does not affect token acquisition.
    try:
        iam_resp = requests.post(
            "https://iam.cloud.ibm.com/identity/token",
            data={
                "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                "apikey": api_key,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=20,
        )
        iam_resp.raise_for_status()
        token = iam_resp.json()["access_token"]
    except Exception as exc:
        # Do not include the api_key value in the error message.
        raise RuntimeError(
            f"IBM IAM token exchange failed (check WATSONX_API_KEY): {type(exc).__name__}"
        ) from exc

    # ── Step 2: call the watsonx.ai text-generation REST endpoint ─────────────
    # Granite 3 uses a simple chat-style prompt with <|system|> / <|user|> /
    # <|assistant|> special tokens.  The model's stop token is already
    # configured inside the deployed model; we stop on the next turn marker.
    gen_url = f"{base_url}/ml/v1/text/generation?version={_WATSONX_API_VERSION}"

    input_text = (
        f"<|system|>\n{system}\n"
        f"<|user|>\n{prompt}\n"
        f"<|assistant|>\n"
    )

    payload = {
        "model_id":   model_id,
        "project_id": project_id,
        "input":      input_text,
        "parameters": {
            "decoding_method": "greedy",
            "max_new_tokens":  1024,
            "repetition_penalty": 1.05,
            "stop_sequences":  ["<|user|>", "<|endoftext|>"],
        },
    }

    try:
        resp = requests.post(
            gen_url,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type":  "application/json",
                "Accept":        "application/json",
            },
            timeout=90,
        )
        resp.raise_for_status()
    except Exception as exc:
        raise RuntimeError(
            f"watsonx.ai generation request failed "
            f"(model={model_id}, region={base_url}): {type(exc).__name__} — {exc}"
        ) from exc

    result_json = resp.json()
    generated   = result_json["results"][0]["generated_text"].strip()
    return generated


def _call_openai(prompt: str, system: str) -> str:
    """
    Call OpenAI chat completions endpoint.
    Requires: OPENAI_API_KEY env var.
    """
    try:
        import requests

        api_key = _get_secret("OPENAI_API_KEY")
        model   = _get_secret("OPENAI_MODEL") or "gpt-4o-mini"

        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            json={
                "model":    model,
                "messages": [
                    {"role": "system",  "content": system},
                    {"role": "user",    "content": prompt},
                ],
                "max_tokens":   800,
                "temperature":  0.3,
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    except Exception as exc:
        raise RuntimeError(f"OpenAI call failed: {exc}") from exc


def query_ai(
    user_question: str,
    safety_ctx: dict | None,
    regulatory_ctx: dict | None,
    provider: str,
) -> tuple[str, str]:
    """
    Route the question to the configured AI provider or fallback engine.

    Returns: (response_text, mode_label)
    """
    # ── Build a rich context block for LLM providers ───────────────────────────
    context_block = _build_llm_context_block(safety_ctx, regulatory_ctx)

    system_prompt = textwrap.dedent("""
        You are PharmaGuard AI Copilot, a pharmacovigilance and regulatory affairs
        analytical assistant for a student hackathon prototype.

        RULES (strictly enforced):
        - Use only the data provided in the CONTEXT block. Do NOT invent numbers.
        - Never claim a drug CAUSES an adverse event. Use language like
          "disproportionate reporting", "potential signal", "requires further assessment".
        - Never provide clinical treatment recommendations or diagnoses.
        - Never claim a dossier will be accepted or rejected by any authority.
        - Always include appropriate caveats about pharmacovigilance limitations.
        - Keep responses concise, structured, and suitable for pharmacy students.
        - Use bullet points and bold headings where helpful.
    """).strip()

    full_prompt = f"CONTEXT:\n{context_block}\n\nQUESTION: {user_question}"

    if provider == "watsonx":
        try:
            text = _call_watsonx(full_prompt, system_prompt)
            return text, "IBM watsonx.ai / Granite"
        except Exception as exc:
            # Show a safe user-facing message — no credentials in exc text.
            st.warning(
                f"IBM watsonx.ai unavailable — switched to rule-based fallback mode.  \n"
                f"Reason: {exc}"
            )
            provider = "fallback"

    if provider == "openai":
        try:
            text = _call_openai(full_prompt, system_prompt)
            return text, "OpenAI"
        except Exception as exc:
            st.warning(f"OpenAI error — falling back to rule-based mode. ({exc})")
            provider = "fallback"

    # ── Rule-based fallback ────────────────────────────────────────────────────
    q = user_question.lower()

    if safety_ctx and any(w in q for w in ["summarise safety", "summarize safety", "safety summary", "signal analysis"]):
        return _fallback_safety_summary(safety_ctx), "Rule-based fallback"

    if regulatory_ctx and any(w in q for w in ["regulatory summary", "summarise regulatory", "summarize regulatory", "readiness summary"]):
        return _fallback_regulatory_summary(regulatory_ctx), "Rule-based fallback"

    if any(w in q for w in ["executive summary", "summarise both", "summarize both", "both analyses", "both modules",
                             "executive", "generate executive"]):
        return _fallback_executive_summary(safety_ctx, regulatory_ctx), "Rule-based fallback"

    if safety_ctx and any(w in q for w in ["top signal", "first signal", "which signal", "review first", "prioriti"]):
        return _fallback_signal_prioritisation(safety_ctx), "Rule-based fallback"

    if safety_ctx and any(w in q for w in ["why", "flagged", "explain", "what does"]) and any(w in q for w in ["signal", "drug", "prr", "event"]):
        return _fallback_top_signal_explanation(safety_ctx), "Rule-based fallback"

    if safety_ctx and any(w in q for w in ["prr", "proportional reporting"]):
        return _fallback_explain_prr(safety_ctx), "Rule-based fallback"

    if regulatory_ctx and any(w in q for w in ["ctd gap", "gap", "fix", "missing", "priority", "what should"]):
        return _fallback_ctd_priorities(regulatory_ctx), "Rule-based fallback"

    # Generic fallback: combine whatever context is available
    return _fallback_combined_summary(safety_ctx, regulatory_ctx), "Rule-based fallback"


def _build_llm_context_block(
    safety_ctx: dict | None,
    regulatory_ctx: dict | None,
) -> str:
    """
    Serialise the current analysis results into a compact text block
    suitable for inclusion in an LLM prompt.
    """
    lines: list[str] = []

    if safety_ctx:
        lines.append("=== DRUG SAFETY SIGNAL ANALYSIS ===")
        lines.append(f"Total drug-event pairs analysed: {safety_ctx['total_pairs']}")
        lines.append(f"Potential signals detected: {safety_ctx['n_signals']}")
        if safety_ctx["top_signals"]:
            lines.append("Top potential signals (by PRR):")
            for sig in safety_ctx["top_signals"]:
                lines.append(
                    f"  - {sig['Drug']} -> {sig['Adverse_Event']}: "
                    f"PRR={sig['PRR']}, Chi2={sig['Chi_Square']}, "
                    f"a={sig['a']}, b={sig.get('b','?')}, c={sig.get('c','?')}, d={sig.get('d','?')}, "
                    f"Status={sig['Signal_Status']}"
                )
        else:
            lines.append("No combinations met the screening criteria.")
    else:
        lines.append("=== DRUG SAFETY SIGNAL ANALYSIS ===")
        lines.append("No safety analysis data available yet.")

    lines.append("")

    if regulatory_ctx:
        lines.append("=== REGULATORY SUBMISSION READINESS ===")
        lines.append(f"Overall readiness score: {regulatory_ctx['score_pct']}% ({_readiness_label(regulatory_ctx['score_pct'])})")
        lines.append(f"Present: {regulatory_ctx['present']} | Missing: {regulatory_ctx['missing']} | N/A: {regulatory_ctx['not_applicable']}")
        mod_df = regulatory_ctx["module_df"]
        lines.append("Module-wise readiness:")
        for _, row in mod_df.iterrows():
            lines.append(f"  - {row['Module']}: {row['Readiness_Pct']}%")
        if regulatory_ctx["missing_by_module"]:
            lines.append("Missing components:")
            for mod, docs in sorted(regulatory_ctx["missing_by_module"].items()):
                for doc in docs:
                    lines.append(f"  - [{mod}] {doc}")
    else:
        lines.append("=== REGULATORY SUBMISSION READINESS ===")
        lines.append("No readiness assessment data available yet.")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# Main render function (called from app.py)
# ══════════════════════════════════════════════════════════════════════════════

def render() -> None:

    # ── Page header ────────────────────────────────────────────────────────────
    st.markdown(
        """
        <h2 style="color:#0d3b66;">🤖 PharmaGuard AI Copilot</h2>
        <p style="color:#555;font-size:1rem;">
            AI-assisted interpretation of pharmacovigilance signals and regulatory readiness.
        </p>
        <hr style="border:1px solid #d0e4f5;">
        """,
        unsafe_allow_html=True,
    )

    # ── AI guardrails disclaimer ───────────────────────────────────────────────
    st.warning(DISCLAIMER, icon=None)

    # ── Detect AI provider ─────────────────────────────────────────────────────
    provider = _detect_ai_provider()

    if provider == "fallback":
        st.info(
            "🔧 **AI API not configured — using transparent rule-based explanation mode.**  \n"
            "To enable IBM watsonx.ai (Frankfurt), add to `.streamlit/secrets.toml`:  \n"
            "`WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, "
            "`WATSONX_URL` (default: `https://eu-de.ml.cloud.ibm.com`).  \n"
            "The rule-based mode produces explanations directly from your actual analysis results.",
            icon=None,
        )
    elif provider == "watsonx":
        active_url   = _get_secret("WATSONX_URL") or _WATSONX_DEFAULT_URL
        active_model = _get_secret("WATSONX_MODEL_ID") or _WATSONX_DEFAULT_MODEL_ID
        st.success(
            f"🟢 AI provider: **IBM watsonx.ai / Granite** — ready.  \n"
            f"Region endpoint: `{active_url}`  |  Model: `{active_model}`"
        )
    else:
        st.success("🟢 AI provider: **OpenAI** — ready.")

    # ── Build analysis contexts ────────────────────────────────────────────────
    safety_ctx     = build_safety_context()
    regulatory_ctx = build_regulatory_context()

    # ── Current analysis context status ───────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📊 Current Analysis Context")

    col1, col2 = st.columns(2)
    with col1:
        if safety_ctx:
            st.success(
                f"✅ **Safety Analysis loaded**  \n"
                f"{safety_ctx['total_pairs']} drug–event pairs · "
                f"{safety_ctx['n_signals']} potential signal(s)"
            )
        else:
            st.warning(
                "⚠️ **No Safety Analysis available**  \n"
                "Run the *Drug Safety Signal Detection* module first, "
                "then click **🔍 Detect Safety Signals**."
            )

    with col2:
        if regulatory_ctx:
            label = _readiness_label(regulatory_ctx["score_pct"])
            st.success(
                f"✅ **Regulatory Readiness loaded**  \n"
                f"Score: {regulatory_ctx['score_pct']}% ({label}) · "
                f"{regulatory_ctx['missing']} missing item(s)"
            )
        else:
            st.warning(
                "⚠️ **No Regulatory Assessment available**  \n"
                "Run the *Regulatory Submission Readiness* module first "
                "and calculate a readiness score."
            )

    # ── Quick summary buttons ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### ⚡ Quick Summaries")

    qcol1, qcol2, qcol3 = st.columns(3)

    with qcol1:
        if st.button("🔬 Generate Safety Summary",
                     key="btn_safety_summary",
                     disabled=(safety_ctx is None)):
            response, mode = query_ai(
                "Summarise the current safety signal analysis.",
                safety_ctx, regulatory_ctx, provider,
            )
            st.session_state["copilot_response"] = response
            st.session_state["copilot_mode"]     = mode
            st.session_state["copilot_question"] = "Generate Safety Summary"

    with qcol2:
        if st.button("📋 Generate Regulatory Summary",
                     key="btn_regulatory_summary",
                     disabled=(regulatory_ctx is None)):
            response, mode = query_ai(
                "Summarise the regulatory readiness assessment.",
                safety_ctx, regulatory_ctx, provider,
            )
            st.session_state["copilot_response"] = response
            st.session_state["copilot_mode"]     = mode
            st.session_state["copilot_question"] = "Generate Regulatory Summary"

    with qcol3:
        if st.button("📄 Generate Executive Summary",
                     key="btn_executive_summary",
                     disabled=(safety_ctx is None and regulatory_ctx is None)):
            try:
                # Read contexts fresh inside the handler to guarantee we have
                # the latest session_state values on this exact re-run.
                _s_ctx = build_safety_context()
                _r_ctx = build_regulatory_context()

                _response = _fallback_executive_summary(_s_ctx, _r_ctx)

                # Store in session_state for the persistent display block.
                st.session_state["copilot_response"] = _response
                st.session_state["copilot_mode"]     = "Rule-based fallback"
                st.session_state["copilot_question"] = "Generate Executive Summary"

                # Also render directly here — this is guaranteed to be visible
                # on the same run regardless of widget ordering issues.
                st.markdown("---")
                st.markdown("**Executive Summary generated** — see the Copilot Response section below, or read it here:")
                st.markdown(_response)
            except Exception as _exc:
                import traceback as _tb
                st.exception(_exc)

    # ── Suggested questions ────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 💡 Suggested Questions")
    st.markdown(
        "Click any question to send it to the Copilot, "
        "or type your own question in the text box below."
    )

    sq_cols = st.columns(2)
    for idx, question in enumerate(SUGGESTED_QUESTIONS):
        with sq_cols[idx % 2]:
            if st.button(question, key=f"sq_{idx}"):
                response, mode = query_ai(
                    question, safety_ctx, regulatory_ctx, provider,
                )
                st.session_state["copilot_response"] = response
                st.session_state["copilot_mode"]     = mode
                st.session_state["copilot_question"] = question

    # ── Free-text query ────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🗨️ Ask the Copilot")

    user_input = st.text_area(
        "Type your question about the safety analysis or regulatory readiness:",
        height=90,
        placeholder="e.g. Why was Atorvastatin flagged for Myopathy?",
        key="copilot_input",
    )

    ask_col, clear_col = st.columns([2, 5])
    with ask_col:
        ask_clicked = st.button("🤖 Ask Copilot", type="primary",
                                key="btn_ask_copilot",
                                disabled=(not user_input.strip()))
    with clear_col:
        if st.button("🗑️ Clear Response", key="btn_clear_response"):
            st.session_state.pop("copilot_response", None)
            st.session_state.pop("copilot_mode",     None)
            st.session_state.pop("copilot_question", None)

    if ask_clicked and user_input.strip():
        with st.spinner("Analysing…"):
            response, mode = query_ai(
                user_input.strip(), safety_ctx, regulatory_ctx, provider,
            )
        st.session_state["copilot_response"] = response
        st.session_state["copilot_mode"]     = mode
        st.session_state["copilot_question"] = user_input.strip()

    # ── Response display ───────────────────────────────────────────────────────
    if "copilot_response" in st.session_state:
        st.markdown("---")
        st.markdown("### 🤖 Copilot Response")

        mode = st.session_state.get("copilot_mode", "")
        question = st.session_state.get("copilot_question", "")

        mode_colour = "#2e7d32" if "watsonx" in mode or "OpenAI" in mode else "#666"
        st.markdown(
            f'<div style="background:#f0f4f8;border-radius:6px;padding:10px 16px;'
            f'font-size:0.82rem;color:{mode_colour};margin-bottom:10px;">'
            f'<strong>Q:</strong> {question} &nbsp;|&nbsp; '
            f'<strong>Mode:</strong> {mode}</div>',
            unsafe_allow_html=True,
        )

        response_box = (
            '<div style="background:#ffffff;border:1px solid #d0e4f5;border-left:4px solid #1a6eb5;'
            'border-radius:0 8px 8px 0;padding:20px 24px;line-height:1.7;">'
        )
        st.markdown(response_box, unsafe_allow_html=True)
        st.markdown(st.session_state["copilot_response"])
        st.markdown("</div>", unsafe_allow_html=True)

        # Inline disclaimer under every response
        st.caption(
            "⚠️ AI-generated content is for educational and analytical assistance only. "
            "Does not establish causality, replace expert review, or constitute regulatory advice."
        )

    # ── Important limitations ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### ⚠️ Important Limitations")
    st.markdown(
        """
        - The Copilot works only with the data currently loaded in this session.
          Results are lost when the browser is refreshed.
        - Statistical signal detection (PRR / chi-square) does **not** prove causality.
        - The CTD readiness score is based solely on the checklist you provided.
        - Rule-based explanations are generated from templates — they are not medical or legal advice.
        - If using an LLM provider, outputs may vary and should always be reviewed critically.
        - Always consult a qualified pharmacovigilance or regulatory affairs professional before taking action.
        """
    )

    # ── Footer ─────────────────────────────────────────────────────────────────
    st.markdown(FOOTER_HTML, unsafe_allow_html=True)
