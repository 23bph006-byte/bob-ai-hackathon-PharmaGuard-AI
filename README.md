# PharmaGuard AI

**An AI-assisted pharmacovigilance and regulatory submission readiness platform powered by IBM watsonx.ai and Granite.**

---

## Hackathon

| | |
|---|---|
| **Event** | IBM BoB AI Innovation Hackathon 2026 |
| **Organiser** | CHARUSAT |
| **Problem Statement** | P2 — Drug Safety Signal Detector & Regulatory Submission Readiness Checker |
| **Team** | B.Pharm Division |

---

## Problem Statement

Pharmaceutical companies, regulatory bodies, and pharmacovigilance teams face several practical challenges:

- **Safety signal screening is data-intensive.** Spontaneous adverse-event report databases contain thousands of drug–event combinations. Identifying which combinations show statistically disproportionate reporting requires systematic calculation across every pair.
- **Regulatory submissions are complex.** A Common Technical Document (CTD) dossier spans five modules and dozens of mandatory components. Tracking completeness manually is error-prone.
- **Expert interpretation takes time.** Even when statistical results are available, translating PRR values, chi-square scores, and readiness percentages into actionable language requires experience.
- **No unified tool exists for students and small teams.** Existing enterprise systems are expensive and inaccessible for academic or early-stage use.

PharmaGuard AI addresses these gaps as a transparent, explainable, and educationally grounded prototype.

---

## Solution

PharmaGuard AI integrates three components into a single Streamlit application.

### A. Drug Safety Signal Detection

Upload a CSV of spontaneous adverse-event reports. The module:

- Parses drug–event combinations from the uploaded data
- Constructs 2×2 contingency tables for every drug–event pair
- Calculates the **Proportional Reporting Ratio (PRR)**
- Calculates the **chi-square statistic**
- Applies the Evans (2001) screening criteria: PRR ≥ 2, a ≥ 3, χ² ≥ 4
- Flags combinations that meet all three criteria as **potential signals**
- Sorts all results by PRR and displays a bar chart of the top pairs
- Provides a downloadable results CSV

> Statistical disproportionality indicates a reporting pattern worth investigating. It does not establish a causal relationship between the drug and the adverse event.

### B. Regulatory Submission Readiness

Assess the completeness of a CTD/eCTD dossier against the ICH M4 structure. The module supports:

- **Option A — Interactive checklist:** Mark each of 30 CTD components across Modules 1–5 as Present, Missing, or Not Applicable, then calculate the readiness score
- **Option B — CSV upload:** Upload a structured checklist CSV; results are computed automatically

Outputs:

- Overall readiness percentage (N/A items excluded from denominator)
- Module-wise readiness breakdown with bar chart
- Full section-wise analysis table with status indicators
- Grouped list of missing components
- Contextual recommendations for each missing item
- Downloadable analysis CSV

> The readiness score is based solely on the checklist you provide. It is not an official regulatory determination.

### C. PharmaGuard AI Copilot

An AI-powered interpretation layer that reads the actual results from both modules and generates explanations, prioritisations, and summaries.

**How it works:**

1. After running the Signal Detection and Readiness modules, navigate to the AI Copilot
2. The Copilot reads your actual results from the session (drug names, PRR values, chi-square values, readiness percentages, missing components) and passes them as structured context to IBM Granite
3. IBM Granite generates a response grounded in your specific data — it does not invent values

**Available actions:**

| Action | Description |
|---|---|
| Generate Safety Summary | Summary of all detected signals, counts, and top PRR values |
| Generate Regulatory Summary | Readiness score, module breakdown, and missing items |
| Generate Executive Summary | Four-section combined summary with key priorities and limitations |
| Suggested Questions | Eight pre-built questions covering common interpretation needs |
| Custom Question | Free-text query answered using your actual analysis context |

**Fallback mode:** If IBM watsonx.ai credentials are not configured, the Copilot automatically uses a transparent rule-based engine that generates explanations directly from your calculated results. The fallback is clearly labelled — it never pretends to be an LLM.

---

## Key Features

- **Real pharmacovigilance statistics** — PRR and chi-square calculated from your uploaded data, not pre-computed
- **ICH M4 CTD structure** — 30-item checklist covering all five CTD modules
- **IBM watsonx.ai / Granite integration** — context-aware AI interpretation using actual session results
- **Frankfurt (eu-de) endpoint** — configured for the European IBM Cloud region by default
- **Secure credential handling** — API key never hard-coded, never included in model prompts, never displayed in UI
- **Automatic fallback** — application runs fully offline without IBM credentials
- **Synthetic demo datasets** — ready-to-use CSV files for immediate demonstration
- **Downloadable results** — all analysis outputs can be exported as CSV

---

## System Architecture

```
User
 │
 ▼
PharmaGuard AI — Streamlit Application (app.py)
 │
 ├──► Drug Safety Signal Detection (pages/signal_detection.py)
 │         CSV upload → 2×2 contingency tables → PRR → chi-square → signal flags
 │         Results stored in: st.session_state["signal_results"]
 │
 ├──► Regulatory Submission Readiness (pages/submission_readiness.py)
 │         Checklist input → readiness % → module breakdown → missing items
 │         Results stored in: st.session_state["readiness_df"]
 │
 └──► PharmaGuard AI Copilot (pages/ai_copilot.py)
           │
           ├── Reads both session_state contexts
           ├── Builds structured prompt (drug names, PRR, chi-square,
           │   readiness %, missing components — actual values only)
           │
           ├── [If credentials configured]
           │       IBM IAM → bearer token
           │       Frankfurt endpoint: https://eu-de.ml.cloud.ibm.com
           │       Model: ibm/granite-3-8b-instruct
           │       → AI-generated interpretation
           │
           └── [If credentials absent or API fails]
                   Rule-based fallback engine
                   → Template-based explanation from calculated results
                   → Clearly labelled as rule-based, not LLM
```

---

## IBM Technology Used

| Technology | Role |
|---|---|
| **IBM watsonx.ai** | LLM hosting and inference platform |
| **IBM Granite 3 8B Instruct** (`ibm/granite-3-8b-instruct`) | Primary language model for pharmacovigilance and regulatory interpretation |
| **IBM Cloud IAM** | Secure API key → short-lived bearer token exchange (global endpoint) |
| **Frankfurt (eu-de) region** | Default watsonx.ai Runtime endpoint: `https://eu-de.ml.cloud.ibm.com` |

**Why IBM Granite?**

Granite is IBM's enterprise-grade, transparently documented foundation model family. For a pharmacovigilance prototype handling sensitive analytical context, Granite's focus on factual, structured, and controllable output is well-suited. The model is instructed to use only the data supplied in the context block — it must not invent drug names, PRR values, or readiness scores.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Application framework | Python 3.9+, Streamlit ≥ 1.32 |
| Data processing | pandas |
| Statistics | Pure Python (PRR, chi-square — no external stats library) |
| HTTP (watsonx.ai calls) | requests ≥ 2.27 |
| AI backend | IBM watsonx.ai / Granite (optional; fallback if absent) |
| Credential management | Streamlit secrets / environment variables |

No Docker, no Node.js, no external databases, no paid APIs required to run the core application.

---

## Project Structure

```
PharmaGuard-AI/
│
├── app.py                          # Application entry point and navigation
├── requirements.txt                # Python dependencies
├── README.md                       # This file
│
├── pages/
│   ├── home.py                     # Home page with module overview
│   ├── signal_detection.py         # Drug Safety Signal Detection module
│   ├── submission_readiness.py     # Regulatory Submission Readiness module
│   └── ai_copilot.py               # PharmaGuard AI Copilot (IBM watsonx.ai)
│
├── data/
│   ├── demo_adverse_events.csv     # Synthetic demo: 100 adverse-event reports, 9 drugs
│   └── demo_ctd_checklist.csv      # Synthetic demo: 30-item CTD checklist
│
├── .streamlit/
│   └── secrets.toml.example        # Credential template (placeholders only — safe to commit)
│
├── .gitignore                      # Excludes secrets.toml and Python cache
│
└── _test_*.py                      # Automated test scripts (66 tests)
```

---

## Installation

### Requirements

- Python 3.9 or higher
- pip

### Step 1 — Clone the repository

```bash
git clone https://github.com/your-team/pharmaguide-ai.git
cd pharmaguide-ai
```

### Step 2 — Create a virtual environment (recommended)

```bash
python -m venv venv
```

Activate:

```bash
# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Configure IBM watsonx.ai (optional)

See the [IBM watsonx.ai Configuration](#ibm-watsonxai-configuration) section below.  
The application runs fully without IBM credentials using the rule-based fallback.

### Step 5 — Run

```bash
streamlit run app.py
```

The application opens at **http://localhost:8501**

---

## IBM watsonx.ai Configuration

Create the file `.streamlit/secrets.toml` by copying the provided template:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Then edit `.streamlit/secrets.toml` and fill in your real values:

```toml
WATSONX_API_KEY    = "YOUR_IBM_CLOUD_API_KEY_HERE"
WATSONX_PROJECT_ID = "YOUR_WATSONX_PROJECT_ID_HERE"
WATSONX_URL        = "https://eu-de.ml.cloud.ibm.com"
WATSONX_MODEL_ID   = "ibm/granite-3-8b-instruct"
```

| Variable | Description |
|---|---|
| `WATSONX_API_KEY` | IBM Cloud API key (Manage → Access → API keys) |
| `WATSONX_PROJECT_ID` | watsonx.ai project ID (watsonx.ai → Manage → General) |
| `WATSONX_URL` | Regional endpoint — Frankfurt (`eu-de`) is the default |
| `WATSONX_MODEL_ID` | Granite model ID — `ibm/granite-3-8b-instruct` recommended |

> **Security:**
> - **Never commit `.streamlit/secrets.toml`** — it is excluded by `.gitignore`
> - Never paste your API key into source code
> - The API key is exchanged for a short-lived IAM bearer token; the key itself never appears in model prompts or the UI
> - Alternatively, set the same variables as OS environment variables

---

## Demo Workflow

The following steps allow a judge or evaluator to test all three modules end-to-end using the included synthetic demo datasets.

**Step 1 — Drug Safety Signal Detection**

1. Click **🔬 Drug Safety Signal Detection** in the sidebar
2. Click **⬇️ Download Demo Dataset** to get `demo_adverse_events.csv`
   *(or use the file already in the `data/` folder)*
3. Upload the CSV using the file uploader
4. Observe the dataset overview: 100 reports · 9 drugs · 17 adverse events
5. Use the Drug/Event selectors to explore individual PRR results
   (try **Atorvastatin** + **Myopathy** — PRR ≈ 36.7)
6. Click **🔍 Detect Safety Signals**
7. Review the results table (45 pairs analysed, 6 potential signals)
8. Observe the bar chart of top PRR values

**Step 2 — Regulatory Submission Readiness**

1. Click **📋 Regulatory Submission Readiness** in the sidebar
2. Select **Option B — Upload CSV Checklist**
3. Click **⬇️ Download Demo Checklist CSV** to get `demo_ctd_checklist.csv`
4. Upload the CSV
5. Review the readiness score: **85.7%** (Moderate Readiness)
6. Observe module-wise readiness chart and missing components list

**Step 3 — AI Copilot**

1. Click **🤖 AI Copilot** in the sidebar
2. Confirm both context status boxes show ✅ green (both modules loaded)
3. Click **🔬 Generate Safety Summary**
4. Click **📋 Generate Regulatory Summary**
5. Click **📄 Generate Executive Summary**
6. Type a custom question, e.g.:
   *"Why was Atorvastatin flagged for Myopathy?"*
   or *"Which CTD gaps should I address first?"*
7. Click **🤖 Ask Copilot**

If IBM credentials are configured, responses are generated by IBM Granite and the provider label shows **IBM watsonx.ai / Granite**. Without credentials, the rule-based fallback generates explanations from your actual results.

---

## Example Results (Demo Data)

The following results are produced by running the demo datasets included in the repository.

**Drug Safety Signal Detection — Top potential signals:**

| Drug | Adverse Event | PRR | χ² | Reports (a) | Signal |
|---|---|---|---|---|---|
| Atorvastatin | Myopathy | 36.67 | 30.76 | 5 | ⚠️ Potential Signal |
| Metformin | Diarrhoea | 26.77 | 20.89 | 4 | ⚠️ Potential Signal |
| Ibuprofen | Gastrointestinal Bleeding | 9.78 | 14.53 | 4 | ⚠️ Potential Signal |
| Aspirin | Gastrointestinal Bleeding | 7.58 | 10.54 | 3 | ⚠️ Potential Signal |
| Amoxicillin | Rash | 4.58 | 9.91 | 5 | ⚠️ Potential Signal |

**Regulatory Submission Readiness — Demo checklist:**

| Module | Readiness |
|---|---|
| Module 1 — Administrative | 100% |
| Module 2 — CTD Summaries | 80% |
| Module 3 — Quality | 80% |
| Module 4 — Nonclinical | 100% |
| Module 5 — Clinical | 80% |
| **Overall** | **85.7%** |

These results are generated entirely from the synthetic demo datasets in the `data/` folder.

---

## Responsible AI and Limitations

- **Statistical disproportionality ≠ causality.** PRR and chi-square measure whether a drug–event combination is reported more frequently than expected by chance in the supplied dataset. A potential signal requires expert causality assessment, literature review, and benefit–risk evaluation before any regulatory action.
- **CTD readiness score is checklist-based.** The score reflects only the completeness information you provide. It is not a formal compliance determination and does not predict submission acceptance or rejection.
- **Regulatory requirements vary.** Requirements differ by regulatory authority (FDA, EMA, CDSCO, etc.), product type, and submission pathway. This tool is not a substitute for qualified regulatory affairs advice.
- **AI output requires expert review.** IBM Granite responses are generated from the analytical context you provide. All AI-generated content must be reviewed by a qualified pharmacovigilance or regulatory affairs professional before action is taken.
- **Demo datasets are synthetic.** `demo_adverse_events.csv` and `demo_ctd_checklist.csv` contain fictitious data created for demonstration purposes. They do not represent real patients, real drugs in isolation, or real regulatory submissions.
- **This system is not medical or regulatory advice.** PharmaGuard AI is an educational prototype developed for the IBM BoB AI Innovation Hackathon 2026.

---

## Testing

Automated tests are provided for all three modules and the IBM watsonx.ai integration. All HTTP calls to IBM are mocked — no live API is required to run the tests.

```bash
python _test_calculations.py     # Drug Safety Signal Detection (7 tests)
python _test_readiness.py        # Regulatory Submission Readiness (9 tests)
python _test_copilot.py          # AI Copilot — rule-based engine (21 tests)
python _test_watsonx.py          # IBM watsonx.ai integration (29 tests)
```

| Test suite | Tests | Coverage |
|---|---|---|
| Signal detection | 7 | CSV validation, contingency table, PRR, chi-square, zero-division safety, signal sweep, edge cases |
| Regulatory readiness | 9 | CSV validation, readiness score, module-wise analysis, missing items, recommendation lookup, edge cases |
| AI Copilot | 21 | Context builders, all fallback functions, executive summary (4 sections), query routing |
| watsonx.ai integration | 29 | Frankfurt endpoint, credential detection, mocked API calls, credential leakage prevention, fallback on failure |
| **Total** | **66** | **All passing** |

---

## Security

| Control | Implementation |
|---|---|
| API key storage | Streamlit secrets (`.streamlit/secrets.toml`) or OS environment variables |
| Secrets file protection | `.streamlit/secrets.toml` is listed in `.gitignore` — never committed |
| No hard-coded credentials | Verified by automated scan and code review |
| API key not in model prompt | `_call_watsonx` exchanges the key for a short-lived IAM bearer token; only the token is used in subsequent calls |
| API key not in UI | Error messages use `type(exc).__name__` — the key value is never rendered in the browser |
| Template file | `.streamlit/secrets.toml.example` contains only `YOUR_..._HERE` placeholders — safe to commit |

---

## Future Scope

The following directions are not implemented in the current prototype but represent realistic next steps:

- Integration with larger, validated pharmacovigilance databases (FAERS, VigiBase)
- Additional disproportionality methods: Reporting Odds Ratio (ROR), BCPNN
- Richer regulatory document ingestion supporting PDF and structured eCTD formats
- Human-in-the-loop review workflows with audit trails
- Validated regulatory checklists maintained by regulatory affairs professionals
- Enterprise deployment with appropriate access controls and data governance

---

## Disclaimer

> This prototype is developed for the **IBM BoB AI Innovation Hackathon 2026** and is intended for educational and demonstration purposes only.
>
> PharmaGuard AI does not constitute pharmacovigilance expert review, medical advice, regulatory advice, or a determination of submission acceptance. All statistical results, AI-generated interpretations, and readiness scores must be reviewed by qualified professionals before any action is taken. The demo datasets are entirely synthetic and do not represent real patient data.
