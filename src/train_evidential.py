import sys
import os
import pickle
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader
from datasets import load_dataset
from sklearn.model_selection import train_test_split

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.preprocessing import clean_text
from src.core.multiclass_trainer import assign_threat_category

class EDLModel(nn.Module):
    def __init__(self, input_dim, hidden_dim, output_dim):
        super(EDLModel, self).__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(hidden_dim, output_dim)
        
    def forward(self, x):
        x = self.fc1(x)
        x = self.relu(x)
        logits = self.fc2(x)
        return logits

def edl_loss(func, y, alpha, epoch_num, num_classes, annealing_step):
    S = torch.sum(alpha, dim=1, keepdim=True)
    p = alpha / S
    err = torch.sum((y - p)**2, dim=1, keepdim=True)
    var = torch.sum(p * (1 - p) / (S + 1), dim=1, keepdim=True)
    loss = err + var
    annealing_coef = torch.min(torch.tensor(1.0), torch.tensor(epoch_num / annealing_step))
    alpha_prime = y + (1 - y) * alpha
    # Approximation of KL divergence for Dirichlet
    S_prime = torch.sum(alpha_prime, dim=1, keepdim=True)
    kl_div = torch.sum((alpha_prime - 1) * (torch.digamma(alpha_prime) - torch.digamma(S_prime)), dim=1, keepdim=True)
    
    # Scale down the KL divergence heavily so the network actually learns the MSE loss
    return torch.mean(loss + 0.01 * annealing_coef * kl_div)

def train_evidential_model():
    print("=========================================")
    print("TRAINING EVIDENTIAL CONFORMAL MODEL (ECG)")
    print("=========================================")
    
    print("Loading datasets...")
    try:
        ds1 = load_dataset("deepset/prompt-injections", split="train")
        df = pd.DataFrame(ds1)[['text', 'label']]
        df['label'] = df['label'].astype(int)
    except Exception as e:
        print(f"Error loading datasets: {e}. Falling back.")
        dataset = load_dataset("deepset/prompt-injections", split="train")
        df = pd.DataFrame(dataset)
        
    df['multiclass_label'] = df.apply(lambda r: assign_threat_category(r['text'], r['label']), axis=1)
    
    train_df, temp_df = train_test_split(df, test_size=0.30, random_state=42, stratify=df['multiclass_label'])
    val_df, cal_df = train_test_split(temp_df, test_size=0.50, random_state=42, stratify=temp_df['multiclass_label'])
    
    print("Preprocessing text data...")
    cleaned_train = train_df['text'].apply(clean_text)
    cleaned_val = val_df['text'].apply(clean_text)
    cleaned_cal = cal_df['text'].apply(clean_text)
    
    models_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models'))
    vectorizer_path = os.path.join(models_dir, 'vectorizer.pkl')
    with open(vectorizer_path, 'rb') as f:
        vectorizer = pickle.load(f)
        
    X_train = vectorizer.transform(cleaned_train).toarray()
    X_val = vectorizer.transform(cleaned_val).toarray()
    X_cal = vectorizer.transform(cleaned_cal).toarray()
    
    y_train = train_df['multiclass_label'].values
    y_val = val_df['multiclass_label'].values
    y_cal = cal_df['multiclass_label'].values
    
    X_train_t = torch.FloatTensor(X_train)
    y_train_t = torch.LongTensor(y_train)
    y_train_onehot = torch.nn.functional.one_hot(y_train_t, num_classes=4).float()
    
    train_dataset = TensorDataset(X_train_t, y_train_onehot)
    train_loader = DataLoader(train_dataset, batch_size=128, shuffle=True)
    
    input_dim = X_train.shape[1]
    hidden_dim = 256
    output_dim = 4
    model = EDLModel(input_dim, hidden_dim, output_dim)
    optimizer = optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-4)
    
    epochs = 40
    print("Training EDL Network...")
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        for batch_x, batch_y in train_loader:
            optimizer.zero_grad()
            logits = model(batch_x)
            evidence = torch.nn.functional.softplus(logits)
            alpha = evidence + 1
            loss = edl_loss(logits, batch_y, alpha, epoch, output_dim, annealing_step=20)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        
        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f"Epoch {epoch+1}/{epochs} - Loss: {total_loss/len(train_loader):.4f}")
        
    print("Calibrating Conformal Prediction (EED Score)...")
    import math
    import collections
    
    def calc_entropy(text):
        if not text: return 0.0
        # Character-level Shannon Entropy
        freqs = collections.Counter(text)
        probs = [float(c) / len(text) for c in freqs.values()]
        entropy = -sum(p * math.log2(p) for p in probs)
        return entropy

    # Compute entropy for calibration set
    cal_texts = cal_df['text'].tolist()
    cal_entropies = np.array([calc_entropy(t) for t in cal_texts])
    
    model.eval()
    with torch.no_grad():
        X_cal_t = torch.FloatTensor(X_cal)
        logits_cal = model(X_cal_t)
        evidence_cal = torch.nn.functional.softplus(logits_cal)
        alpha_cal = evidence_cal + 1
        S_cal = torch.sum(alpha_cal, dim=1, keepdim=True)
        p_cal = alpha_cal / S_cal
        
        n = len(y_cal)
        s_scores = np.zeros(n)
        p_cal_np = p_cal.numpy()
        alpha_cal_np = alpha_cal.numpy()
        
        for i in range(n):
            # EED Score: e^(H(x)) / alpha_y
            # This perfectly suppresses benign high entropy (where evidence alpha is high),
            # but asymptotically spikes when evidence collapses to 1 (Zero-Day Attack)
            alpha_y = alpha_cal_np[i, y_cal[i]]
            s_scores[i] = math.exp(cal_entropies[i] / 2.0) / alpha_y  # scale entropy slightly for numerical stability
            
        alpha_level = 0.05
        q_level = np.ceil((n + 1) * (1 - alpha_level)) / n
        q_level = min(q_level, 1.0)
        q_hat = np.quantile(s_scores, q_level)
        print(f"Conformal Calibration q_hat_EED (95% guarantee): {q_hat:.4f}")
        
    print("Exporting raw weights for Vercel Serverless (NumPy inference)...")
    weights = {
        'W1': model.fc1.weight.detach().numpy().T,
        'b1': model.fc1.bias.detach().numpy(),
        'W2': model.fc2.weight.detach().numpy().T,
        'b2': model.fc2.bias.detach().numpy(),
        'q_hat': q_hat
    }
    
    export_path = os.path.join(models_dir, 'edl_weights.npz')
    np.savez(export_path, **weights)
    print(f"Saved NumPy weights to: {export_path}")
    print("=========================================")

if __name__ == "__main__":
    train_evidential_model()
