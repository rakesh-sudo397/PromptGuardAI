import re
import string
import base64

def strip_zero_width_characters(text: str) -> str:
    """
    Strips invisible unicode characters (zero-width spaces) commonly used
    by attackers to evade regex filters (e.g. i\u200bn\u200bs\u200bt...).
    """
    if not text:
        return ""
    zero_width_chars = ["\u200b", "\u200c", "\u200d", "\ufeff"]
    for char in zero_width_chars:
        text = text.replace(char, "")
    return text

def decode_base64_payloads(text: str) -> str:
    """
    Scans text for potential Base64 substrings, decodes them if valid, 
    and appends the decoded text to the end of the prompt.
    """
    if not text:
        return ""
        
    b64_pattern = re.compile(r'\b[A-Za-z0-9+/]{8,}=*\b')
    matches = b64_pattern.findall(text)
    
    decoded_payloads = []
    for match in matches:
        try:
            padded_match = match + "=" * ((4 - len(match) % 4) % 4)
            decoded_bytes = base64.b64decode(padded_match, validate=True)
            decoded_str = decoded_bytes.decode('utf-8', errors='ignore').strip()
            
            if decoded_str and all(c in string.printable for c in decoded_str) and len(decoded_str) > 3:
                decoded_payloads.append(decoded_str)
        except Exception:
            continue
            
    if decoded_payloads:
        return text + " " + " ".join(decoded_payloads)
    return text

def normalize_leetspeak(text: str) -> str:
    """
    Translates common leet-speak character substitutions back to standard letters.
    """
    if not text:
        return ""
        
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
    
    words = text.split()
    normalized_words = []
    
    for word in words:
        has_letters = any(c.isalpha() for c in word)
        has_leet = any(c in leet_dict for c in word)
        
        if has_letters and has_leet:
            new_word = "".join([leet_dict[c] if c in leet_dict else c for c in word])
            normalized_words.append(new_word)
        else:
            normalized_words.append(word)
            
    return " ".join(normalized_words)

def redact_pii_features(text: str) -> (str, int):
    """
    Scans the prompt for PII (emails, phone numbers, API keys, credentials)
    and replaces them with redaction placeholders. Returns (redacted_text, count).
    """
    if not text:
        return ("", 0)
        
    redacted = text
    count = 0
    
    # 1. Emails
    email_pattern = re.compile(r'\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b')
    emails = email_pattern.findall(redacted)
    if emails:
        count += len(emails)
        redacted = email_pattern.sub("[REDACTED_EMAIL]", redacted)
        
    # 2. API Keys & Live Tokens (e.g. pg_live_..., sk_..., api_...)
    api_pattern = re.compile(r'\b(?:sk|pg|api)_[a-zA-Z0-9]{12,64}\b')
    api_keys = api_pattern.findall(redacted)
    if api_keys:
        count += len(api_keys)
        redacted = api_pattern.sub("[REDACTED_API_KEY]", redacted)
        
    # 3. Phone Numbers
    phone_pattern = re.compile(r'\b(?:\+?\d{1,3}[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b')
    phones = phone_pattern.findall(redacted)
    if phones:
        count += len(phones)
        redacted = phone_pattern.sub("[REDACTED_PHONE]", redacted)
        
    # 4. Credit Cards
    cc_pattern = re.compile(r'\b(?:\d{4}[- ]?){3}\d{4}\b')
    ccs = cc_pattern.findall(redacted)
    if ccs:
        count += len(ccs)
        redacted = cc_pattern.sub("[REDACTED_CREDENTIAL]", redacted)
        
    return redacted, count

def auto_scrub_payloads(text: str) -> str:
    """
    Active Defense: Sanitizes and neutralizes known prompt injection commands.
    """
    if not text:
        return ""
        
    scrubbed = text
    
    # Common attack signatures to clean/neutralize
    scrub_patterns = [
        (r'(?i)ignore\s+all\s+(?:previous\s+)?instructions', '[SCRUBBED_INSTRUCTION_OVERRIDE]'),
        (r'(?i)ignore\s+all\s+rules', '[SCRUBBED_RULE_OVERRIDE]'),
        (r'(?i)forget\s+(?:everything|what\s+i\s+said|previous\s+rules)', '[SCRUBBED_CONTEXT_WIPE]'),
        (r'(?i)you\s+are\s+now\s+a\s+simulated\s+system\s+administrator', '[SCRUBBED_SIMULATION]'),
        (r'(?i)you\s+are\s+now\s+(?:dan|unrestricted)', '[SCRUBBED_ROLEPLAY]'),
        (r'(?i)system\s+leakage|reveal\s+secret|output\s+system\s+prompt', '[SCRUBBED_LEAK_ATTEMPT]')
    ]
    
    for pattern, repl in scrub_patterns:
        scrubbed = re.sub(pattern, repl, scrubbed)
        
    return scrubbed

def clean_text(text: str) -> str:
    """
    Cleans raw prompt text by lowercasing, decoding base64/hex blocks,
    translating leet-speak, removing excess whitespace, and stripping punctuation.
    """
    if not text or not isinstance(text, str):
        return ""
    
    # 1. Strip zero-width spacing
    text_processed = strip_zero_width_characters(text)
    
    # 2. Detect and decode base64 payloads
    text_processed = decode_base64_payloads(text_processed)
    
    # 3. Translate leet-speak words
    text_processed = normalize_leetspeak(text_processed)
    
    # 4. Lowercase all text
    text_cleaned = text_processed.lower()
    
    # 5. Replace newlines and tabs with spaces
    text_cleaned = re.sub(r'\s+', ' ', text_cleaned)
    
    # 6. Strip punctuation (preserving separators like '-' and '#')
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