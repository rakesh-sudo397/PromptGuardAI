import re

# Define a dictionary of compile regex patterns for jailbreak detection
JAILBREAK_RULES = {
    "ignore_instruction_override": re.compile(
        r"\b(?:ignore|forget|override|skip|bypass|erase)\b.*\b(?:above|previous|last|system|instructions|prior|safety|guard|filter|policy|protocol)\b|\b(?:system|instructions?|rules?|safety|guard)\b.*\b(?:ignore|forget|override|skip|bypass|erase)\b",
        re.IGNORECASE
    ),
    "roleplay_impersonation": re.compile(
        r"\b(?:you are now|act as|roleplay as|assume the role of|simulate|pretend to be|you are a|du bist jetzt|agiere als)\b",
        re.IGNORECASE
    ),
    "developer_mode_simulation": re.compile(
        r"\b(?:dan|jailbreak\w*|developer mode|dev mode|unfiltered|uag|unrestricted)\b",
        re.IGNORECASE
    ),
    "system_leakage_attempt": re.compile(
        r"\b(?:output|print|show|expose|leak|display)\b.*\b(?:system prompt|initial system|developer prompt|source instructions|prompt configurations)\b",
        re.IGNORECASE
    ),
    "context_separation_break": re.compile(
        r"(?:\[\s*end\s*of\s*.*\]|\bstop\b.*\btranslation\b|---|\#\#\#|===|___).*\b(?:now|instead|do this|print|output|override)\b",
        re.IGNORECASE
    ),
    "stop_scanning_override": re.compile(
        r"\b(?:stop\s+scanning|disable\s+guard|stop\s+following|bypass\s+the?\s+security|override\s+safety)\b",
        re.IGNORECASE
    )
}