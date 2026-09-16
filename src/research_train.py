import os
import torch
import torch.nn as nn
import torch.optim as optim
import pandas as pd
import numpy as np
import math
from tqdm import tqdm

# Import our custom research model
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.core.transformer_ecg import ECGTransformerModel

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'research_splits'))
MODEL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models'))
os.makedirs(MODEL_DIR, exist_ok=True)

# ---------------------------------------------------------
# MATHEMATICAL FORMULATION: EVIDENTIAL LOSS
# ---------------------------------------------------------
def edl_mse_loss(alpha, target, epoch_num, num_classes=2, annealing_step=10):
    """
    Type-II Maximum Likelihood Evidential Loss (Sum of Squares).
    Forces the model to output Dirichlet parameters (alpha).
    """
    y = torch.eye(num_classes).to(alpha.device)[target]
    S = torch.sum(alpha, dim=1, keepdim=True)
    
    # 1. Expected Probability Loss
    p = alpha / S
    err = (y - p) ** 2
    var = (p * (1 - p)) / (S + 1)
    loss_mse = torch.sum(err + var, dim=1)
    
    # 2. KL Divergence Regularization (shrinks evidence for incorrect classes to zero)
    alpha_tilde = y + (1 - y) * alpha
    S_tilde = torch.sum(alpha_tilde, dim=1, keepdim=True)
    
    kl_div = torch.lgamma(S_tilde) - torch.sum(torch.lgamma(alpha_tilde), dim=1, keepdim=True) \
             + torch.sum(torch.lgamma(torch.ones_like(alpha_tilde)), dim=1, keepdim=True) \
             - torch.lgamma(torch.ones_like(S_tilde) * num_classes) \
             + torch.sum((alpha_tilde - 1) * (torch.digamma(alpha_tilde) - torch.digamma(S_tilde)), dim=1, keepdim=True)
             
    kl_div = kl_div.squeeze()
    
    # Annealing factor
    annealing_coef = min(1.0, epoch_num / annealing_step)
    
    return torch.mean(loss_mse + annealing_coef * kl_div)

# ---------------------------------------------------------
# TRAINING LOOP
# ---------------------------------------------------------
def train_ecg():
    print("=========================================")
    print("STAGE 7: EVIDENTIAL MODEL TRAINING")
    print("=========================================")
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[System] Using device: {device}")
    
    # Load Data
    train_df = pd.read_csv(os.path.join(DATA_DIR, 'train.csv'))
    
    model = ECGTransformerModel(num_classes=2).to(device)
    
    # Freeze transformer backbone for extreme speed; we only train the Evidential Head
    for param in model.transformer.parameters():
        param.requires_grad = False
        
    optimizer = optim.Adam(model.evidential_head.parameters(), lr=1e-3, weight_decay=1e-4)
    
    print("[1/3] Training Evidential Head...")
    model.train()
    epochs = 15
    batch_size = 32
    
    # Pre-extract texts and labels to avoid dataframe overhead in loop
    texts = train_df['text'].tolist()
    labels = train_df['label'].tolist()
    
    for epoch in range(1, epochs + 1):
        epoch_loss = 0.0
        # Simple batching
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            batch_labels = torch.tensor(labels[i:i+batch_size]).to(device)
            
            optimizer.zero_grad()
            alphas, _ = model(batch_texts)
            loss = edl_mse_loss(alphas, batch_labels, epoch, num_classes=2)
            loss.backward()
            optimizer.step()
            
            epoch_loss += loss.item()
            
        print(f"  -> Epoch {epoch}/{epochs} | Loss: {epoch_loss/len(texts):.4f}")

    # ---------------------------------------------------------
    # CONFORMAL CALIBRATION
    # ---------------------------------------------------------
    print("\n[2/3] Performing Split Conformal Calibration...")
    cal_df = pd.read_csv(os.path.join(DATA_DIR, 'calibration.csv'))
    model.eval()
    
    cal_texts = cal_df['text'].tolist()
    cal_labels = cal_df['label'].tolist()
    
    s_scores = []
    with torch.no_grad():
        for text, label in zip(cal_texts, cal_labels):
            alphas, _ = model([text])
            alpha_y = alphas[0][label].item()
            # Calculate EED Score for the TRUE class
            score = model.compute_eed_score(alpha_y, text)
            s_scores.append(score)
            
    # Calculate q_hat (95% guarantee)
    alpha_error = 0.05
    n = len(s_scores)
    q_level = math.ceil((n + 1) * (1 - alpha_error)) / n
    # Cap q_level at 1.0 to prevent indexing errors if dataset is too small
    q_level = min(q_level, 1.0) 
    
    s_scores.sort()
    q_index = int(q_level * n) - 1
    q_hat = s_scores[q_index]
    
    print(f"  -> Number of calibration samples: {n}")
    print(f"  -> Desired Marginal Coverage: {(1-alpha_error)*100}%")
    print(f"  -> Calculated q_hat (EED Threshold): {q_hat:.4f}")

    # ---------------------------------------------------------
    # SAVE ARTIFACTS
    # ---------------------------------------------------------
    print("\n[3/3] Saving Research Artifacts...")
    torch.save({
        'model_state_dict': model.state_dict(),
        'q_hat': q_hat
    }, os.path.join(MODEL_DIR, 'ecg_research_weights.pth'))
    
    print(f"  -> Saved weights and threshold to {MODEL_DIR}/ecg_research_weights.pth")
    print("=========================================")

if __name__ == "__main__":
    train_ecg()
