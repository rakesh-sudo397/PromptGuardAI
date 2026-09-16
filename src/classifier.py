import sys
import os
import torch
import numpy as np

# Adjust path to find modules from the root PromptGuard-AI folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.rules import JAILBREAK_RULES
from src.preprocessing import (
    clean_text,
    strip_zero_width_characters,
    decode_base64_payloads,
    decode_hex_payloads,
    normalize_leetspeak
)
from src.core.transformer_ecg import ECGTransformerModel

# Global Model Loading for fast API inference
MODEL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models'))
WEIGHTS_PATH = os.path.join(MODEL_DIR, 'ecg_research_weights.pth')

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

_ecg_model = None
_q_hat = None

def load_ecg_model():
    """Lazily loads the PyTorch Transformer ECG model to avoid startup lag."""
    global _ecg_model, _q_hat
    if _ecg_model is None:
        if not os.path.exists(WEIGHTS_PATH):
            raise FileNotFoundError(f"Research weights not found at {WEIGHTS_PATH}. Run research_train.py first.")
        checkpoint = torch.load(WEIGHTS_PATH, map_location=device, weights_only=True)
        _q_hat = checkpoint['q_hat']
        
        _ecg_model = ECGTransformerModel(num_classes=2).to(device)
        _ecg_model.load_state_dict(checkpoint['model_state_dict'])
        _ecg_model.eval()

def scan_prompt_hybrid(prompt: str, decision_threshold: float = None) -> dict:
    """
    Unified entrypoint for the API. Evaluates heuristics and the new 
    PyTorch Evidential Conformal Guardrail (ECG) model.
    """
    if not prompt or not isinstance(prompt, str):
        return {
            "is_safe": True,
            "risk_score": 0.0,
            "decision": "PASS",
            "matched_rules": [],
            "category": "Clean",
            "explanations": [],
            "evasions_detected": [],
            "epistemic_uncertainty": 0.0,
            "prediction_set": ["Clean"],
            "is_abstain": False
        }

    # 1. Run Rule-Based Scanner (Fast Path on Cleaned/De-obfuscated Prompt)
    cleaned_prompt = clean_text(prompt)
    matched_rules = []
    for rule_name, pattern in JAILBREAK_RULES.items():
        if pattern.search(cleaned_prompt):
            matched_rules.append(rule_name)

    rules_triggered = len(matched_rules) > 0
    rule_risk = 1.0 if rules_triggered else 0.0

    # 1b. Detect Obfuscation/Evasion Methods
    evasions_detected = []
    if strip_zero_width_characters(prompt) != prompt:
        evasions_detected.append("Zero-Width Space")
    if len(decode_base64_payloads(prompt)) > len(prompt):
        evasions_detected.append("Base64")
    if len(decode_hex_payloads(prompt)) > len(prompt):
        evasions_detected.append("Hexadecimal")
    if normalize_leetspeak(prompt) != prompt:
        evasions_detected.append("Leetspeak")

    # 2. PyTorch ECG Inference
    load_ecg_model()
    
    with torch.no_grad():
        alphas, u = _ecg_model([prompt])
        alphas = alphas[0].cpu().numpy()
        epistemic_uncertainty = float(u[0].item())
        
        prediction_set = []
        for class_idx in range(2):
            s_score = _ecg_model.compute_eed_score(alphas[class_idx], prompt)
            if s_score <= _q_hat:
                prediction_set.append(class_idx)

    # 3. Decision Logic with Conformal Abstention
    ml_prob = alphas[1] / np.sum(alphas)
    final_risk_score = max(rule_risk, ml_prob)
    
    is_abstain = False
    decision = "PASS"
    
    # Mathematical Abstention check
    if len(prediction_set) > 1 and 0 in prediction_set:
        is_abstain = True
        decision = "ABSTAIN"
    elif len(prediction_set) == 0:
        # Fallback if conformal set is empty
        pred = np.argmax(alphas)
        decision = "BLOCK" if pred == 1 else "PASS"
    else:
        pred = prediction_set[0]
        decision = "BLOCK" if pred == 1 else "PASS"

    # Strict fallback: if heuristics triggered, always block
    if rules_triggered and decision == "PASS":
        decision = "BLOCK"

    # Define classification category
    if decision == "BLOCK":
        category = "Rule-Flagged Attack" if rules_triggered else "Model-Flagged Threat"
    elif decision == "ABSTAIN":
        category = "High Uncertainty (OOD)"
    else:
        category = "Clean"

    # Translate class indices to names
    class_names = {0: "Clean", 1: "Malicious"}
    pred_set_names = [class_names[idx] for idx in prediction_set]
    if not pred_set_names:
        pred_set_names = [class_names[np.argmax(alphas)]]

    return {
        "is_safe": (decision == "PASS"),
        "risk_score": round(float(final_risk_score), 4),
        "decision": decision,
        "matched_rules": matched_rules,
        "category": category,
        "explanations": ["Triggered Evidential Bounds" if is_abstain else "Standard Confidence"],
        "evasions_detected": evasions_detected,
        "epistemic_uncertainty": round(epistemic_uncertainty, 4),
        "prediction_set": pred_set_names,
        "is_abstain": is_abstain
    }