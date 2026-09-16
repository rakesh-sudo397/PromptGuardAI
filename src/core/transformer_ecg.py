import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModel
import math
from collections import Counter

class EvidentialHead(nn.Module):
    """
    Replaces standard Softmax with a Type-II Maximum Likelihood Evidential Head.
    Outputs Dirichlet distribution parameters (alpha).
    """
    def __init__(self, input_dim, num_classes):
        super().__init__()
        self.fc1 = nn.Linear(input_dim, 128)
        self.dropout = nn.Dropout(0.2)
        self.fc2 = nn.Linear(128, num_classes)
        
    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        logits = self.fc2(x)
        # Softplus ensures evidence is non-negative
        evidence = F.softplus(logits)
        # Alpha = evidence + 1 (Base Dirichlet Prior)
        alpha = evidence + 1.0
        return alpha

class ECGTransformerModel(nn.Module):
    """
    Evidential Conformal Guardrail (ECG) Model.
    Combines dense semantic embeddings with Evidential Deep Learning.
    """
    def __init__(self, model_name='sentence-transformers/all-MiniLM-L6-v2', num_classes=2):
        super().__init__()
        # 1. Base Dense Embedding Model
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.transformer = AutoModel.from_pretrained(model_name)
        
        # 2. Custom Evidential Head
        self.evidential_head = EvidentialHead(self.transformer.config.hidden_size, num_classes)
        self.num_classes = num_classes

    def encode_text(self, text_list):
        """Generates dense semantic embeddings (handles OOD tokens better than TF-IDF)."""
        inputs = self.tokenizer(text_list, padding=True, truncation=True, max_length=128, return_tensors="pt")
        
        # Move inputs to same device as model
        device = next(self.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        outputs = self.transformer(**inputs)
        
        # Mean pooling
        attention_mask = inputs['attention_mask']
        token_embeddings = outputs.last_hidden_state
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        embeddings = torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)
        return embeddings

    def compute_normalized_entropy(self, text):
        """
        Calculates Character-Level Shannon Entropy of the raw string.
        Normalized by log2(length) to prevent exponential explosion on massive developer prompts.
        """
        if not text: return 0.0
        freqs = Counter(text)
        probs = [float(c) / len(text) for c in freqs.values()]
        entropy = -sum(p * math.log2(p) for p in probs)
        
        # Length normalization (Crucial for EED numerical stability)
        norm_entropy = entropy / math.log2(len(text) + 2)
        return norm_entropy

    def forward(self, text_list):
        """Returns Dirichlet alphas and Epistemic Uncertainty (u)."""
        embeddings = self.encode_text(text_list)
        alphas = self.evidential_head(embeddings)
        
        # Total Evidence (S) = Sum of alphas
        S = torch.sum(alphas, dim=1, keepdim=True)
        # Epistemic Uncertainty (u) = K / S
        u = self.num_classes / S
        
        return alphas, u
        
    def compute_eed_score(self, alpha_y, raw_text, epsilon=1e-6):
        """
        Evidential-Entropy Divergence (EED) Score.
        Formula: S_EED = e^(H_norm) / (alpha_y + epsilon)
        """
        norm_entropy = self.compute_normalized_entropy(raw_text)
        # Add epsilon to strictly prevent division by zero edge-cases
        alpha_safe = alpha_y + epsilon
        
        eed_score = math.exp(norm_entropy) / alpha_safe
        return eed_score
