import re
import string

def clean_text(text: str) -> str:
    """
    Cleans raw prompt text by lowercasing, removing excess whitespace, 
    and stripping common punctuation.
    
    Args:
        text (str): The raw prompt string.
        
    Returns:
        str: The cleaned and normalized string.
    """
    if not text or not isinstance(text, str):
        return ""
    
    # 1. Lowercase all text
    text_cleaned = text.lower()
    
    # 2. Replace newlines and tabs with single spaces
    text_cleaned = re.sub(r'\s+', ' ', text_cleaned)
    
    # 3. Strip punctuation (except for separators like '#' and '-' which can be boundary markers)
    allowed_chars = string.ascii_lowercase + string.digits + " -#"
    text_cleaned = "".join([char for char in text_cleaned if char in allowed_chars])
    
    # 4. Remove extra whitespaces
    return text_cleaned.strip()

def extract_metadata_features(text: str) -> dict:
    """
    Extracts statistical metadata features from raw prompts.
    These features act as supplementary signals alongside TF-IDF.
    
    Args:
        text (str): The raw prompt string.
        
    Returns:
        dict: A dictionary containing engineered features.
    """
    if not text or not isinstance(text, str):
        return {
            "char_length": 0,
            "word_count": 0,
            "uppercase_ratio": 0.0,
            "exclamation_count": 0
        }
        
    char_len = len(text)
    words = text.split()
    word_count = len(words)
    
    # Count uppercase letters (common in instructions like "IGNORE", "STOP")
    uppercase_count = sum(1 for char in text if char.isupper())
    uppercase_ratio = uppercase_count / char_len if char_len > 0 else 0.0
    
    # Count exclamation points (often used in urgent overrides)
    exclamation_count = text.count("!")
    
    return {
        "char_length": char_len,
        "word_count": word_count,
        "uppercase_ratio": round(uppercase_ratio, 4),
        "exclamation_count": exclamation_count
    }