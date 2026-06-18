import sys
import os

# Adjust path to find modules from the root PromptGuard-AI folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pickle
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datasets import load_dataset
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, precision_score, recall_score, f1_score
from src.preprocessing import clean_text

def evaluate_model():
    print("=========================================")
    print("EVALUATING MODEL PERFORMANCE (DAY 3)")
    print("=========================================")
    
    # 1. Load dataset and split (Must match split from train.py)
    dataset = load_dataset("deepset/prompt-injections", split="train")
    df = pd.DataFrame(dataset)
    _, test_df = train_test_split(
        df, 
        test_size=0.20, 
        random_state=42, 
        stratify=df['label']
    )
    
    # 2. Clean test text
    cleaned_test = test_df['text'].apply(clean_text)
    y_test = test_df['label']
    
    # 3. Load Vectorizer and Classifier
    models_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models'))
    vectorizer_path = os.path.join(models_dir, 'vectorizer.pkl')
    model_path = os.path.join(models_dir, 'classifier.pkl')
    
    with open(vectorizer_path, 'rb') as f:
        vectorizer = pickle.load(f)
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
        
    # 4. Vectorize test text
    X_test_tfidf = vectorizer.transform(cleaned_test)
    
    # 5. Generate predictions
    y_pred = model.predict(X_test_tfidf)
    
    # 6. Calculate and print metrics
    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred)
    rec = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    
    print(f"Validation Cohort: {len(test_df)} Samples")
    print(f"Accuracy:  {acc*100:.2f}%")
    print(f"Precision: {prec*100:.2f}% (Safety blocks that were actually attacks)")
    print(f"Recall:    {rec*100:.2f}% (Actual attacks caught by model)")
    print(f"F1 Score:  {f1*100:.2f}%")
    print("\n--- Detailed Classification Report ---")
    print(classification_report(y_test, y_pred, target_names=["Safe", "Injection"]))
    
    # 7. Generate and save Confusion Matrix plot
    cm = confusion_matrix(y_test, y_pred)
    plt.figure(figsize=(6, 5))
    sns.heatmap(
        cm, 
        annot=True, 
        fmt='d', 
        cmap='Blues', 
        xticklabels=['Predicted Safe', 'Predicted Injection'],
        yticklabels=['Actual Safe', 'Actual Injection']
    )
    plt.title('Confusion Matrix: PromptGuard Baseline')
    plt.ylabel('Actual Label')
    plt.xlabel('Predicted Label')
    
    docs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'docs'))
    if not os.path.exists(docs_dir):
        os.makedirs(docs_dir)
        
    cm_path = os.path.join(docs_dir, 'confusion_matrix.png')
    plt.savefig(cm_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Confusion Matrix visualization saved to: {cm_path}")
    print("=========================================")

if __name__ == "__main__":
    evaluate_model()