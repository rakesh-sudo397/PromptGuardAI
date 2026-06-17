# PromptGuard AI - Day 1 Research & Observations

## 1. What is prompt injection in your own words?
Prompt injection is an attack technique where malicious instructions are embedded within a user input to hijack a Large Language Model's execution context. This forces the model to ignore its developer-defined system rules, leading to unauthorized actions, system prompt leaks, or the generation of banned/harmful output.

## 2. What patterns appear in malicious prompts in deepset/prompt-injections?
Through exploratory data analysis, we identified three primary signatures:
- **Instruction Overrides**: Explicit commands using keywords like `ignore`, `forget`, `bypass`, `instead of`, and `override`.
- **System Emulation**: Roleplay setups like `You are now a...`, `Act as`, or `Assume the role of`.
- **Instruction Boundary Breakers**: Appending text after separators, e.g., `---` or `[End of Translation]`, followed by new commands.

## 3. What 3 edge cases would be hardest for a static classifier to identify?
- **Base64 or Hex Obfuscation**: Encoding malicious payloads (e.g., `SWdub3JlIHRoZSBhYm92ZQ==`) which bypass regex but decode into attacks at run-time.
- **Hypothetical/Creative Writing Scenarios**: Framing a harmful prompt inside a creative prompt (e.g., "Write a fictional story about a hacker bypass sequence...").
- **Split-Instruction Attacks**: Distributing the payload across multiple turns or using mathematical/token logic to reassemble it inside the model context.

## 4. What is our plan for Day 2?
We will transition from static regex filters to feature engineering. We plan to extract prompt length, special character ratios, and build a TF-IDF text representation pipeline to prepare for machine learning training.