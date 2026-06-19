"""
Filename: src/server.py
Action: MODIFY
Purpose: Updated TemplateResponse invocations to follow the modern Starlette 0.28.0+ 
         parameter signature (passing 'request' as the first positional/keyword argument).
"""

import os
import sys
import time
import sqlite3
import logging
import datetime
from contextlib import asynccontextmanager, contextmanager
from typing import Dict, Any

# Adjust path to find modules from the root PromptGuard-AI folder when executing directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import FastAPI, Request, HTTPException, status
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

# Template and Static configurations
TEMPLATES_DIR = "templates"
STATIC_DIR = "static"

# Create directories immediately at module load time to prevent StaticFiles RuntimeError
os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
logger.info("Server directories verified and created at module import.")

# Direct Import of scan_prompt_hybrid from your classifier.py
from src.classifier import scan_prompt_hybrid


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


# Pydantic validation schema
class ScanRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Raw prompt text content to check.")


# ==========================================
# PAGE ROUTING (UPDATED SIGNATURES)
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def serve_root(request: Request):
    # Passes request object as first argument
    return templates.TemplateResponse(request=request, name="sandbox.html")


@app.get("/sandbox", response_class=HTMLResponse)
async def serve_sandbox(request: Request):
    # Passes request object as first argument
    return templates.TemplateResponse(request=request, name="sandbox.html")


@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    # Passes request object as first argument
    return templates.TemplateResponse(request=request, name="dashboard.html")


# ==========================================
# REST API V1 ROUTES
# ==========================================

@app.post("/api/v1/scan")
async def scan_prompt(payload: ScanRequest):
    """
    Accepts prompt strings, invokes the hybrid rules/ML classifier, 
    records latency, logs audit logs, and returns telemetry response.
    """
    start_time = time.perf_counter()
    
    try:
        # Call classifier module logic from src/classifier.py
        result = scan_prompt_hybrid(payload.prompt)
    except Exception as e:
        logger.error("Classifier subsystem failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error occurred inside the classification engine."
        )

    # Compute duration metric
    latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
    
    # Map variables from classifier output schema
    is_safe = result.get("is_safe", True)
    is_blocked_val = 0 if is_safe else 1
    risk_score = float(result.get("risk_score", 0.0))
    category = str(result.get("category", "Clean"))
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # Write audit log row to SQLite db
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
    
    # Merge classification outcomes with measured latency
    response_payload = {**result, "latency_ms": latency_ms}
    return JSONResponse(content=response_payload, status_code=status.HTTP_200_OK)


@app.get("/api/v1/metrics")
async def get_metrics():
    """
    Computes statistical telemetry aggregations from the audits table.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Read aggregations (handles empty rows gracefully)
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
            
            # Group distributions by threat class category
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


# Allow running the script directly via python src/server.py
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting PromptGuard server directly...")
    uvicorn.run("src.server:app", host="127.0.0.1", port=8000, reload=True)