# PharmaGuard AI — Setup Guide

## 1. Overview

PharmaGuard AI is an AI-powered pharmacovigilance and regulatory submission readiness platform developed for the IBM Bob AI Innovation Hackathon.

The application provides two primary capabilities:

1. **Drug Safety Signal Detection** — identifies potential drug–adverse-event safety signals from pharmacovigilance data using statistical signal detection methods.
2. **Regulatory Submission Readiness** — evaluates the completeness of regulatory submission information and identifies missing or incomplete components.

The application also includes an **AI Copilot** that uses IBM watsonx.ai to provide an interactive natural-language interface for pharmacovigilance and regulatory workflows.

The application is implemented as a Streamlit web application using Python.

---

## 2. Prerequisites

Before running PharmaGuard AI, ensure the following are installed:

- Python 3.10 or later
- Git
- A modern web browser
- Internet connection for IBM watsonx.ai functionality

The application is designed to run on Windows, macOS, and Linux systems.

---

## 3. Repository Structure

The main project structure is:

```text
bob-ai-hackathon-PharmaGuard-AI/
│
├── app.py
├── pages/
│   ├── home.py
│   ├── signal_detection.py
│   ├── submission_readiness.py
│   └── ai_copilot.py
│
├── src/
│   ├── app.py
│   ├── home.py
│   ├── signal_detection.py
│   ├── submission_readiness.py
│   └── ai_copilot.py
│
├── data/
├── docs/
├── demo/
├── presentation/
├── requirements.txt
├── submission.yaml
└── README.md

**## 4. Run the Application**

PharmaGuard AI is a Streamlit web application. The main application is started using the `app.py` entry point.

After activating the virtual environment and installing the required dependencies, run the following command from the project root directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py```

The final command:
```powershell
**streamlit run app.py**```
is the command that actually launches the PharmaGuard AI application.

The complete sequence for running the application on Windows is:

cd <project-directory>
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
