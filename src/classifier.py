from src.rules import JAILBREAK_RULES

def scan_prompt(prompt: str) -> dict:
    """
    Scans a prompt against static regex rules.
    
    Args:
        prompt (str): The raw string input from the user.
        
    Returns:
        dict: Safety report including safety classification and triggered rules.
    """
    if not prompt or not isinstance(prompt, str):
        return {
            "is_safe": True,
            "risk_score": 0.0,
            "matched_rules": [],
            "message": "Empty or invalid prompt format."
        }
    
    matched_rules = []
    
    # Iterate through compiled rules in rules.py
    for rule_name, pattern in JAILBREAK_RULES.items():
        if pattern.search(prompt):
            matched_rules.append(rule_name)
            
    is_safe = len(matched_rules) == 0
    risk_score = 1.0 if not is_safe else 0.0
    
    return {
        "is_safe": is_safe,
        "risk_score": risk_score,
        "matched_rules": matched_rules,
        "message": "Malicious activity detected." if not is_safe else "Prompt classified as safe."
    }