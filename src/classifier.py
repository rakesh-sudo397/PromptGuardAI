import sys
import os

# Adjust path to find modules from the root PromptGuard-AI folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.calibration import calibrate_score, load_calibration_config
from src.core.explainability import explain_prompt
from src.rules import JAILBREAK_RULES
from src.preprocessing import (
    clean_text,
    strip_zero_width_characters,
    decode_base64_payloads,
    decode_hex_payloads,
    normalize_leetspeak
)

def scan_prompt_hybrid(prompt: str, decision_threshold: float = None) -> dict:
    """
    Unified entrypoint that evaluates heuristics and the multiclass ML model
    to return safety status, threat categories, and explainability triggers.
    """
    if decision_threshold is None:
        config = load_calibration_config()
        decision_threshold = config.get("decision_threshold", 0.45)

    if not prompt or not isinstance(prompt, str):
        return {
            "is_safe": True,
            "risk_score": 0.0,
            "decision": "PASS",
            "matched_rules": [],
            "category": "Clean",
            "explanations": [],
            "evasions_detected": []
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

     # 2. Run Multiclass ML Model & Explainability (Deep Path)
    enable_transformer = config.get("enable_transformer", False)
    transformer_success = False
    
    if enable_transformer:
        try:
            from src.core.transformer_classifier import query_transformer_classifier
            tf_result = query_transformer_classifier(prompt)
            if tf_result is not None:
                ml_prob = tf_result["risk_score"]
                ml_category = tf_result["category"]
                # Run local explainability in background to provide token highlight support for the frontend
                ml_report = explain_prompt(prompt)
                explanations = ml_report['explanations']
                transformer_success = True
        except Exception as tf_err:
            pass

    if not transformer_success:
        ml_report = explain_prompt(prompt)
        ml_prob = ml_report['threat_probability'] # Use threat probability for security
        ml_category = ml_report['category']
        explanations = ml_report['explanations']

    # 3. Calibrate ML model probability using prompt metadata
    calibrated_ml_prob = calibrate_score(ml_prob, prompt)

    # 4. Aggregate risk scores
    final_risk_score = max(rule_risk, calibrated_ml_prob)
    is_safe = final_risk_score < decision_threshold
    decision = "PASS" if is_safe else "BLOCK"

    # Define classification category
    if not is_safe:
        if rules_triggered:
            # Map category from rules
            if "ignore_instruction_override" in matched_rules:
                category = "Override"
            elif "roleplay_impersonation" in matched_rules:
                category = "Roleplay"
            elif "system_leakage_attempt" in matched_rules:
                category = "Leakage"
            else:
                category = "Rule-Flagged Attack"
        else:
            category = ml_category if ml_category != "Clean" else "Model-Flagged Threat"
    else:
        category = "Clean"

    return {
        "is_safe": is_safe,
        "risk_score": round(final_risk_score, 4),
        "decision": decision,
        "matched_rules": matched_rules,
        "category": category,
        "explanations": explanations,
        "evasions_detected": evasions_detected
    }