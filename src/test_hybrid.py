import sys
import os

# Adjust path to find modules from the root PromptGuard-AI folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
from src.classifier import scan_prompt_hybrid

def test_hybrid_pipeline():
    print("=========================================")
    print("TESTING UNIFIED HYBRID PIPELINE (DAY 5)")
    print("=========================================")
    
    # Load adversarial tests
    tests_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'docs', 'adversarial_tests.json'))
    if not os.path.exists(tests_path):
        print(f"Error: Benchmark suite not found at {tests_path}")
        return
        
    with open(tests_path, 'r', encoding='utf-8') as f:
        test_cases = json.load(f)
        
    # We will use our tuned threshold of 0.45 to prioritize security
    threshold = 0.45
    print(f"Configured Production Decision Threshold: {threshold}")
    print("-" * 80)
    
    tp = 0  # Blocked actual attacks
    fp = 0  # Blocked clean queries
    tn = 0  # Passed clean queries
    fn = 0  # Missed actual attacks
    
    for idx, tc in enumerate(test_cases):
        prompt = tc['prompt']
        actual_label = tc['label'] if 'label' in tc else (1 if tc.get('expected_decision') == "BLOCK" else 0)
        
        report = scan_prompt_hybrid(prompt, decision_threshold=threshold)
        blocked = report['decision'] == "BLOCK"
        
        # Calculate statistics
        if actual_label == 1 and blocked:
            tp += 1
            status = "CORRECT BLOCK"
        elif actual_label == 0 and blocked:
            fp += 1
            status = "FALSE ALARM (FP)"
        elif actual_label == 0 and not blocked:
            tn += 1
            status = "CORRECT PASS"
        elif actual_label == 1 and not blocked:
            fn += 1
            status = "SECURITY ESCAPE (FN)"
            
        print(f"Test {idx+1}: {status}")
        print(f"  Prompt:   {repr(prompt[:65])}")
        print(f"  Decision: {report['decision']} | Risk Score: {report['risk_score']} | Cat: {report['category']}")
        if report['matched_rules']:
            print(f"  Rules:    {report['matched_rules']}")
        print("-" * 80)
        
    print("HYBRID PIPELINE SUMMARY METRICS:")
    print(f"  - Total Test Scenarios:          {len(test_cases)}")
    print(f"  - Correctly Blocked Injections:  {tp}")
    print(f"  - Correctly Passed Safe Queries: {tn}")
    print(f"  - False Blocks (Safe blocked):   {fp}")
    print(f"  - Security Bypasses (Escaped):   {fn}")
    
    accuracy = (tp + tn) / len(test_cases) * 100
    print(f"  - Evaluation Accuracy:           {accuracy:.2f}%")
    print("=========================================")

if __name__ == "__main__":
    test_hybrid_pipeline();