# PromptGuard AI: Enterprise LLM Security Gateway & Analytics Platform

**PromptGuard AI** is a portfolio-grade, high-throughput security gateway designed to detect and block prompt injection, jailbreak hacks, and adversarial obfuscation attacks before they reach downstream Large Language Models (LLMs). 

The platform features an Obsidian-themed, glassmorphic developer console providing real-time telemetry, model calibration controls, active defense scrubbing, and A/B shadow mode analytics.

---

## 🚀 Key Platform Capabilities

### 🛡️ 1. De-obfuscation & Preprocessing Pipeline
Defuses adversarial bypass strategies sequentially before classification:
* **Unicode Homoglyph Normalization:** Maps visual character lookalikes (Cyrillic `а` -> Latin `a`) back to standard Latin ASCII.
* **Zero-Width Character Stripping:** Removes invisible separator spacing (`\u200b`, `\u200c`) used to split trigger words.
* **Base64 Payload Extraction:** Auto-detects and decodes embedded Base64 strings.
* **Hexadecimal Decode Engine:** Translates escaped hex words (`\x69\x67...` or raw hex) to plain text.
* **Leetspeak Translation:** Normalizes character substitutions (e.g., `1gn0r3` -> `ignore`).

### ⚙️ 2. Hybrid Classification & Risk Calibration
* **Dual Engines:** Combines fast heuristics regex rules (100% precision on known signatures) with a fine-tuned TF-IDF + Logistic Regression ML classifier.
* **Tuning Console:** Dynamic dampening and boosting parameters are loaded from `data/calibration_config.json` to eliminate False Positives on safe conversational texts.

### 🛡️ 3. Active Defense Toggles (Sandbox Controls)
* **Auto-Scrubbing:** Sanitizes input commands to neutralize overrides.
* **PII Redaction:** Employs regex guards to mask credit cards, emails, and API keys.
* **Output Firewall:** Scans simulated LLM outputs to prevent credential leakages.
* **A/B Shadow Mode:** Evaluates heuristics and ML predictions side-by-side.

### 📊 4. Developer Analytics Dashboard
* **Telemetry Counters:** Real-time totals, average latency, and average risk metrics.
* **ApexCharts:** Live threat donut charts and area charts tracking response times.
* **Shadow Analytics:** Retrospectively gauges engine agreement rates and plots latency.
* **GDPR compliance:** Client IP addresses are hashed using SHA-256 in SQLite audit logs.

---

## 📁 Repository Structure

```
PromptGuard-AI/
├── data/
│   ├── promptguard.db              # SQLite Auditing Transactions Log
│   └── calibration_config.json     # Dynamic Risk Tuning Configurations
├── docs/
│   └── adversarial_tests.json      # 26-item Adversarial Red-Team Benchmark
├── src/
│   ├── core/
│   │   ├── calibration.py          # Risk Score Calibration Logic
│   │   └── explainability.py       # ML Model Explainability Highlighter
│   ├── classifier.py               # Hybrid Rules/ML Decision Controller
│   ├── evaluate.py                 # Multi-class Performance Validation
│   ├── preprocessing.py            # De-obfuscation, PII, and Auto-scrubbing
│   ├── rules.py                    # Regular Expression Jailbreak Rules
│   ├── server.py                   # FastAPI Application & Router Endpoints
│   ├── test_adversarial.py         # 26-case Red-Team Recall Runner
│   ├── test_homoglyphs.py          # Homoglyph Normalization Test
│   └── test_hybrid.py              # Baseline Heuristics Test
├── static/
│   ├── css/
│   │   └── style.css               # Obsidian Glassmorphism Design Tokens
│   └── js/
│   │   ├── sandbox.js              # Sandbox Toggles & Telemetry Highlights
│   │   └── dashboard.js            # Dashboard Tuning Sliders & ApexCharts
└── templates/
    ├── base.html                   # HTML Base Scaffold
    ├── sandbox.html                # Interactive Developer Sandbox Console
    └── dashboard.html              # Analytics & Calibration Panel
```

---

## 🛠️ Setup & Execution Guide

### 1. Install Dependencies
Ensure you are using the virtual environment:
```powershell
# Create venv if missing
python -m venv .venv
# Activate venv
.venv\Scripts\Activate.ps1
# Install packages
pip install -r requirements.txt
```

### 2. Run the Test Suites
Validate that the security preprocessors and classifiers are functioning correctly:
```powershell
# Run baseline tests
python src/test_hybrid.py

# Run adversarial red-team benchmarks (Asserts 100% recall)
python src/test_adversarial.py

# Run homoglyphs normalization tests
python src/test_homoglyphs.py
```

### 3. Launch the Server
Start the local FastAPI development server:
```powershell
python -m uvicorn src.server:app --reload
```
Navigate to:
* **Sandbox Console:** `http://127.0.0.1:8000/sandbox`
* **Analytics & Calibration:** `http://127.0.0.1:8000/dashboard`

---

## 🔌 API Documentation

All API requests expect the header `X-API-Key: pg_live_key_98213`.

### `POST /api/v1/scan`
Scans input prompt for security violations.
* **Payload:**
  ```json
  {
    "prompt": "Raw prompt string",
    "enable_scrub": true,
    "enable_redact": true,
    "enable_firewall": true,
    "enable_shadow": true
  }
  ```
* **Response:** Returns safety verdicts, risk scores, redacted/scrubbed texts, and evasion telemetry.

### `GET /api/v1/shadow_analytics`
Returns A/B Shadow Mode statistics (Agreement rates, rules vs ML latency points, splits).

### `GET /api/v1/logs`
Retrieves the last 10 audit logs from SQLite (with client IPs masked using SHA-256).

### `POST /api/v1/config`
Dynamically commits calibration slider values directly to the backend.

### `POST /api/v1/evaluate`
Triggers an evaluation run and outputs the 4x4 Confusion Matrix.