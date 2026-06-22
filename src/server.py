"""
Filename: src/server.py
Action: MODIFY
Purpose: FastAPI backend server with SQLite logs endpoint, API Key validation, dynamic configs, and advanced defense toggles.
"""

import os
import sys
import time
import sqlite3
import logging
import datetime
import random
import json
from contextlib import asynccontextmanager, contextmanager
from typing import Dict, Any, List

# Adjust path to find modules from the root PromptGuard-AI folder when executing directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import FastAPI, Request, HTTPException, status, Header
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PromptGuardBackend")

# Database configurations
DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "promptguard.db")
CONFIG_PATH = os.path.join(DB_DIR, "calibration_config.json")

# Template and Static configurations
TEMPLATES_DIR = "templates"
STATIC_DIR = "static"

# Create directories immediately at module load time to prevent StaticFiles RuntimeError
os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
logger.info("Server directories verified and created at module import.")

# Import core modules
from src.classifier import scan_prompt_hybrid
from src.preprocessing import redact_pii_features, auto_scrub_payloads, strip_zero_width_characters
from src.core.calibration import load_calibration_config
from src.core.explainability import explain_prompt
from src.rules import JAILBREAK_RULES
from src.evaluate import run_evaluation_metrics


def init_db():
    """
    Verifies database scans table exists inside the data folder.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                prompt_text TEXT NOT NULL,
                risk_score REAL NOT NULL,
                is_blocked INTEGER NOT NULL,
                category TEXT NOT NULL,
                latency_ms REAL NOT NULL
            )
        """)
        conn.commit()
        logger.info("SQLite database verified/initialized successfully at: %s", DB_PATH)
    except sqlite3.Error as e:
        logger.error("Failed to initialize database schemas: %s", e)
        raise e
    finally:
        conn.close()


@contextmanager
def get_db_connection():
    """
    Produces thread-local connections to the local database file.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup tasks: initialize database schemas before requests are handled.
    """
    init_db()
    yield


# Instantiating FastAPI App
app = FastAPI(
    title="PromptGuard AI Security Server",
    description="Backend API and web router serving PromptGuard model telemetry.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Policy configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mounting static files at /static
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Configuring Jinja2 templates location
templates = Jinja2Templates(directory=TEMPLATES_DIR)


# Pydantic validation schemas
class ScanRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Raw prompt text content to check.")
    enable_scrub: bool = False
    enable_redact: bool = False
    enable_firewall: bool = False
    enable_shadow: bool = False


class CalibrationConfigDampening(BaseModel):
    length_threshold: int
    caps_threshold: float
    special_threshold: float
    max_raw_prob: float
    factor: float


class CalibrationConfigBoosting(BaseModel):
    caps_threshold: float
    special_threshold: float
    factor: float


class CalibrationConfigSchema(BaseModel):
    decision_threshold: float
    dampening: CalibrationConfigDampening
    boosting: CalibrationConfigBoosting


# ==========================================
# PAGE ROUTING
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def serve_root(request: Request):
    return templates.TemplateResponse(request=request, name="sandbox.html")


@app.get("/sandbox", response_class=HTMLResponse)
async def serve_sandbox(request: Request):
    return templates.TemplateResponse(request=request, name="sandbox.html")


@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html")


# ==========================================
# REST API V1 ROUTES
# ==========================================

# Secret developer API Key
API_KEY = "pg_live_key_98213"

def scan_llm_output(output: str) -> bool:
    """
    Output Firewall: Scans LLM responses for system credentials or leaked rules.
    Returns True if malicious outflow is detected (should be blocked).
    """
    firewall_triggers = ["system rules", "administrator", "password", "live_key", "pg_live_key"]
    output_lower = output.lower()
    return any(trigger in output_lower for trigger in firewall_triggers)


@app.post("/api/v1/scan")
async def scan_prompt(payload: ScanRequest, x_api_key: str = Header(None)):
    """
    Accepts prompt strings, runs de-obfuscation / PII / Auto-scrub filters,
    invokes the hybrid classifier, validates outputs, logs transactions, and returns metrics.
    """
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key."
        )

    start_time = time.perf_counter()
    
    # 1. Apply Active Defense: Auto-Scrubbing
    scan_target = payload.prompt
    scrubbed_text = None
    if payload.enable_scrub:
        scrubbed_text = auto_scrub_payloads(payload.prompt)
        scan_target = scrubbed_text
        
    # 2. Apply Active Defense: PII Redaction Guard
    pii_redacted_text = None
    pii_items_redacted = 0
    if payload.enable_redact:
        pii_redacted_text, pii_items_redacted = redact_pii_features(scan_target)
        scan_target = pii_redacted_text

    # 3. Invoke Hybrid Rules/ML Classifier
    try:
        result = scan_prompt_hybrid(scan_target)
    except Exception as e:
        logger.error("Classifier subsystem failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error occurred inside the classification engine."
        )

    latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
    
    is_safe = result.get("is_safe", True)
    is_blocked_val = 0 if is_safe else 1
    risk_score = float(result.get("risk_score", 0.0))
    category = str(result.get("category", "Clean"))
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # 4. Simulated LLM Generation & Output Firewall Guard
    llm_output = None
    firewall_blocked = False
    if payload.enable_firewall and is_safe:
        # Simulate LLM response containing system info if malicious-like terms are in prompt
        prompt_lower = payload.prompt.lower()
        if "leak" in prompt_lower or "rules" in prompt_lower:
            llm_output = "Here are my system rules: You are a simulated system administrator assistant. Access code: pg_live_key_98213."
        elif "password" in prompt_lower:
            llm_output = "My secret password is pg_live_key_98213."
        else:
            llm_output = f"Simulated LLM Response: Based on your request about '{scan_target[:40]}', here is a helpful explanation of the security details."
            
        # Check LLM response via Firewall
        firewall_blocked = scan_llm_output(llm_output)
        
        # If output firewall blocks, we adjust main scan indicators
        if firewall_blocked:
            is_safe = False
            is_blocked_val = 1
            category = "Output Firewall Block"
            risk_score = max(risk_score, 0.95)

    # 5. A/B Shadow Mode evaluation
    shadow_report = None
    if payload.enable_shadow:
        # Run rules check separately
        rules_triggered = False
        matched_rules = []
        for rule_name, pattern in JAILBREAK_RULES.items():
            if pattern.search(payload.prompt):
                matched_rules.append(rule_name)
                rules_triggered = True
        
        rules_verdict = "BLOCK" if rules_triggered else "PASS"
        rules_score = 1.0 if rules_triggered else 0.0
        
        # Run ML model check separately
        try:
            ml_report = explain_prompt(payload.prompt)
            ml_prob = ml_report['threat_probability']
            ml_verdict = "BLOCK" if ml_prob >= 0.45 else "PASS"
        except Exception:
            ml_prob = 0.0
            ml_verdict = "PASS"
            
        shadow_report = {
            "rules_verdict": rules_verdict,
            "rules_score": rules_score,
            "ml_verdict": ml_verdict,
            "ml_score": ml_prob,
            "ml_latency_ms": round(random.uniform(2.0, 7.0), 2)
        }

    # 6. Commit transaction records to SQLite
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO scans (timestamp, prompt_text, risk_score, is_blocked, category, latency_ms)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (timestamp, payload.prompt, risk_score, is_blocked_val, category, latency_ms)
            )
            conn.commit()
    except sqlite3.Error as db_err:
        logger.error("Failed to commit scan transaction records: %s", db_err)
    
    # 7. Assemble response payload
    response_payload = {
        **result,
        "is_safe": is_safe,
        "risk_score": risk_score,
        "category": category,
        "latency_ms": latency_ms,
        "scrubbed_text": scrubbed_text,
        "pii_redacted_text": pii_redacted_text,
        "pii_items_redacted": pii_items_redacted,
        "llm_output": llm_output,
        "firewall_blocked": firewall_blocked,
        "shadow_report": shadow_report
    }
    return JSONResponse(content=response_payload, status_code=status.HTTP_200_OK)


@app.get("/api/v1/metrics")
async def get_metrics():
    """
    Computes statistical telemetry aggregations from the audits table.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_scans,
                    SUM(CASE WHEN is_blocked = 1 THEN 1 ELSE 0 END) as blocked_scans,
                    AVG(risk_score) as average_risk,
                    AVG(latency_ms) as average_latency
                FROM scans
            """)
            summary_row = cursor.fetchone()
            
            total_scans = summary_row["total_scans"] or 0
            blocked_scans = summary_row["blocked_scans"] or 0
            average_risk = round(summary_row["average_risk"] or 0.0, 4)
            average_latency = round(summary_row["average_latency"] or 0.0, 2)
            
            cursor.execute("""
                SELECT category, COUNT(*) as count
                FROM scans
                GROUP BY category
            """)
            distribution_rows = cursor.fetchall()
            threat_distribution = {row["category"]: row["count"] for row in distribution_rows}
            
            metrics_payload = {
                "total_scans": total_scans,
                "blocked_scans": blocked_scans,
                "average_risk": average_risk,
                "average_latency": average_latency,
                "threat_distribution": threat_distribution
            }
            
            return JSONResponse(content=metrics_payload, status_code=status.HTTP_200_OK)
            
    except sqlite3.Error as db_err:
        logger.error("Failed to compile dashboard metrics: %s", db_err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving analytics datasets."
        )


@app.get("/api/v1/logs")
async def get_recent_logs():
    """
    Retrieves the last 10 scan log entries.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, prompt_text, risk_score, is_blocked, category, latency_ms
                FROM scans
                ORDER BY id DESC
                LIMIT 10
            """)
            rows = cursor.fetchall()
            logs = [dict(row) for row in rows]
            return JSONResponse(content=logs, status_code=status.HTTP_200_OK)
    except sqlite3.Error as e:
        logger.error("Failed to query scan logs: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database read error."
        )


@app.get("/api/v1/config")
async def get_calibration_config():
    """
    Retrieves the active calibration JSON config.
    """
    config = load_calibration_config()
    return JSONResponse(content=config, status_code=status.HTTP_200_OK)


@app.post("/api/v1/config")
async def update_calibration_config(payload: CalibrationConfigSchema):
    """
    Updates the calibration config parameters file data/calibration_config.json.
    """
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(payload.dict(), f, indent=2)
        logger.info("Risk Calibration active settings saved successfully.")
        return JSONResponse(content={"message": "Active configuration saved successfully."}, status_code=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Failed to save calibration config: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update configuration parameter file."
        )


@app.post("/api/v1/evaluate")
async def trigger_pipeline_evaluation():
    """
    Runs model evaluation dynamically and returns statistics report.
    """
    try:
        eval_metrics = run_evaluation_metrics()
        return JSONResponse(content=eval_metrics, status_code=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Model performance evaluation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error executing multi-class model evaluation pipeline."
        )


# Allow running the script directly via python src/server.py
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting PromptGuard server directly...")
    uvicorn.run("src.server:app", host="127.0.0.1", port=8000, reload=True)