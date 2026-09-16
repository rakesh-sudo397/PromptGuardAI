import torch
import torch.optim as optim
import pandas as pd
import numpy as np
import os
import sys

# Ensure paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.core.transformer_ecg import ECGTransformerModel
from src.core.risk_control import CascadedRiskController, compute_calibration_metrics

def edl_mse_loss(alpha, target, epoch_num, num_classes=2, annealing_step=10):
    y = torch.eye(num_classes).to(alpha.device)[target]
    S = torch.sum(alpha, dim=1, keepdim=True)
    p = alpha / S
    err = (y - p) ** 2
    var = (p * (1 - p)) / (S + 1)
    
    # KL Divergence annealing
    annealing_coef = min(1.0, epoch_num / annealing_step)
    alp = alpha - 1
    kl = annealing_coef * torch.sum(torch.lgamma(S) - torch.sum(torch.lgamma(alpha), dim=1, keepdim=True) + torch.sum(alp * (p - 1), dim=1, keepdim=True), dim=1)
    
    return torch.mean(torch.sum(err + var, dim=1) + kl)

def train_evidential_router():
    print("Loading scaled real-world datasets...")
    train_df = pd.read_csv('data/research_splits/real_train.csv')
    cal_df = pd.read_csv('data/research_splits/real_calibration.csv')
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = ECGTransformerModel(num_classes=2).to(device)
    optimizer = optim.Adam(model.parameters(), lr=2e-5)
    
    # Minimal training loop for demonstration (in production, use DataLoader)
    print("Training Evidential Router...")
    model.train()
    epochs = 3
    batch_size = 16
    
    for epoch in range(epochs):
        # Shuffling
        train_df = train_df.sample(frac=1.0)
        texts = train_df['text'].tolist()
        labels = train_df['label'].tolist()
        
        total_loss = 0
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            batch_labels = torch.tensor(labels[i:i+batch_size]).to(device)
            
            optimizer.zero_grad()
            alphas, _ = model(batch_texts)
            loss = edl_mse_loss(alphas, batch_labels, epoch)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            
        print(f"Epoch {epoch+1}/{epochs} - Loss: {total_loss / len(texts):.4f}")
        
    print("\nExecuting Cascaded Conformal Risk Control (CCRC)...")
    # Wrap calibration data
    class DummyLoader:
        def __init__(self, df, bs):
            self.df = df
            self.bs = bs
        def __iter__(self):
            texts = self.df['text'].tolist()
            labels = self.df['label'].tolist()
            for i in range(0, len(texts), self.bs):
                yield texts[i:i+self.bs], torch.tensor(labels[i:i+self.bs])

    cal_loader = DummyLoader(cal_df, 32)
    u_arr, preds_arr, labels_arr = compute_calibration_metrics(model, cal_loader, device)
    
    # Use the mathematically guaranteed Risk Controller
    # We guarantee a False Positive Rate <= 1% (0.01)
    crc = CascadedRiskController(alpha=0.01)
    optimal_tau = crc.calibrate(u_arr, preds_arr, labels_arr)
    
    print(f"\n[MATHEMATICAL GUARANTEE] Conformal Routing Threshold (tau) calculated: {optimal_tau:.4f}")
    print("This guarantees <= 1% False Positives on Developer Code.")
    
    os.makedirs('models', exist_ok=True)
    torch.save({
        'model_state_dict': model.state_dict(),
        'q_hat': optimal_tau # Preserving old key name for backward compatibility, but it is now tau
    }, 'models/ecg_research_weights.pth')
    
    print("Model and mathematical threshold saved securely.")

if __name__ == "__main__":
    train_evidential_router()
