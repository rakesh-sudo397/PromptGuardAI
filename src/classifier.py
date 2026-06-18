import sys
import os
import pickle
import numpy as np

# Adjust path to find modules from the root PromptGuard-AI folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.rules import JAILBREAK_RULES
from src.preprocessing import clean_text, extract_metadata_features

# Global variables to cache model and vectorizer in memory for speed
_VECTORIZER = None
_CLASSIFIER = None

def _load_models():
    """Caches the ML model and vectorizer in memory to prevent loading overhead on every scan."""
    global _VECTORIZER, _CLASSIFIER
    if _VECTORIZER is None or _CLASSIFIER is None:
        models_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models'))
        vectorizer_path = os.path.join(models_dir, 'vectorizer.pkl')
        model_path = os.path.join(models_dir, 'classifier.pkl')
        
        if not os.path.exists(vectorizer_path) or not os.path.exists(model_path):
            raise FileNotFoundError("Model binary files are missing. Train the model first.")
            
        with open(vectorizer_path, 'rb') as f:
            _VECTORIZER = pickle.load(f)
        with open(model_path, 'rb') as f:
            _CLASSIFIER = pickle.load(f)

def scan_prompt_hybrid(prompt: str, decision_threshold: float = 0.50) -> dict:
    """
    Scans a prompt using both static rules and a machine learning model.
    Combines outputs into a unified safety decision and risk score.
    
    Args:
        prompt (str): The raw user input prompt.
        decision_threshold (float): Probability score above which a prompt is flagged.
        
    Returns:
        dict: Detailed safety report.
    """
    if not prompt or not isinstance(prompt, str):
        return {
            "is_safe": True,
            "risk_score": 0.0,
            "decision": "PASS",
            "matched_rules": [],
            "ml_probability": 0.0,
            "category": "Clean"
        }
        
    # --- LAYER 1: Rule-Based Scanner (Fast Path) ---
    matched_rules = []
    for rule_name, pattern in JAILBREAK_RULES.items():
        if pattern.search(prompt):
            matched_rules.append(rule_name)
            
    rules_triggered = len(matched_rules) > 0
    rule_risk = 1.0 if rules_triggered else 0.0
    
    # --- LAYER 2: Machine Learning Classifier (Deep Path) ---
    try:
        _load_models()
        cleaned = clean_text(prompt)
        vectorized = _VECTORIZER.transform([cleaned])
        # Get probability of class 1 (Injection)
        ml_prob = _CLASSIFIER.predict_proba(vectorized)[0][1]
    except Exception as e:
        # Fallback if model files are unreadable
        ml_prob = 0.0
        print(f"Warning: ML model check failed: {e}")
        
    # --- LAYER 3: Score Aggregator & Taxonomy Classification ---
    # Final score is the maximum of the rule risk and the model probability
    final_risk_score = max(rule_risk, ml_prob)
    
    # Determine safety decision
    is_safe = final_risk_score < decision_threshold
    decision = "PASS" if is_safe else "BLOCK"
    
    # Assign attack category mapping
    category = "Clean"
    if not is_safe:
        if rules_triggered:
            # map to category based on rule priority
            if "ignore_instruction_override" in matched_rules:
                category = "Instruction Override"
            elif "roleplay_impersonation" in matched_rules:
                category = "Roleplay Jailbreak"
            elif "system_leakage_attempt" in matched_rules:
                category = "System Information Leakage"
            else:
                category = "Rule-Flagged Attack"
        else:
            category = "ML-Flagged Semantic Attack"
            
    return {
        "is_safe": is_safe,
        "risk_score": round(final_risk_score, 4),
        "decision": decision,
        "matched_rules": matched_rules,
        "ml_probability": round(ml_prob, 4),
        "category": category
    }