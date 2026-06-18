import re
import string
import base64

def decode_base64_payloads(text: str) -> str:
    """
    Scans text for potential Base64 substrings, decodes them if valid, 
    and appends the decoded text to the end of the prompt.
    """
    if not text:
        return ""
        
    # Regex to find potential base64 patterns (letters, numbers, +, /, and = padding)
    # Looking for word-like chunks that are at least 8 characters long
    b64_pattern = re.compile(r'\b[A-Za-z0-9+/]{8,}=*\b')
    matches = b64_pattern.findall(text)
    
    decoded_payloads = []
    for match in matches:
        try:
            # Add padding if missing
            padded_match = match + "=" * ((4 - len(match) % 4) % 4)
            decoded_bytes = base64.b64decode(padded_match, validate=True)
            decoded_str = decoded_bytes.decode('utf-8', errors='ignore').strip()
            
            # Check if decoded payload contains printable ascii characters (not binary garbage)
            if decoded_str and all(c in string.printable for c in decoded_str) and len(decoded_str) > 3:
                decoded_payloads.append(decoded_str)
        except Exception:
            # If it's not valid base64 (just a long word), ignore and proceed
            continue
            
    if decoded_payloads:
        # Append the decoded text so the TF-IDF feature columns can read it
        return text + " " + " ".join(decoded_payloads)
    return text

def normalize_leetspeak(text: str) -> str:
    """
    Translates common leet-speak character substitutions back to standard letters.
    """
    if not text:
        return ""
        
    # Define translation dictionary
    leet_dict = {
        '1': 'i',
        '0': 'o',
        '3': 'e',
        '4': 'a',
        '5': 's',
        '7': 't',
        '@': 'a',
        '$': 's'
    }
    
    # We only want to substitute characters if they are embedded within words 
    # to avoid changing actual numbers (e.g. dates or quantities).
    words = text.split()
    normalized_words = []
    
    for word in words:
        # Check if the word contains a mix of digits/symbols and letters (obfuscation pattern)
        has_letters = any(c.isalpha() for c in word)
        has_leet = any(c in leet_dict for c in word)
        
        if has_letters and has_leet:
            new_word = "".join([leet_dict[c] if c in leet_dict else c for c in word])
            normalized_words.append(new_word)
        else:
            normalized_words.append(word)
            
    return " ".join(normalized_words)

def clean_text(text: str) -> str:
    """
    Cleans raw prompt text by lowercasing, decoding base64 blocks,
    translating leet-speak, removing excess whitespace, and stripping punctuation.
    """
    if not text or not isinstance(text, str):
        return ""
    
    # 1. Detect and decode base64 payloads
    text_processed = decode_base64_payloads(text)
    
    # 2. Translate leet-speak words
    text_processed = normalize_leetspeak(text_processed)
    
    # 3. Lowercase all text
    text_cleaned = text_processed.lower()
    
    # 4. Replace newlines and tabs with spaces
    text_cleaned = re.sub(r'\s+', ' ', text_cleaned)
    
    # 5. Strip punctuation (preserving separators like '-' and '#')
    allowed_chars = string.ascii_lowercase + string.digits + " -#"
    text_cleaned = "".join([char for char in text_cleaned if char in allowed_chars])
    
    return text_cleaned.strip()

def extract_metadata_features(text: str) -> dict:
    """
    Extracts statistical metadata features from raw prompts.
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
    
    uppercase_count = sum(1 for char in text if char.isupper())
    uppercase_ratio = uppercase_count / char_len if char_len > 0 else 0.0
    
    exclamation_count = text.count("!")
    
    return {
        "char_length": char_len,
        "word_count": word_count,
        "uppercase_ratio": round(uppercase_ratio, 4),
        "exclamation_count": exclamation_count
    }