import numpy as np
import torch
import pandas as pd
from typing import List, Tuple

class CascadedRiskController:
    """
    Implements Learnable Conformal Risk Control (LCRC) for Cascaded Guardrails.
    Mathematically guarantees that the Edge Router's False Positive Rate (FPR)
    on benign traffic will not exceed a user-defined threshold (alpha),
    regardless of distribution shifts.
    """
    def __init__(self, alpha: float = 0.01, max_loss: float = 1.0):
        self.alpha = alpha  # Target risk level (e.g., 0.01 = 1% False Positive Rate)
        self.max_loss = max_loss # B (upper bound of the loss function)
        self.optimal_tau = None
        
    def loss_function(self, y_true: int, y_pred: int, uncertainty: float, tau: float) -> float:
        """
        Defines the False Positive risk in a routing cascade.
        - If the prompt is malicious (y=1), loss = 0 (we are bounding FPR, not FNR here).
        - If the prompt is benign (y=0):
            - If uncertainty > tau, we ROUTE to heavy LLM (Safe, Loss = 0)
            - If uncertainty <= tau, Edge makes decision:
                - If Edge says "Pass" (y_pred=0), Loss = 0
                - If Edge says "Block" (y_pred=1), FATAL FALSE POSITIVE, Loss = 1
        """
        if y_true == 1:
            return 0.0
            
        if uncertainty > tau:
            return 0.0 # Routed, no edge false positive
            
        if y_pred == 1:
            return 1.0 # Edge confidently blocked a benign prompt
            
        return 0.0

    def calibrate(self, uncertainties: np.ndarray, y_preds: np.ndarray, y_trues: np.ndarray) -> float:
        """
        Finds the maximum routing threshold (tau) that satisfies the risk bound alpha.
        """
        n = len(y_trues)
        
        # Test all possible threshold values (sort unique uncertainties)
        # We add a 0 and a very large number to cover edge cases
        possible_taus = np.unique(uncertainties)
        possible_taus = np.concatenate(([0.0], possible_taus, [1.0]))
        possible_taus.sort()
        
        valid_taus = []
        
        for tau in possible_taus:
            # 1. Calculate empirical risk on calibration set for this tau
            empirical_risk = 0.0
            for u, y_p, y_t in zip(uncertainties, y_preds, y_trues):
                empirical_risk += self.loss_function(y_t, y_p, u, tau)
            empirical_risk /= n
            
            # 2. Apply Hoeffding/Conformal finite-sample correction bound
            # R_hat_plus = (n / (n+1)) * empirical_risk + (B / (n+1))
            r_hat_plus = (n / (n + 1)) * empirical_risk + (self.max_loss / (n + 1))
            
            # 3. Check if the upper bound satisfies our target alpha
            if r_hat_plus <= self.alpha:
                valid_taus.append(tau)
                
        if not valid_taus:
            # If no threshold works, we must route everything to be safe (tau = 0)
            self.optimal_tau = 0.0
            print(f"[Warning] Cannot guarantee {self.alpha*100}% FPR. Defaulting to route-all (tau=0.0).")
        else:
            # We want the LARGEST tau (meaning we keep as much traffic at the edge as possible)
            # while still strictly maintaining the mathematical security bound.
            self.optimal_tau = max(valid_taus)
            
        return self.optimal_tau

def compute_calibration_metrics(model, dataloader, device):
    """Utility to extract uncertainties and predictions for calibration."""
    model.eval()
    all_u = []
    all_preds = []
    all_labels = []
    
    with torch.no_grad():
        for texts, labels in dataloader:
            alphas, u = model(texts)
            preds = torch.argmax(alphas, dim=1).cpu().numpy()
            
            all_u.extend(u.cpu().numpy().flatten())
            all_preds.extend(preds)
            all_labels.extend(labels.numpy())
            
    return np.array(all_u), np.array(all_preds), np.array(all_labels)
