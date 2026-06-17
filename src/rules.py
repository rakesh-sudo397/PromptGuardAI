import re

# Define a dictionary of compile regex patterns for jailbreak detection
JAILBREAK_RULES = {
    "ignore_instruction_override": re.compile(
        r"\b(?:ignore|forget|override|skip|bypass|erase)\b.*\b(?:above|previous|last|system|instructions|prior)\b",
        re.IGNORECASE
    ),
    "roleplay_impersonation": re.compile(
        r"\b(?:you are now|act as|roleplay as|assume the role of|simulate|pretend to be)\b",
        re.IGNORECASE
    ),
    "developer_mode_simulation": re.compile(
        r"\b(?:dan|jailbreak|developer mode|dev mode|unfiltered|uag|unrestricted)\b",
        re.IGNORECASE
    ),
    "system_leakage_attempt": re.compile(
        r"\b(?:output|print|show|expose|leak|display)\b.*\b(?:system prompt|initial system|developer prompt|source instructions)\b",
        re.IGNORECASE
    ),
    "context_separation_break": re.compile(
        r"(?:\[\s*end\s*of\s*.*\]|\bstop\b.*\btranslation\b|---|\#\#\#).*\b(?:now|instead|do this)\b",
        re.IGNORECASE
    )
}