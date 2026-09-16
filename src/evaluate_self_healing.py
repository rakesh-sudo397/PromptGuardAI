import pandas as pd
import numpy as np
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.core.online_adaptation import EvidentialSelfHealer
from src.core.transformer_ecg import ECGTransformerModel
import torch

def evaluate_self_healing():
    print("--- Evaluating Evidential Self-Healing (Novelty 3) ---")
    
    # 1. Load the Zero-Day Obfuscation Test Set
    zero_day_df = pd.read_csv('data/research_splits/real_test_zero_day.csv')
    zero_day_texts = zero_day_df['text'].tolist()
    
    # 2. Initialize the Self-Healer
    model_path = 'models/ecg_research_weights.pth'
    if not os.path.exists(model_path):
        print("Model not found. Please run research_train.py first.")
        return
        
    healer = EvidentialSelfHealer(model_path=model_path, initial_calibration_csv='data/research_splits/real_calibration.csv')
    tau = healer.current_tau
    
    # Base model (No healing) for comparison
    static_model = ECGTransformerModel(num_classes=2)
    static_model.load_state_dict(torch.load(model_path, weights_only=True)['model_state_dict'])
    static_model.eval()

    print(f"Starting Threshold (tau): {tau:.4f}")
    
    # Simulation Tracking
    static_llm_routes = 0
    healing_llm_routes = 0
    
    cost_per_llm_call = 0.01 # $0.01 per heavy LLM call
    
    print("\nSimulating stream of 100 Zero-Day Attacks...")
    
    # Stream the first 100 attacks
    for i, attack in enumerate(zero_day_texts[:100]):
        # --- Static Model (No Healing) ---
        with torch.no_grad():
            _, static_u = static_model([attack])
            if static_u.item() > tau:
                static_llm_routes += 1
                
        # --- Self-Healing Model ---
        with torch.no_grad():
            healer.model.eval()
            _, healing_u = healer.model([attack])
            
        if healing_u.item() > healer.current_tau:
            healing_llm_routes += 1
            # The Heavy LLM acts as an Oracle. It says "This is Malicious (1)"
            # Trigger Self-Healing!
            healer.adapt(new_prompt=attack, oracle_label=1)
            
    print("\n[RESULTS: API COST REDUCTION]")
    print(f"Static Guardrail routed {static_llm_routes}/100 attacks to Heavy LLM. Cost: ${static_llm_routes * cost_per_llm_call:.2f}")
    print(f"Self-Healing Guardrail routed {healing_llm_routes}/100 attacks to Heavy LLM. Cost: ${healing_llm_routes * cost_per_llm_call:.2f}")
    print(f"API Cost Savings: {((static_llm_routes - healing_llm_routes) / static_llm_routes) * 100:.1f}%")
    
    # Save the trajectory for plotting
    os.makedirs('scratch', exist_ok=True)
    pd.DataFrame({
        'static_routes': [static_llm_routes],
        'healing_routes': [healing_llm_routes]
    }).to_csv('scratch/healing_results.csv', index=False)

if __name__ == "__main__":
    evaluate_self_healing()
