import os
import numpy as np

def relu(x):
    return np.maximum(0, x)

def softplus(x):
    return np.log1p(np.exp(-np.abs(x))) + np.maximum(x, 0)

class EvidentialConformalGuardrail:
    def __init__(self):
        models_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'models'))
        weights_path = os.path.join(models_dir, 'edl_weights.npz')
        
        if not os.path.exists(weights_path):
            raise FileNotFoundError(f"Missing EDL weights at {weights_path}. Run train_evidential.py first.")
            
        data = np.load(weights_path)
        self.W1 = data['W1']
        self.b1 = data['b1']
        self.W2 = data['W2']
        self.b2 = data['b2']
        self.q_hat = data['q_hat'].item()
        
        self.class_names = {
            0: "Clean",
            1: "Override",
            2: "Roleplay",
            3: "Leakage"
        }
        
    def _calc_entropy(self, text):
        import math
        import collections
        if not text: return 0.0
        freqs = collections.Counter(text)
        probs = [float(c) / len(text) for c in freqs.values()]
        entropy = -sum(p * math.log2(p) for p in probs)
        return entropy
        
    def predict(self, X_tfidf, raw_prompt=""):
        """
        Takes in a sparse TF-IDF vector and raw text, performs pure-NumPy inference.
        Returns probabilities, epistemic uncertainty, and the Conformal Prediction Set.
        """
        # Convert sparse to dense if necessary
        if hasattr(X_tfidf, "toarray"):
            X = X_tfidf.toarray()
        else:
            X = X_tfidf
            
        # Forward pass (MLP)
        hidden = relu(X @ self.W1 + self.b1)
        logits = hidden @ self.W2 + self.b2
        
        # Evidential outputs
        evidence = softplus(logits)
        alpha = evidence + 1.0
        S = np.sum(alpha, axis=1, keepdims=True)
        
        p = alpha / S
        u = 4.0 / S  # Epistemic uncertainty (K / S, where K=4)
        
        p = p[0]
        u = u[0][0]
        
        # Conformal Prediction Set (EED Score)
        H_raw = self._calc_entropy(raw_prompt)
        
        import math
        s_scores = np.zeros(4)
        for i in range(4):
            alpha_y = alpha[0][i]
            # EED Formula: e^(H/2) / alpha_y
            s_scores[i] = math.exp(H_raw / 2.0) / alpha_y
        
        pred_set_indices = np.where(s_scores <= self.q_hat)[0]
        pred_set = [self.class_names[idx] for idx in pred_set_indices]
        
        return {
            "probabilities": p.tolist(),
            "epistemic_uncertainty": float(u),
            "prediction_set": pred_set,
            "q_hat_threshold": float(self.q_hat),
            "entropy": float(H_raw)
        }
