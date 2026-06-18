# PromptGuard AI - Day 3 Security Audit Log

## 1. Baseline Model Performance
- **Validation Dataset Size**: 110 prompts (test split)
- **Accuracy**: 92.73%
- **Precision**: 88.37% (5 False Positives triggered)
- **Recall**: 92.68% (3 False Negatives/Missed attacks)
- **F1 Score**: 90.47%

---

## 2. Failure Mode Analysis (Vulnerabilities)

### A. False Negatives (Critical Misses)
Our model failed to identify the following injections in testing/validation:
1. **Base64 Payload Bypasses**: Prompts like `"SWdub3JlIHRoZSBhYm92Z..."` were classified as **SAFE**. 
   * *Reason*: The TF-IDF representation doesn't know the meaning of randomized alphabet strings; it sees it as a single, low-frequency, non-threatening word.
2. **Leet-Speak Obfuscation**: `"1gn0r3 pr3v10us rul3s..."` was passed with low probability.
   * *Reason*: Characters like `1`, `0`, and `3` alter the spelling from `ignore` and `rules`, preventing the model's vocabulary columns from activating.
3. **Multilingual Bypass**: Steathy prompts written in languages like German or French had low confidence levels compared to their English equivalents.

### B. False Positives (False Blocks)
Our model triggered blocks on these safe queries:
1. Prompts that use words like `"system"`, `"rules"`, or `"instructions"` in normal settings (e.g., `"Generate a list of rules for a chess game"`).
   * *Reason*: The TF-IDF weights for vocabulary columns containing `rules` and `system` are very high due to their abundance in attack prompts, confusing the classifier.

---

## 3. Remediation Plan (Day 4 & 5)
To address the vulnerabilities identified in this audit, we will implement:
- **Base64 Decoder Preprocessor**: An automatic decoder function in `src/preprocessing.py` that intercepts base64 string regex patterns, decodes them back to plain English, and scans the decoded payload.
- **Visual Unicode Cleaner**: Strips character-obfuscation patterns (leetspeak) before feature extraction.
- **Risk Score Adjustment**: Combine model probability with metadata weights (such as character length) to reduce false positives on short, simple prompts.