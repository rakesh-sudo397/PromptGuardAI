"""
Filename: src/core/auth.py
Purpose: Cryptographically secure password hashing (PBKDF2-SHA256) and API key generation logic.
"""

import os
import hashlib
import secrets

# NIST recommended parameters for PBKDF2
ITERATIONS = 100000
HASH_ALGO = 'sha256'
SALT_SIZE = 16

def hash_password(password: str) -> str:
    """
    Generates a secure salt and hashes the password using PBKDF2-HMAC-SHA256.
    Returns: string in the format pbkdf2:sha256:iterations$salt$hash
    """
    salt = secrets.token_bytes(SALT_SIZE)
    pwd_bytes = password.encode('utf-8')
    dk = hashlib.pbkdf2_hmac(HASH_ALGO, pwd_bytes, salt, ITERATIONS)
    
    salt_hex = salt.hex()
    hash_hex = dk.hex()
    return f"pbkdf2:{HASH_ALGO}:{ITERATIONS}${salt_hex}${hash_hex}"

def verify_password(password: str, password_hash: str) -> bool:
    """
    Verifies a password against the stored pbkdf2 hash.
    """
    if not password or not password_hash:
        return False
    try:
        parts = password_hash.split('$')
        if len(parts) != 3:
            return False
        meta, salt_hex, hash_hex = parts
        
        # Verify algorithm parameters
        meta_parts = meta.split(':')
        if len(meta_parts) != 3 or meta_parts[0] != 'pbkdf2':
            return False
        algo = meta_parts[1]
        iterations = int(meta_parts[2])
        
        salt = bytes.fromhex(salt_hex)
        stored_hash = bytes.fromhex(hash_hex)
        
        pwd_bytes = password.encode('utf-8')
        dk = hashlib.pbkdf2_hmac(algo, pwd_bytes, salt, iterations)
        
        return secrets.compare_digest(dk, stored_hash)
    except Exception:
        return False

def generate_api_key() -> str:
    """
    Generates a secure, random developer API key prefixed with pg_live_.
    """
    # 24 random bytes -> 48 hex characters
    random_str = secrets.token_hex(24)
    return f"pg_live_{random_str}"

def generate_session_token() -> str:
    """
    Generates a secure session token for cookie-based browser authentication.
    """
    return secrets.token_urlsafe(32)
