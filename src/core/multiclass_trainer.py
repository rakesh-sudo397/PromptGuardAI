import sys
import os

# Adjust path to find modules from the root PromptGuard-AI folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import pickle
import pandas as pd
from datasets import load_dataset
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from src.preprocessing import clean_text

def assign_threat_category(text: str, label: int) -> int:
    """
    Heuristically maps binary injection prompts (label=1) to 3 threat classes,
    while keeping safe prompts as label=0.
    """
    if label == 0:
        return 0 # Class 0: Clean Query
        
    text_lower = text.lower()
    
    # 1. Class 2: Roleplay / Impersonation
    if any(w in text_lower for w in ["act as", "roleplay", "pretend", "dan", "unrestricted", "simulation", "you are"]):
        return 2
        
    # 2. Class 3: System Prompt Leakage
    if any(w in text_lower for w in ["system", "instructions", "rules", "leak", "expose", "reveal", "print"]):
        return 3
        
    # 3. Class 1: Direct Instruction Override (Fallback)
    return 1

def train_multiclass_model():
    print("=========================================")
    print("TRAINING MULTI-CLASS TAXONOMY MODEL (DAY 6)")
    print("=========================================")
    
    # 1. Load dataset
    print("Loading combined datasets (deepset, xTRam1, neuralchemy, imoxto) from Hugging Face...")
    try:
        ds1 = load_dataset("deepset/prompt-injections", split="train")
        df1 = pd.DataFrame(ds1)[['text', 'label']]
        ds2 = load_dataset("xTRam1/safe-guard-prompt-injection", split="train")
        df2 = pd.DataFrame(ds2)[['text', 'label']]
        ds3 = load_dataset("neuralchemy/Prompt-injection-dataset", split="train")
        df3 = pd.DataFrame(ds3)[['text', 'label']]
        ds4 = load_dataset("imoxto/prompt_injection_cleaned_dataset-v2", split="train")
        df4 = pd.DataFrame(ds4)[['text', 'labels']].rename(columns={'labels': 'label'})
        df4 = df4.sample(n=min(10000, len(df4)), random_state=42)
        df = pd.concat([df1, df2, df3, df4], ignore_index=True)
        df['label'] = df['label'].astype(int)
    except Exception as e:
        print(f"Error combining datasets: {e}. Falling back to default deepset/prompt-injections.")
        dataset = load_dataset("deepset/prompt-injections", split="train")
        df = pd.DataFrame(dataset)
    
    # 2. Apply taxonomy mapping
    print("Applying taxonomy labeling heuristic...")
    df['multiclass_label'] = df.apply(lambda row: assign_threat_category(row['text'], row['label']), axis=1)
    
    print("\nTaxonomy Class Distribution:")
    print("  Class 0 (Clean Query):          ", sum(df['multiclass_label'] == 0))
    print("  Class 1 (Instruction Override): ", sum(df['multiclass_label'] == 1))
    print("  Class 2 (Roleplay Jailbreak):   ", sum(df['multiclass_label'] == 2))
    print("  Class 3 (System Prompt Leak):   ", sum(df['multiclass_label'] == 3))
    
    # 3. Split dataset (80/20 Train/Test)
    train_df, test_df = train_test_split(
        df, 
        test_size=0.20, 
        random_state=42, 
        stratify=df['multiclass_label']
    )
    
    # 4. Clean text and load vectorizer
    print("\nPreprocessing text data...")
    cleaned_train = train_df['text'].apply(clean_text)
    cleaned_test = test_df['text'].apply(clean_text)
    
    models_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'models'))
    vectorizer_path = os.path.join(models_dir, 'vectorizer.pkl')
    
    with open(vectorizer_path, 'rb') as f:
        vectorizer = pickle.load(f)
        
    X_train = vectorizer.transform(cleaned_train)
    X_test = vectorizer.transform(cleaned_test)
    
    y_train = train_df['multiclass_label']
    y_test = test_df['multiclass_label']
    
    # 5. Fit Multinomial Logistic Regression model
    print("Fitting multinomial logistic regression classifier...")
    # Unweighted and compatible with all scikit-learn versions
    model = LogisticRegression(
        solver='lbfgs', 
        random_state=42, 
        max_iter=1000,
        class_weight='balanced'
    )
    model.fit(X_train, y_train)
    
    # 6. Evaluate multi-class metrics
    y_pred = model.predict(X_test)
    print("\n--- Multi-Class Classification Metrics ---")
    print(classification_report(
        y_test, 
        y_pred, 
        target_names=["Clean", "Override", "Roleplay", "Leakage"]
    ))
    
    # 7. Overwrite classifier.pkl with our new multi-class model
    model_path = os.path.join(models_dir, 'classifier.pkl')
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    print(f"Serialized multi-class model saved to: {model_path}")
    print("=========================================")

if __name__ == "__main__":
    train_multiclass_model()