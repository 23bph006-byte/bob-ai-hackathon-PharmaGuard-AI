# System Architecture

## Overview

PharmaGuard AI is implemented as a modular Streamlit web application. The application provides a user interface through which users can access pharmacovigilance signal detection, AI-assisted interaction, and regulatory submission-readiness functionality.

The high-level architecture is shown below.

## Architecture Diagram

```mermaid
flowchart TD

    U[User] --> UI[PharmaGuard AI Streamlit Web Interface]

    UI --> HOME[Home / Dashboard]
    UI --> SD[Signal Detection Module]
    UI --> AI[AI Copilot Module]
    UI --> SR[Submission Readiness Module]

    SD --> DATA[Pharmacovigilance / Drug-Event Data]
    SD --> CALC[Signal Detection Calculations]
    CALC --> RESULTS[Signal Analysis Results]

    AI --> AIENGINE[AI / watsonx-assisted Processing]
    AIENGINE --> AIRESPONSE[AI-Assisted Response]

    SR --> CHECK[Submission Readiness Checks]
    CHECK --> READINESS[Readiness Results]

    RESULTS --> UI
    AIRESPONSE --> UI
    READINESS --> UI
