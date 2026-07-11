import re

class StreamingSanitizer:
    def __init__(self):
        self.buffer = ""
        # Sensitive patterns to redact in real-time outputs
        self.pii_patterns = [
            # Email address regex
            (re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'), "[REDACTED_EMAIL]"),
            # API key patterns (pg_live_..., sk_live_...)
            (re.compile(r'\b(?:pg|sk)_(?:live|test)_[a-zA-Z0-9]{12,60}\b'), "[REDACTED_API_KEY]"),
            # Generic credentials / secret keys
            (re.compile(r'\b(?:password|secret|token)\s*[:=]\s*[^\s]{6,50}\b', re.IGNORECASE), "[REDACTED_SECRET]")
        ]

    def process_chunk(self, chunk: str) -> str:
        """
        Appends the new chunk to the buffer, identifies word boundaries, 
        redacts sensitive data, and returns the safe leading portion of the buffer.
        """
        self.buffer += chunk
        
        # Search backwards for the last word/sentence boundary
        split_idx = -1
        for i in range(len(self.buffer) - 1, -1, -1):
            if self.buffer[i] in (' ', '\n', '\t', ',', '.', '!', '?', ';', ':', '-', '(', ')'):
                split_idx = i
                break
                
        if split_idx == -1:
            # Word is still being formed; keep buffering
            return ""
            
        # Extract the complete chunk to process
        to_process = self.buffer[:split_idx + 1]
        self.buffer = self.buffer[split_idx + 1:]
        
        # Redact patterns
        sanitized = to_process
        for pattern, replacement in self.pii_patterns:
            sanitized = pattern.sub(replacement, sanitized)
            
        return sanitized

    def finalize(self) -> str:
        """
        Processes and returns any leftover content inside the buffer at the end of the stream.
        """
        remaining = self.buffer
        self.buffer = ""
        sanitized = remaining
        for pattern, replacement in self.pii_patterns:
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized
