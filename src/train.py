import sys
import os

# Adjust path to find modules from the root PromptGuard-AI folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pickle
import pandas as pd
from datasets import load_dataset
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from src.preprocessing import clean_text

def train_model():
    print("=========================================")
    print("TRAINING ML BASELINE MODEL (DAY 3)")
    print("=========================================")
    
    # 1. Load the dataset
    print("Loading deepset/prompt-injections dataset...")
    dataset = load_dataset("deepset/prompt-injections", split="train")
    df = pd.DataFrame(dataset)
    
    # 2. Perform Train/Test Split (80% Train, 20% Test)
    # Stratify makes sure both splits have the exact same ratio of safe vs injection prompts
    print("Splitting dataset (80/20 train/test split)...")
    train_df, test_df = train_test_split(
        df, 
        test_size=0.20, 
        random_state=42, 
        stratify=df['label']
    )
    print(f"Training samples: {len(train_df)} | Test samples: {len(test_df)}")
    
    # 3. Preprocess training set text
    print("Preprocessing training text...")
    cleaned_train = train_df['text'].apply(clean_text)
    
    # 4. Load the TF-IDF Vectorizer
    vectorizer_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models', 'vectorizer.pkl'))
    if not os.path.exists(vectorizer_path):
        print(f"Error: Fitted vectorizer not found at {vectorizer_path}. Run vectorizer.py first.")
        return
        
    with open(vectorizer_path, 'rb') as f:
        vectorizer = pickle.load(f)
    print("Vectorizer loaded successfully.")
    
    # 5. Transform cleaned training text into numerical vectors
    X_train_tfidf = vectorizer.transform(cleaned_train)
    y_train = train_df['label']
    
    # 6. Train Logistic Regression model
    print("Training Logistic Regression classifier...")
    model = LogisticRegression(random_state=42, class_weight='balanced')
    model.fit(X_train_tfidf, y_train)
    
    # 7. Serialize and save the model
    models_dir = os.path.dirname(vectorizer_path)
    model_path = os.path.join(models_dir, 'classifier.pkl')
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    
    print(f"Model trained successfully and saved to: {model_path}")
    print("=========================================")

if __name__ == "__main__":
    train_model()