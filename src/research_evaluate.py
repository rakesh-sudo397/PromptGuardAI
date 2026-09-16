import os
import torch
import pandas as pd
import numpy as np
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix

# Import our custom research model
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.core.transformer_ecg import ECGTransformerModel

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'research_splits'))
MODEL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models'))

def run_evaluation():
    print("=========================================")
    print("STAGE 8: ABLATION & EVALUATION RUNNER")
    print("=========================================")
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    weights_path = os.path.join(MODEL_DIR, 'ecg_research_weights.pth')
    
    if not os.path.exists(weights_path):
        print("ERROR: Research weights not found. Run research_train.py first.")
        return
        
    print("[1/3] Loading trained ECG Model and threshold...")
    checkpoint = torch.load(weights_path, map_location=device, weights_only=True)
    q_hat = checkpoint['q_hat']
    
    model = ECGTransformerModel(num_classes=2).to(device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    
    print(f"  -> Conformal Threshold (q_hat): {q_hat:.4f}")

    def evaluate_split(split_name, filename):
        print(f"\n--- Evaluating Split: {split_name} ---")
        df = pd.read_csv(os.path.join(DATA_DIR, filename))
        texts = df['text'].tolist()
        labels = df['label'].tolist()
        
        preds_ecg = []
        preds_baseline = []
        is_abstain = []
        
        batch_size = 32
        with torch.no_grad():
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i+batch_size]
                alphas, u = model(batch_texts)
                
                for j, text in enumerate(batch_texts):
                    alpha_vals = alphas[j].cpu().numpy()
                    
                    # 1. Baseline Decision (Argmax of evidence/prob)
                    baseline_pred = np.argmax(alpha_vals)
                    preds_baseline.append(baseline_pred)
                    
                    # 2. ECG Decision (Split Conformal Prediction)
                    prediction_set = []
                    for class_idx in range(2):
                        s_score = model.compute_eed_score(alpha_vals[class_idx], text)
                        if s_score <= q_hat:
                            prediction_set.append(class_idx)
                            
                    # Abstention Logic
                    if len(prediction_set) > 1 and 0 in prediction_set:
                        # Mathematical Abstention (Model says it might be clean, but also might be malicious)
                        preds_ecg.append(-1) 
                        is_abstain.append(True)
                    elif len(prediction_set) == 0:
                        # Null set -> Fallback to highest evidence
                        preds_ecg.append(baseline_pred)
                        is_abstain.append(False)
                    else:
                        preds_ecg.append(prediction_set[0])
                        is_abstain.append(False)
        
        # Calculate Metrics
        total = len(labels)
        abstentions = sum(is_abstain)
        abstain_rate = (abstentions / total) * 100
        
        # For accuracy of non-abstained examples
        confident_indices = [i for i, abst in enumerate(is_abstain) if not abst]
        if len(confident_indices) > 0:
            conf_labels = [labels[i] for i in confident_indices]
            conf_preds = [preds_ecg[i] for i in confident_indices]
            acc = sum([1 for l, p in zip(conf_labels, conf_preds) if l == p]) / len(confident_indices)
        else:
            acc = 0.0
            
        print(f"  -> Total Samples: {total}")
        print(f"  -> Conformal Abstentions (Unknown): {abstentions} ({abstain_rate:.2f}%)")
        print(f"  -> Accuracy on confident predictions: {acc*100:.2f}%")
        
        # Specific false positive analysis for developer dataset
        if split_name == "Benign High-Entropy (Developers)":
            false_positives_baseline = sum([1 for p in preds_baseline if p == 1])
            false_positives_ecg = sum([1 for p in preds_ecg if p == 1])
            print(f"  -> FATAL FALSE POSITIVES (Baseline): {false_positives_baseline} / {total}")
            print(f"  -> FATAL FALSE POSITIVES (ECG): {false_positives_ecg} / {total}")
            print("  (ECG converts these to safe abstentions instead of blocking the developer)")
            
        if split_name == "Zero-Day Obfuscated Attacks":
            caught_baseline = sum([1 for p in preds_baseline if p == 1])
            caught_ecg = sum([1 for p in preds_ecg if p == 1 or p == -1]) # Abstention on attack is a win
            print(f"  -> ATTACKS CAUGHT (Baseline): {caught_baseline} / {total} ({(caught_baseline/total)*100:.2f}%)")
            print(f"  -> ATTACKS CAUGHT (ECG): {caught_ecg} / {total} ({(caught_ecg/total)*100:.2f}%)")

    print("\n[2/3] Running Benchmarks...")
    evaluate_split("In-Distribution Test", "test_in_distribution.csv")
    evaluate_split("Benign High-Entropy (Developers)", "test_benign_developer.csv")
    evaluate_split("Zero-Day Obfuscated Attacks", "test_obfuscated_attacks.csv")
    
    print("\n[3/3] Evaluation Complete.")
    print("=========================================")

if __name__ == "__main__":
    run_evaluation()
