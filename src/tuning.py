import sys
import os

# Adjust path to find modules from the root PromptGuard-AI folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pickle
import pandas as pd
import numpy as np
from datasets import load_dataset
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score
from src.preprocessing import clean_text

def tune_threshold():
    print("=========================================")
    print("EVALUATING CLASSIFICATION THRESHOLDS (DAY 4)")
    print("=========================================")
    
    # 1. Load test split
    dataset = load_dataset("deepset/prompt-injections", split="train")
    df = pd.DataFrame(dataset)
    _, test_df = train_test_split(
        df, 
        test_size=0.20, 
        random_state=42, 
        stratify=df['label']
    )
    
    cleaned_test = test_df['text'].apply(clean_text)
    y_test = test_df['label']
    
    # 2. Load model and vectorizer
    models_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models'))
    vectorizer_path = os.path.join(models_dir, 'vectorizer.pkl')
    model_path = os.path.join(models_dir, 'classifier.pkl')
    
    with open(vectorizer_path, 'rb') as f:
        vectorizer = pickle.load(f)
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
        
    # 3. Vectorize test text
    X_test_tfidf = vectorizer.transform(cleaned_test)
    
    # 4. Get probability predictions for the injection class (class 1)
    y_probs = model.predict_proba(X_test_tfidf)[:, 1]
    
    # 5. Evaluate thresholds from 0.1 to 0.9
    thresholds = np.arange(0.1, 1.0, 0.05)
    
    print(f"{'Threshold':<10} | {'Accuracy':<8} | {'Precision':<9} | {'Recall':<8} | {'F1-Score':<8}")
    print("-" * 55)
    
    best_f1 = 0
    best_threshold = 0.5
    
    for t in thresholds:
        # Classify as 1 (Injection) if probability exceeds threshold t
        preds = (y_probs >= t).astype(int)
        
        acc = accuracy_score(y_test, preds)
        prec = precision_score(y_test, preds, zero_division=0)
        rec = recall_score(y_test, preds, zero_division=0)
        f1 = f1_score(y_test, preds, zero_division=0)
        
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = t
            
        print(f"{t:<10.2f} | {acc*100:<7.2f}% | {prec*100:<8.2f}% | {rec*100:<7.2f}% | {f1*100:<7.2f}%")
        
    print("-" * 55)
    print(f"Optimal Threshold (Max F1-Score): {best_threshold:.2f} (F1: {best_f1*100:.2f}%)")
    print("=========================================")

if __name__ == "__main__":
    tune_threshold()