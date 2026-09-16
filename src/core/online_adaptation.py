import torch
import torch.optim as optim
from collections import deque
import random
import sys
import os
import numpy as np

# Adjust path to find modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.core.transformer_ecg import ECGTransformerModel
from src.core.risk_control import CascadedRiskController

class EvidentialSelfHealer:
    """
    Novelty 3: Online Test-Time Adaptation (Self-Healing) for Guard AI.
    Intercepts the Heavy LLM's (Oracle) verdict on routed zero-day attacks and
    updates the Edge Model's Dirichlet parameters in real-time, completely bounded
    by the Conformal Risk Controller to prevent catastrophic forgetting of benign code.
    """
    def __init__(self, model_path, initial_calibration_csv=None, device='cpu'):
        self.device = device
        self.model_path = model_path
        self.model = ECGTransformerModel(num_classes=2).to(self.device)
        
        if os.path.exists(model_path):
            checkpoint = torch.load(model_path, map_location=self.device, weights_only=True)
            self.model.load_state_dict(checkpoint['model_state_dict'])
            self.current_tau = checkpoint.get('q_hat', 1.0)
        else:
            raise FileNotFoundError(f"Base model not found at {model_path}. Run research_train.py first.")
            
        # Optimize ONLY the Evidential Head (keeps adaptation microsecond-fast)
        self.optimizer = optim.Adam(self.model.evidential_head.parameters(), lr=5e-4)
        
        # Replay Buffer (Memory) to prevent the model from forgetting what benign code looks like
        self.replay_buffer = deque(maxlen=1000)
        
        # Initialize CRC Shield
        self.risk_controller = CascadedRiskController(alpha=0.01) # Strict 1% FPR Guarantee
        
        if initial_calibration_csv and os.path.exists(initial_calibration_csv):
            import pandas as pd
            df = pd.read_csv(initial_calibration_csv)
            for _, row in df.iterrows():
                self.replay_buffer.append((row['text'], row['label']))

    def edl_loss(self, alpha, target):
        """Standard Type-II Maximum Likelihood Loss for quick online updates"""
        y = torch.eye(2).to(self.device)[target]
        S = torch.sum(alpha, dim=1, keepdim=True)
        p = alpha / S
        err = (y - p) ** 2
        var = (p * (1 - p)) / (S + 1)
        return torch.mean(torch.sum(err + var, dim=1))

    def adapt(self, new_prompt: str, oracle_label: int):
        """
        Real-time single-step adaptation. Called whenever the Heavy LLM returns a verdict.
        """
        self.model.train()
        self.optimizer.zero_grad()
        
        # Batching: The new Zero-Day + 7 random memories to prevent catastrophic forgetting
        batch_texts = [new_prompt]
        batch_labels = [oracle_label]
        
        if len(self.replay_buffer) > 0:
            samples = random.sample(self.replay_buffer, min(7, len(self.replay_buffer)))
            batch_texts.extend([s[0] for s in samples])
            batch_labels.extend([s[1] for s in samples])
            
        batch_labels_tensor = torch.tensor(batch_labels).to(self.device)
        
        # Forward pass (Extract evidence)
        alphas, _ = self.model(batch_texts)
        loss = self.edl_loss(alphas, batch_labels_tensor)
        
        # Backward pass (Heal the model)
        loss.backward()
        self.optimizer.step()
        
        # Add new knowledge to memory
        self.replay_buffer.append((new_prompt, oracle_label))
        
        # RECALIBRATE THE MATHEMATICAL SHIELD
        self._recalibrate()
        
        # Save the healed weights
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'q_hat': self.current_tau
        }, self.model_path)
        
        return loss.item(), self.current_tau
        
    def _recalibrate(self):
        """Dynamically updates the routing threshold tau using Conformal Risk Control."""
        self.model.eval()
        texts = [s[0] for s in self.replay_buffer]
        labels = [s[1] for s in self.replay_buffer]
        
        with torch.no_grad():
            all_u = []
            all_preds = []
            for i in range(0, len(texts), 32):
                batch_t = texts[i:i+32]
                alphas, u = self.model(batch_t)
                preds = torch.argmax(alphas, dim=1).cpu().numpy()
                all_u.extend(u.cpu().numpy().flatten())
                all_preds.extend(preds)
                
        # Calculate new guaranteed threshold
        self.current_tau = self.risk_controller.calibrate(
            np.array(all_u), np.array(all_preds), np.array(labels)
        )
