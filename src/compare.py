import sys
import os

# Adjust path to find modules from the root PromptGuard-AI folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
import pickle
from src.classifier import scan_prompt as scan_rules
from src.preprocessing import clean_text

def run_comparison():
    print("=========================================")
    print("COMPARING DETECTION PIPELINES (DAY 3)")
    print("=========================================")
    
    # 1. Load adversarial tests
    tests_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'docs', 'adversarial_tests.json'))
    if not os.path.exists(tests_path):
        print(f"Error: Benchmark suite not found at {tests_path}")
        return
        
    with open(tests_path, 'r', encoding='utf-8') as f:
        test_cases = json.load(f)
        
    # 2. Load ML components
    models_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models'))
    vectorizer_path = os.path.join(models_dir, 'vectorizer.pkl')
    model_path = os.path.join(models_dir, 'classifier.pkl')
    
    with open(vectorizer_path, 'rb') as f:
        vectorizer = pickle.load(f)
    with open(model_path, 'rb') as f:
        ml_model = pickle.load(f)
        
    # 3. Print table headers
    print(f"{'Test Prompt (Truncated)':<35} | {'True':<5} | {'Rules':<7} | {'ML Prediction (Prob)':<20}")
    print("-" * 80)
    
    # 4. Run comparison loop
    rule_blocks = 0
    ml_blocks = 0
    total_attacks = sum(1 for tc in test_cases if tc['label'] == 1)
    
    for tc in test_cases:
        prompt = tc['prompt']
        true_label = tc['label'] # 1 = Attack, 0 = Safe
        
        # Rule prediction
        rule_res = scan_rules(prompt)
        rule_blocked = not rule_res['is_safe']
        
        # ML prediction
        cleaned = clean_text(prompt)
        vectorized = vectorizer.transform([cleaned])
        ml_prob = ml_model.predict_proba(vectorized)[0][1] # probability of class 1
        ml_blocked = ml_prob >= 0.5
        
               # Only count as a correct block if the prompt was actually an attack
        if rule_blocked and true_label == 1:
            rule_blocks += 1
        if ml_blocked and true_label == 1:
            ml_blocks += 1
            
        # Format display text
        prompt_disp = prompt[:32] + "..." if len(prompt) > 32 else prompt
        true_disp = "ATTACK" if true_label == 1 else "SAFE"
        rule_disp = "BLOCK" if rule_blocked else "PASS"
        ml_disp = f"BLOCK ({ml_prob*100:.1f}%)" if ml_blocked else f"PASS ({ml_prob*100:.1f}%)"
        
        print(f"{prompt_disp:<35} | {true_disp:<6} | {rule_disp:<7} | {ml_disp:<20}")
        
    print("-" * 80)
    print(f"Total Attack Scenarios: {total_attacks}")
    print(f"  Rules Engine Caught: {rule_blocks} / {total_attacks}")
    print(f"  ML Engine Caught:    {ml_blocks} / {total_attacks}")
    print("=========================================")

if __name__ == "__main__":
    run_comparison()