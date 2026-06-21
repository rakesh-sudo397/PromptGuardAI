"""
Filename: src/core/calibration.py
Action: MODIFY
Purpose: Calibrates raw ML model probabilities based on prompt structural metadata and keyword checks.
"""

import sys
import os

# Adjust path to find modules from the root PromptGuard-AI folder when executing directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.preprocessing import extract_metadata_features, clean_text

# Core threat terms to check (pre-normalized)
THREAT_KEYWORDS = {"ignore", "instructions", "rules", "system", "override", "bypass", "forget", "roleplay", "dan", "developer", "leak", "reveal", "output"}

def calibrate_score(ml_threat_probability: float, prompt: str) -> float:
    """
    Adjusts raw threat probability using structural indicators and keyword validation
    to eliminate both security escapes (FN) and false alarms (FP).
    """
    if not prompt or not isinstance(prompt, str):
        return ml_threat_probability
        
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
    # If the query is relatively short, standard casing, and has low delimiter density:
    if length < 100 and caps_ratio < 0.15 and special_ratio < 0.05:
        # Only dampen if it doesn't contain threat keywords AND raw score is not extremely high
        if not has_threat_keywords and ml_threat_probability < 0.55:
            calibrated_score *= 0.5
        
    # 4. Apply Boosting (Penalty for attack indicators)
    elif caps_ratio > 0.35 or special_ratio > 0.20:
        calibrated_score = min(1.0, calibrated_score * 1.3)
        
    return round(calibrated_score, 4)