import os
import json
import urllib.request
import urllib.error
import logging

logger = logging.getLogger("PromptGuardTransformer")

HF_MODEL_ID = "deepset/prompt-injections"

def query_transformer_classifier(prompt: str) -> dict:
    """
    Queries HuggingFace Serverless Inference API for prompt injection detection.
    Returns: {"is_safe": bool, "risk_score": float, "category": str} or None if failed.
    """
    token = os.environ.get("HF_API_TOKEN", "")
    url = f"https://api-inference.huggingface.co/models/{HF_MODEL_ID}"
    
    headers = {
        "Content-Type": "application/json"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
        
    payload = {
        "inputs": prompt
    }
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        # Fast 3.0 second timeout to avoid delaying real-time user prompts
        with urllib.request.urlopen(req, timeout=3.0) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            
            # Parse Hugging Face standard text classification response: [[{"label": "...", "score": ...}, ...]]
            if isinstance(res_json, list) and len(res_json) > 0:
                predictions = res_json[0]
                if isinstance(predictions, list):
                    sorted_preds = sorted(predictions, key=lambda x: x.get("score", 0.0), reverse=True)
                    top_pred = sorted_preds[0]
                    label = top_pred.get("label", "").upper()
                    score = float(top_pred.get("score", 0.0))
                    
                    # For deepset/prompt-injections: LABEL_1/INJECTION is malicious, LABEL_0/SAFE is clean
                    is_injection = (label == "INJECTION" or label == "LABEL_1")
                    
                    return {
                        "is_safe": not is_injection,
                        "risk_score": score if is_injection else (1.0 - score),
                        "category": "Override" if is_injection else "Clean"
                    }
            return None
    except Exception as e:
        logger.warning("HuggingFace Transformer inference failed or timed out: %s. Using local fallback.", e)
        return None
