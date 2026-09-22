import os
import subprocess
import sys

try:
    from docx import Document
    from docx.shared import Pt, Inches
    from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
except ImportError:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'python-docx'])
    from docx import Document
    from docx.shared import Pt, Inches
    from docx.enum.text import WD_PARAGRAPH_ALIGNMENT

doc = Document()

# Title
title = doc.add_heading('PromptGuard AI: Comprehensive Project Manifesto', 0)
title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

doc.add_paragraph("A complete architectural, developmental, and scientific record from inception to the present moment.")

# Section 1
doc.add_heading('1. The Ultimate Use-Case & Purpose of the Project', level=1)
doc.add_paragraph("What is the project used for?")
doc.add_paragraph("PromptGuard AI is an edge-deployed, mathematically bounded security gateway for Large Language Models (LLMs). Its primary use is to sit between a user and an Enterprise LLM (like GPT-4 or Llama-3) to detect and block malicious prompt injections, jailbreaks, and zero-day obfuscated attacks (like Base64 or Hex encodings).", style='List Bullet')
doc.add_paragraph("Crucially, it is designed to solve the 'Complexity vs. Intent' problem: It must successfully block hackers WITHOUT falsely blocking Software Developers who are pasting complex Python code, JSON payloads, or SQL databases into the LLM.", style='List Bullet')

# Section 2
doc.add_heading('2. Phase 1: Foundation & The Web Application', level=1)
doc.add_paragraph("WHAT WE BUILT:")
doc.add_paragraph("1. A full-stack web application with a React frontend (UI/UX, Login, Signup) and a FastAPI backend (server.py).", style='List Bullet')
doc.add_paragraph("2. An SQLite database (promptguard.db) to manage users and log attack telemetry.", style='List Bullet')
doc.add_paragraph("3. A baseline Machine Learning classifier using Scikit-Learn (LinearSVC) and TF-IDF vectorization.", style='List Bullet')
doc.add_paragraph("WHY WE BUILT IT:")
doc.add_paragraph("We needed a functional prototype and a live API to route traffic. We implemented TF-IDF as a baseline to establish the foundational architecture.")
doc.add_paragraph("WHY WE ABANDONED THE ML PIPELINE:")
doc.add_paragraph("TF-IDF relies on a fixed vocabulary. When a hacker uses 'Zero-Day Obfuscation' (e.g., encoding a jailbreak into Base64), the TF-IDF vectorizer sees unknown words and maps them to zero. The baseline model was mathematically blind to unseen attacks.")

# Section 3
doc.add_heading('3. Phase 2: The Deep Learning Pivot & EDL', level=1)
doc.add_paragraph("WHAT WE BUILT:")
doc.add_paragraph("1. We rewrote the core engine (transformer_ecg.py) using PyTorch and the Sentence-Transformers 'MiniLM-L6-v2' backbone.", style='List Bullet')
doc.add_paragraph("2. We replaced standard Softmax with an Evidential Deep Learning (EDL) Head to quantify Epistemic Uncertainty (Dirichlet distribution).", style='List Bullet')
doc.add_paragraph("WHY WE BUILT IT:")
doc.add_paragraph("Dense transformers map text to a latent space, allowing the model to understand context rather than exact word matches. Furthermore, we needed EDL because standard Softmax models suffer from 'Out-of-Distribution (OOD) Overconfidence'. Softmax forces a model to guess confidently even when it has no idea what it is looking at. EDL allows the model to output 'I don't know' (Epistemic Uncertainty) when it sees a zero-day attack.")

# Section 4
doc.add_heading('4. Phase 3: The Brutal Novelty Audit', level=1)
doc.add_paragraph("WHAT WE DID:")
doc.add_paragraph("We halted implementation and conducted a rigorous simulated peer-review against top-tier IEEE/USENIX standards. We evaluated our early mathematical heuristic, 'Evidential-Entropy Divergence (EED)'.", style='List Bullet')
doc.add_paragraph("WHY WE DID IT:")
doc.add_paragraph("To guarantee publication, a project cannot just be 'good engineering'; it must possess unassailable scientific novelty. The audit revealed that EED was a heuristic, lacking strict statistical proof, and was vulnerable to semantic jailbreaks. We ruthlessly discarded EED to protect the paper's integrity and pivoted to a Systems-Security framework.")

# Section 5
doc.add_heading('5. Phase 4: The Triple-Threat Architecture (Current State)', level=1)
doc.add_paragraph("This is the core scientific contribution of the project. We built a 3-pillar 'Self-Healing Conformal Cascade'.")

doc.add_heading('Pillar 1: Evidential Routing for Cascaded Guardrails (ERCG)', level=2)
doc.add_paragraph("WHAT IT IS: We modified the API to route prompts to a Heavy LLM (like Llama-Guard) ONLY when the Edge Model's Epistemic Uncertainty spikes.")
doc.add_paragraph("WHY WE DID IT: The industry uses Softmax to trigger routing. We proved that Softmax overconfidence causes edge models to confidently misclassify Base64 attacks and Developer Code, fatally failing to route them. ERCG fixes this structural vulnerability.")

doc.add_heading('Pillar 2: Cascaded Conformal Risk Control (risk_control.py)', level=2)
doc.add_paragraph("WHAT IT IS: A statistical algorithm using the Hoeffding/Bates upper bound to dynamically set the uncertainty routing threshold (tau).")
doc.add_paragraph("WHY WE DID IT: Guessing a threshold (e.g., 0.8) is unscientific. This algorithm provides a mathematical theorem guaranteeing that the system will NEVER falsely block more than 1% of benign developer code, securing the paper against reviewer attacks.")

doc.add_heading('Pillar 3: Evidential Self-Healing (online_adaptation.py)', level=2)
doc.add_paragraph("WHAT IT IS: A real-time training loop. When a zero-day is routed to the Heavy LLM, the Edge Model intercepts the LLM's verdict and uses it as a pseudo-label to execute a single-step gradient update on itself.")
doc.add_paragraph("WHY WE DID IT: To solve the 'Concept Drift' cat-and-mouse game. The model autonomously learns new zero-day attacks in real-time, drastically reducing Heavy LLM API costs. The Conformal Risk Controller acts as a shield to prevent catastrophic forgetting.")

# Section 6
doc.add_heading('6. Phase 5: Empirical Benchmarking & Handoff', level=1)
doc.add_paragraph("WHAT WE BUILT:")
doc.add_paragraph("1. scale_datasets.py: A script that pulls tens of thousands of real-world instructions (Dolly), real developer code (Alpaca), and real prompt injections (Deepset) from HuggingFace.", style='List Bullet')
doc.add_paragraph("2. generate_paper_plots.py: Visual generators for KDE uncertainty distributions and API cost reductions.", style='List Bullet')
doc.add_paragraph("3. GitHub Handoff: Initialized git, committed the entire mathematical architecture, wrote CONTRIBUTING.md, and pushed to the feature/ds-Rakesh branch.", style='List Bullet')
doc.add_paragraph("WHY WE DID IT:")
doc.add_paragraph("Mathematical theorems must be proven empirically. The scaled datasets provide the massive scale required by peer reviewers. The GitHub handoff ensures that your collaborator can immediately take over the Heavy LLM API integration and JailbreakBench testing without disrupting the core ML physics.")

save_path = r"C:\Users\RAKESH N\PromptGuard-AI\PromptGuard_Project_Manifesto.docx"
doc.save(save_path)
print(f"Manifesto generated successfully at {save_path}")
