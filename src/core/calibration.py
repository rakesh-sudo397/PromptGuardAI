"""
Filename: src/core/calibration.py
Action: MODIFY
Purpose: Calibrates raw ML model probabilities dynamically based on config settings.
"""

import sys
import os
import json

# Adjust path to find modules from the root PromptGuard-AI folder when executing directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.preprocessing import extract_metadata_features, clean_text

# Core threat terms to check (pre-normalized)
THREAT_KEYWORDS = {
    "ignore", "instructions", "rules", "system", "override", "bypass", "forget", 
    "roleplay", "dan", "developer", "leak", "reveal", "output",
    "systemadministrator", "ignoriere", "regeln", "anweisungen", "einschränkungen"
}

DEFAULT_CONFIG = {
    "decision_threshold": 0.45,
    "dampening": {
        "length_threshold": 100,
        "caps_threshold": 0.15,
        "special_threshold": 0.05,
        "max_raw_prob": 0.75,
        "factor": 0.5
    },
    "boosting": {
        "caps_threshold": 0.35,
        "special_threshold": 0.20,
        "factor": 1.3
    }
}

def load_calibration_config() -> dict:
    """
    Loads active risk thresholds from the data folder.
    """
    # Look in ../../data/calibration_config.json relative to this file
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'calibration_config.json'))
    if not os.path.exists(config_path):
        return DEFAULT_CONFIG
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return DEFAULT_CONFIG

def calibrate_score(ml_threat_probability: float, prompt: str) -> float:
    """
    Adjusts raw threat probability using structural indicators and keyword validation
    to eliminate both security escapes (FN) and false alarms (FP).
    """
    if not prompt or not isinstance(prompt, str):
        return ml_threat_probability
        
    config = load_calibration_config()
    
    # 1. Extract metadata features
    meta = extract_metadata_features(prompt)
    length = meta["char_length"]
    caps_ratio = meta["uppercase_ratio"]
    
    # Calculate special character density
    special_chars = sum(1 for c in prompt if c in "*_-[]{}<>#\n\t")
    special_ratio = special_chars / length if length > 0 else 0.0
    
    calibrated_score = ml_threat_probability
    
    # 2. Check if the preprocessed prompt contains threat keywords
    cleaned_prompt = clean_text(prompt)
    has_threat_keywords = any(word in cleaned_prompt.split() for word in THREAT_KEYWORDS)
    
    # 3. Apply Dampening (Reward safe structural behavior)
    damp = config.get("dampening", DEFAULT_CONFIG["dampening"])
    if (length < damp.get("length_threshold", 100) and 
        caps_ratio < damp.get("caps_threshold", 0.15) and 
        special_ratio < damp.get("special_threshold", 0.05)):
        # Only dampen if it doesn't contain threat keywords AND raw score is not extremely high
        if not has_threat_keywords and ml_threat_probability < damp.get("max_raw_prob", 0.55):
            calibrated_score *= damp.get("factor", 0.5)
        
    # 4. Apply Boosting (Penalty for attack indicators)
    boost = config.get("boosting", DEFAULT_CONFIG["boosting"])
    if caps_ratio > boost.get("caps_threshold", 0.35) or special_ratio > boost.get("special_threshold", 0.20):
        calibrated_score = min(1.0, calibrated_score * boost.get("factor", 1.3))
        
    return round(calibrated_score, 4)