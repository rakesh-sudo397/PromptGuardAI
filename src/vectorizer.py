import sys
import os

# Adjust path to find modules from the root PromptGuard-AI folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pickle
import pandas as pd
from datasets import load_dataset
from sklearn.feature_extraction.text import TfidfVectorizer
from src.preprocessing import clean_text

def build_vectorizer():
    print("=========================================")
    print("BUILDING TF-IDF VECTORIZER (DAY 2)")
    print("=========================================")
    
    # 1. Load the dataset
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
    
    # 2. Clean the prompts using our preprocessing module
    print("Cleaning prompts...")
    df['cleaned_text'] = df['text'].apply(clean_text)
    
    # 3. Initialize the TF-IDF Vectorizer
    # We use a max of 1000 features and set ngram_range=(1, 2) 
    # to capture single words and two-word phrases (like "ignore instructions")
    vectorizer = TfidfVectorizer(max_features=3000, ngram_range=(1, 2))
    
    # 4. Fit the vectorizer on our cleaned text
    print("Fitting vectorizer on cleaned text...")
    X_tfidf = vectorizer.fit_transform(df['cleaned_text'])
    
    print(f"Vocabulary fitted successfully. Feature matrix shape: {X_tfidf.shape}")
    
    # 5. Create models directory if it doesn't exist
    models_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models'))
    if not os.path.exists(models_dir):
        os.makedirs(models_dir)
        print(f"Created models directory at: {models_dir}")
        
    # 6. Save the fitted vectorizer
    vectorizer_path = os.path.join(models_dir, 'vectorizer.pkl')
    with open(vectorizer_path, 'wb') as f:
        pickle.dump(vectorizer, f)
    print(f"Saved fitted vectorizer to: {vectorizer_path}")
    
    # 7. Print top 15 words/phrases with highest average TF-IDF scores
    print("\nTop 15 features in vocabulary:")
    feature_names = vectorizer.get_feature_names_out()
    # Compute mean TF-IDF value for each feature column across the entire dataset
    mean_tfidf = X_tfidf.mean(axis=0).A1
    tfidf_ranking = pd.Series(mean_tfidf, index=feature_names).sort_values(ascending=False)
    print(tfidf_ranking.head(15))
    print("=========================================")

if __name__ == "__main__":
    build_vectorizer()