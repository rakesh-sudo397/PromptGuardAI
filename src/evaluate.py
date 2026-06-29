"""
Filename: src/evaluate.py
Action: MODIFY
Purpose: Evaluates the multi-class model, saves a 4x4 Confusion Matrix, and returns dictionary metrics.
"""

import sys
import os
import pickle
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datasets import load_dataset
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score

# Adjust path to find modules from the root PromptGuard-AI folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.preprocessing import clean_text
from src.core.multiclass_trainer import assign_threat_category

def evaluate_model():
    print("=========================================")
    print("EVALUATING MULTI-CLASS MODEL PERFORMANCE")
    print("=========================================")
    
    # 1. Load dataset and split (Must match splits from training)
    dataset = load_dataset("deepset/prompt-injections", split="train")
    df = pd.DataFrame(dataset)
    df['multiclass_label'] = df.apply(lambda r: assign_threat_category(r['text'], r['label']), axis=1)
    
    _, test_df = train_test_split(
        df, 
        test_size=0.20, 
        random_state=42, 
        stratify=df['multiclass_label']
    )
    
    # 2. Clean test text
    cleaned_test = test_df['text'].apply(clean_text)
    y_test = test_df['multiclass_label']
    
    # 3. Load Vectorizer and Classifier
    models_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models'))
    vectorizer_path = os.path.join(models_dir, 'vectorizer.pkl')
    model_path = os.path.join(models_dir, 'classifier.pkl')
    
    with open(vectorizer_path, 'rb') as f:
        vectorizer = pickle.load(f)
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
        
    # 4. Vectorize test text and predict
    X_test_tfidf = vectorizer.transform(cleaned_test)
    y_pred = model.predict(X_test_tfidf)
    
    # 5. Calculate and print metrics
    acc = accuracy_score(y_test, y_pred)
    print(f"Validation Cohort: {len(test_df)} Samples")
    print(f"Accuracy: {acc*100:.2f}%")
    print("\n--- Multi-Class Classification Report ---")
    print(classification_report(
        y_test, 
        y_pred, 
        target_names=["Clean", "Override", "Roleplay", "Leakage"]
    ))
    
    # 6. Generate and save 4x4 Confusion Matrix plot
    cm = confusion_matrix(y_test, y_pred)
    plt.figure(figsize=(8, 6))
    sns.heatmap(
        cm, 
        annot=True, 
        fmt='d', 
        cmap='Purples', 
        xticklabels=["Clean", "Override", "Roleplay", "Leakage"],
        yticklabels=["Clean", "Override", "Roleplay", "Leakage"]
    )
    plt.title('Confusion Matrix: PromptGuard Multi-Class Model')
    plt.ylabel('Actual Category')
    plt.xlabel('Predicted Category')
    
    docs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'docs'))
    os.makedirs(docs_dir, exist_ok=True)
        
    cm_path = os.path.join(docs_dir, 'confusion_matrix.png')
    plt.savefig(cm_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Confusion Matrix saved to: {cm_path}")
    print("=========================================")

def run_evaluation_metrics() -> dict:
    """
    Computes classification evaluation metrics and confusion matrix values.
    Returns a dictionary suitable for API responses.
    """
    # 1. Load dataset and split
    dataset = load_dataset("deepset/prompt-injections", split="train")
    df = pd.DataFrame(dataset)
    df['multiclass_label'] = df.apply(lambda r: assign_threat_category(r['text'], r['label']), axis=1)
    
    _, test_df = train_test_split(
        df, 
        test_size=0.20, 
        random_state=42, 
        stratify=df['multiclass_label']
    )
    
    # 2. Clean test text
    cleaned_test = test_df['text'].apply(clean_text)
    y_test = test_df['multiclass_label']
    
    # 3. Load Vectorizer and Classifier
    models_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models'))
    vectorizer_path = os.path.join(models_dir, 'vectorizer.pkl')
    model_path = os.path.join(models_dir, 'classifier.pkl')
    
    with open(vectorizer_path, 'rb') as f:
        vectorizer = pickle.load(f)
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
        
    # 4. Vectorize test text and predict
    X_test_tfidf = vectorizer.transform(cleaned_test)
    y_pred = model.predict(X_test_tfidf)
    
    # 5. Compute metrics
    acc = float(accuracy_score(y_test, y_pred))
    report = classification_report(
        y_test, 
        y_pred, 
        target_names=["Clean", "Override", "Roleplay", "Leakage"],
        output_dict=True
    )
    cm = confusion_matrix(y_test, y_pred)
    
    class_metrics = {}
    for cls_name in ["Clean", "Override", "Roleplay", "Leakage"]:
        if cls_name in report:
            class_metrics[cls_name] = {
                "precision": float(report[cls_name]["precision"]),
                "recall": float(report[cls_name]["recall"]),
                "f1": float(report[cls_name]["f1-score"])
            }
            
    return {
        "accuracy": acc,
        "class_metrics": class_metrics,
        "confusion_matrix": cm.tolist()
    }

if __name__ == "__main__":
    evaluate_model()