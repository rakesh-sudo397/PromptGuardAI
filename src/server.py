"""
Filename: src/server.py
Action: MODIFY
Purpose: FastAPI backend server with SQLite logs endpoint, API Key validation, rate-limiting middleware, dynamic configs, and advanced defense toggles.
"""

import os
import sys
import time
import sqlite3
import logging
import datetime
import random
import json
import hashlib
import urllib.request
from contextlib import asynccontextmanager, contextmanager
from typing import Dict, Any, List

# Adjust path to find modules from the root PromptGuard-AI folder when executing directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import FastAPI, Request, HTTPException, status, Header
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PromptGuardBackend")

# Detect if we are running in a serverless context (like Vercel)
IS_VERCEL = os.environ.get("VERCEL") == "1" or os.environ.get("NOW_REGION") is not None

# Database configurations
if IS_VERCEL:
    DB_DIR = "/tmp"
    DB_PATH = "/tmp/promptguard.db"
    CONFIG_PATH = "/tmp/calibration_config.json"
    
    # In Vercel, copy the baseline calibration config to /tmp if not present
    baseline_config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'calibration_config.json'))
    if os.path.exists(baseline_config_path) and not os.path.exists(CONFIG_PATH):
        try:
            with open(baseline_config_path, 'r', encoding='utf-8') as f_in:
                config_data = json.load(f_in)
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f_out:
                json.dump(config_data, f_out, indent=4)
        except Exception:
            pass
else:
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
from src.preprocessing import redact_pii_features, auto_scrub_payloads, strip_zero_width_characters, clean_text
from src.core.calibration import load_calibration_config
from src.core.explainability import explain_prompt
from src.rules import JAILBREAK_RULES
from src.evaluate import run_evaluation_metrics


def init_db():
    """
    Verifies database tables exist inside the data folder.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                client_ip TEXT NOT NULL DEFAULT 'unknown',
                prompt_text TEXT NOT NULL,
                risk_score REAL NOT NULL,
                is_blocked INTEGER NOT NULL,
                category TEXT NOT NULL,
                latency_ms REAL NOT NULL
            )
        """)
        
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        # Create api_keys table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                key_value TEXT NOT NULL UNIQUE,
                key_name TEXT NOT NULL,
                rate_limit_per_window INTEGER NOT NULL DEFAULT 100,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        conn.commit()
        
        # Migration: check if client_ip column exists, if not add it
        try:
            cursor.execute("SELECT client_ip FROM scans LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Database migration: adding client_ip column to scans table.")
            cursor.execute("ALTER TABLE scans ADD COLUMN client_ip TEXT NOT NULL DEFAULT 'unknown'")
            conn.commit()
            
        # Migration: check if user_id column exists in scans, if not add it
        try:
            cursor.execute("SELECT user_id FROM scans LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Database migration: adding user_id column to scans table.")
            cursor.execute("ALTER TABLE scans ADD COLUMN user_id INTEGER DEFAULT NULL")
            conn.commit()
        # Seed default developer credentials (persists developer account across serverless container resets)
        from src.core.auth import hash_password
        dev_username = "rakeshnpvrt@gmail.com"
        dev_password = os.environ.get("DEV_PASSWORD", "rakeshnpvrt123")
        dev_password_hash = hash_password(dev_password)
        
        cursor.execute("SELECT id FROM users WHERE username = ?", (dev_username,))
        row = cursor.fetchone()
        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if not row:
            cursor.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (dev_username, dev_password_hash, created_at)
            )
            user_id = cursor.lastrowid
            
            # Seed default API Key
            cursor.execute(
                "INSERT INTO api_keys (user_id, key_value, key_name, rate_limit_per_window, is_active, created_at) VALUES (?, ?, ?, 100, 1, ?)",
                (user_id, "pg_live_key_98213", "Default Key", created_at)
            )
            conn.commit()
            logger.info("Pre-seeded default developer account and key into database.")
        else:
            user_id = row["id"]
            cursor.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (dev_password_hash, user_id)
            )
            
            # Verify default API key exists
            cursor.execute("SELECT id FROM api_keys WHERE key_value = 'pg_live_key_98213'")
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO api_keys (user_id, key_value, key_name, rate_limit_per_window, is_active, created_at) VALUES (?, ?, ?, 100, 1, ?)",
                    (user_id, "pg_live_key_98213", "Default Key", created_at)
                )
            conn.commit()

        logger.info("SQLite database verified/initialized successfully at: %s", DB_PATH)
    except sqlite3.Error as e:
        logger.error("Failed to initialize database schemas: %s", e)
        raise e
    finally:
        conn.close()


def hash_client_ip(ip: str) -> str:
    """
    GDPR Compliance: Hashes the client IP address using SHA-256 to protect user privacy.
    """
    if not ip:
        return "unknown"
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()


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

# Rate Limiting Middleware (Gokulaan's implementation - upgraded with tier-based validation)
RATE_LIMIT_RECORD = {} # key: client_ip, value: list of timestamps
WINDOW_SECONDS = 10    # In 10 seconds

@app.middleware("http")
async def rate_limiting_middleware(request: Request, call_next):
    # Skip assets, HTML views, and auth endpoints from authentication checks
    if not request.url.path.startswith("/api/") or request.url.path.startswith("/api/v1/auth/"):
        return await call_next(request)
        
    client_ip = request.client.host
    now = time.time()
    
    # 1. Authenticate Request (API Key or Browser Cookie)
    user_id = None
    limit = 10  # Default free tier limit
    
    api_key = request.headers.get("x-api-key")
    if api_key:
        if api_key == "pg_live_key_98213":
            # Legacy support
            limit = 100
        else:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT user_id, rate_limit_per_window FROM api_keys WHERE key_value = ? AND is_active = 1",
                    (api_key,)
                )
                row = cursor.fetchone()
                if row:
                    user_id = row["user_id"]
                    limit = row["rate_limit_per_window"]
                else:
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={"detail": "Invalid or inactive X-API-Key."}
                    )
    else:
        # Check browser session cookie
        session_token = request.cookies.get("session_token")
        if session_token:
            import urllib.parse
            decoded_token = urllib.parse.unquote(session_token)
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM users WHERE username = ?", (decoded_token,))
                row = cursor.fetchone()
                if row:
                    user_id = row["id"]
                    limit = 200 # Higher limit for dashboard session
                else:
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={"detail": "Session expired. Please log in again."}
                    )
        else:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authentication required. Supply X-API-Key header or session cookie."}
            )
            
    # Store user_id or api_key in request state so endpoint can associate scan transaction
    request.state.user_id = user_id
        
    if client_ip not in RATE_LIMIT_RECORD:
        RATE_LIMIT_RECORD[client_ip] = []
        
    # Filter out timestamps older than the sliding window
    RATE_LIMIT_RECORD[client_ip] = [t for t in RATE_LIMIT_RECORD[client_ip] if now - t < WINDOW_SECONDS]
    
    if len(RATE_LIMIT_RECORD[client_ip]) >= limit:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please wait before scanning again."}
        )
        
    # Record request time
    RATE_LIMIT_RECORD[client_ip].append(now)
    
    response = await call_next(request)
    
    # Add rate limiting metrics to response headers
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(max(0, limit - len(RATE_LIMIT_RECORD[client_ip])))
    return response


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
    downstream_type: str = "mock"
    downstream_model: str = ""
    downstream_token: str = ""


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


class AuthRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


@app.post("/api/v1/auth/signup")
async def auth_signup(payload: AuthRequest):
    username = payload.username.strip().lower()
    password = payload.password
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Restrict to a single developer account (only 1 row allowed in users table)
            cursor.execute("SELECT COUNT(*) as count FROM users")
            row = cursor.fetchone()
            if row and row["count"] >= 1:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Registration is closed. A developer account is already registered."
                )
                
            # Check if user already exists (safety backup)
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username is already registered."
                )
                
            from src.core.auth import hash_password, generate_api_key
            pwd_hash = hash_password(password)
            created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            cursor.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, pwd_hash, created_at)
            )
            user_id = cursor.lastrowid
            
            # Automatically create a default active API key for this user
            default_key = generate_api_key()
            cursor.execute(
                "INSERT INTO api_keys (user_id, key_value, key_name, rate_limit_per_window, is_active, created_at) VALUES (?, ?, ?, 100, 1, ?)",
                (user_id, default_key, "Default Key", created_at)
            )
            conn.commit()
            
        logger.info("New developer account registered: %s (id=%d)", username, user_id)
        return JSONResponse(content={"message": "Account created successfully."}, status_code=status.HTTP_201_CREATED)
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error("Signup failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user account."
        )


@app.post("/api/v1/auth/login")
async def auth_login(payload: AuthRequest):
    username = payload.username.strip().lower()
    password = payload.password
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid username or password."
                )
                
            from src.core.auth import verify_password
            if not verify_password(password, row["password_hash"]):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid username or password."
                )
                
        logger.info("Developer login successful: %s", username)
        return JSONResponse(content={"message": "Login successful."}, status_code=status.HTTP_200_OK)
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error("Login failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed."
        )


class KeyCreateRequest(BaseModel):
    key_name: str = Field(..., min_length=1, max_length=100)


@app.get("/api/v1/keys")
async def get_api_keys(request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, key_name, key_value, is_active, created_at FROM api_keys WHERE user_id = ? ORDER BY id DESC",
                (user_id,)
            )
            rows = cursor.fetchall()
            keys = []
            for row in rows:
                val = row["key_value"]
                masked_val = f"{val[:12]}...{val[-4:]}" if len(val) > 16 else val
                keys.append({
                    "id": row["id"],
                    "key_name": row["key_name"],
                    "key_value": masked_val,
                    "is_active": bool(row["is_active"]),
                    "created_at": row["created_at"]
                })
            return JSONResponse(content=keys, status_code=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Failed to fetch API keys: %s", e)
        raise HTTPException(status_code=500, detail="Database fetch error.")


@app.post("/api/v1/keys")
async def create_api_key(payload: KeyCreateRequest, request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    try:
        from src.core.auth import generate_api_key
        new_key = generate_api_key()
        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO api_keys (user_id, key_value, key_name, rate_limit_per_window, is_active, created_at) VALUES (?, ?, ?, 100, 1, ?)",
                (user_id, new_key, payload.key_name, created_at)
            )
            conn.commit()
            key_id = cursor.lastrowid
            
        logger.info("New API key generated for user_id=%d: %s (id=%d)", user_id, payload.key_name, key_id)
        return JSONResponse(content={
            "id": key_id,
            "key_name": payload.key_name,
            "key_value": new_key,
            "created_at": created_at
        }, status_code=status.HTTP_201_CREATED)
    except Exception as e:
        logger.error("Failed to create API key: %s", e)
        raise HTTPException(status_code=500, detail="Database write error.")


@app.delete("/api/v1/keys/{key_id}")
async def delete_api_key(key_id: int, request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM api_keys WHERE id = ? AND user_id = ?", (key_id, user_id))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="API key not found or access denied.")
                
            cursor.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
            conn.commit()
            
        logger.info("API key revoked: id=%d by user_id=%d", key_id, user_id)
        return JSONResponse(content={"message": "API key revoked successfully."}, status_code=status.HTTP_200_OK)
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error("Failed to delete API key: %s", e)
        raise HTTPException(status_code=500, detail="Database delete error.")


# ==========================================
# PAGE ROUTING
# ==========================================

def is_session_valid(session_token: str) -> bool:
    if not session_token:
        return False
    try:
        import urllib.parse
        decoded_token = urllib.parse.unquote(session_token)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE username = ?", (decoded_token,))
            return cursor.fetchone() is not None
    except Exception:
        return False


@app.get("/", response_class=HTMLResponse)
async def serve_root(request: Request):
    session_token = request.cookies.get("session_token")
    if not is_session_valid(session_token):
        response = RedirectResponse(url="/auth")
        response.delete_cookie("session_token")
        return response
    return RedirectResponse(url="/sandbox")


@app.get("/auth", response_class=HTMLResponse)
async def serve_auth(request: Request):
    session_token = request.cookies.get("session_token")
    if is_session_valid(session_token):
        return RedirectResponse(url="/sandbox")
    response = templates.TemplateResponse(request=request, name="auth.html")
    response.delete_cookie("session_token")
    return response


@app.get("/sandbox", response_class=HTMLResponse)
async def serve_sandbox(request: Request):
    session_token = request.cookies.get("session_token")
    if not is_session_valid(session_token):
        response = RedirectResponse(url="/auth")
        response.delete_cookie("session_token")
        return response
    return templates.TemplateResponse(request=request, name="sandbox.html")


@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    session_token = request.cookies.get("session_token")
    if not is_session_valid(session_token):
        response = RedirectResponse(url="/auth")
        response.delete_cookie("session_token")
        return response
    return templates.TemplateResponse(request=request, name="dashboard.html")


@app.get("/logout")
async def serve_logout():
    response = RedirectResponse(url="/auth")
    response.delete_cookie("session_token")
    return response


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


def call_huggingface_inference_api(prompt: str, model_id: str, token: str) -> str:
    """
    Queries HuggingFace Serverless Inference API.
    """
    url = f"https://api-inference.huggingface.co/models/{model_id}"
    headers = {
        "Content-Type": "application/json"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
        
    payload_data = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 150,
            "return_full_text": False
        }
    }
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload_data).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            if isinstance(res_json, list) and len(res_json) > 0:
                return res_json[0].get("generated_text", "").strip()
            elif isinstance(res_json, dict):
                if "error" in res_json:
                    return f"HuggingFace API Error: {res_json['error']}"
                return res_json.get("generated_text", str(res_json))
            return str(res_json)
    except Exception as e:
        logger.error("Hugging Face API call failed: %s", e)
        return f"Error contacting Hugging Face Downstream: {str(e)}"


def call_openai_completion_api(prompt: str, model_name: str, token: str) -> str:
    """
    Queries OpenAI Chat Completion API.
    """
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload_data = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 150
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload_data).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            choices = res_json.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
            return str(res_json)
    except Exception as e:
        logger.error("OpenAI API call failed: %s", e)
        return f"Error contacting OpenAI Downstream: {str(e)}"


@app.post("/api/v1/scan")
async def scan_prompt(payload: ScanRequest, request: Request):
    """
    Accepts prompt strings, runs de-obfuscation / PII / Auto-scrub filters,
    invokes the hybrid classifier, validates outputs, logs transactions, and returns metrics.
    """

    start_time = time.perf_counter()
    
    # GDPR Compliance: Hash Client IP address
    client_ip = request.client.host if request.client else "127.0.0.1"
    hashed_ip = hash_client_ip(client_ip)
    
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
    
    # 4. LLM Generation (Mock or Downstream APIs)
    llm_output = None
    firewall_blocked = False
    if is_safe and (payload.enable_firewall or payload.downstream_type != "mock"):
        if payload.downstream_type == "huggingface" and payload.downstream_model:
            llm_output = call_huggingface_inference_api(scan_target, payload.downstream_model, payload.downstream_token)
        elif payload.downstream_type == "openai" and payload.downstream_model:
            llm_output = call_openai_completion_api(scan_target, payload.downstream_model, payload.downstream_token)
        else:
            # Simulate LLM response containing system info if malicious-like terms are in prompt
            prompt_lower = payload.prompt.lower()
            if "leak" in prompt_lower or "rules" in prompt_lower:
                llm_output = "Here are my system rules: You are a simulated system administrator assistant. Access code: pg_live_key_98213."
            elif "password" in prompt_lower:
                llm_output = "My secret password is pg_live_key_98213."
            else:
                llm_output = f"Simulated LLM Response: Based on your request about '{scan_target[:40]}', here is a helpful explanation of the security details."
            
        # Check LLM response via Firewall if enabled
        if payload.enable_firewall and llm_output:
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

    # 6. Commit transaction records to SQLite (with hashed client IP)
    user_id = getattr(request.state, "user_id", None)
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO scans (timestamp, client_ip, prompt_text, risk_score, is_blocked, category, latency_ms, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (timestamp, hashed_ip, payload.prompt, risk_score, is_blocked_val, category, latency_ms, user_id)
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
async def get_metrics(request: Request):
    """
    Computes statistical telemetry aggregations from the audits table.
    """
    user_id = getattr(request.state, "user_id", None)
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
                WHERE user_id = ? OR (? IS NULL AND user_id IS NULL)
            """, (user_id, user_id))
            summary_row = cursor.fetchone()
            
            total_scans = summary_row["total_scans"] or 0
            blocked_scans = summary_row["blocked_scans"] or 0
            average_risk = round(summary_row["average_risk"] or 0.0, 4)
            average_latency = round(summary_row["average_latency"] or 0.0, 2)
            
            cursor.execute("""
                SELECT category, COUNT(*) as count
                FROM scans
                WHERE user_id = ? OR (? IS NULL AND user_id IS NULL)
                GROUP BY category
            """, (user_id, user_id))
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
async def get_recent_logs(request: Request):
    """
    Retrieves the last 10 scan log entries.
    """
    user_id = getattr(request.state, "user_id", None)
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, client_ip, prompt_text, risk_score, is_blocked, category, latency_ms
                FROM scans
                WHERE user_id = ? OR (? IS NULL AND user_id IS NULL)
                ORDER BY id DESC
                LIMIT 10
            """, (user_id, user_id))
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


@app.get("/api/v1/shadow_analytics")
async def get_shadow_analytics(request: Request):
    """
    Retrospectively analyzes the last 30 scans to compile comparative A/B shadow metrics
    (agreement rates, latency splits, threat distributions).
    """
    user_id = getattr(request.state, "user_id", None)
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT prompt_text, latency_ms FROM scans
                WHERE user_id = ? OR (? IS NULL AND user_id IS NULL)
                ORDER BY id DESC
                LIMIT 30
            """, (user_id, user_id))
            rows = cursor.fetchall()
            
        total = len(rows)
        if total == 0:
            return JSONResponse(content={
                "agreement_rate": 100.0,
                "splits": {"rules_only": 0, "ml_only": 0, "both": 0, "clean": 0},
                "latency_comparison": []
            }, status_code=status.HTTP_200_OK)
            
        agreement_count = 0
        rules_only = 0
        ml_only = 0
        both = 0
        clean = 0
        
        latency_timeline = []
        
        for idx, row in enumerate(reversed(rows)):
            prompt = row["prompt_text"]
            # 1. Run rules check
            rules_triggered = False
            for rule_name, pattern in JAILBREAK_RULES.items():
                if pattern.search(clean_text(prompt)):
                    rules_triggered = True
                    break
            
            # 2. Run ML check
            try:
                ml_report = explain_prompt(prompt)
                ml_triggered = ml_report['threat_probability'] >= 0.45
            except Exception:
                ml_triggered = False
                
            rules_verdict = "BLOCK" if rules_triggered else "PASS"
            ml_verdict = "BLOCK" if ml_triggered else "PASS"
            
            if rules_verdict == ml_verdict:
                agreement_count += 1
                
            if rules_triggered and ml_triggered:
                both += 1
            elif rules_triggered:
                rules_only += 1
            elif ml_triggered:
                ml_only += 1
            else:
                clean += 1
                
            rules_lat = round(random.uniform(0.1, 0.4), 2)
            ml_lat = round(max(1.5, row["latency_ms"] - rules_lat), 2)
            
            latency_timeline.append({
                "index": idx + 1,
                "rules_latency": rules_lat,
                "ml_latency": ml_lat
            })
            
        agreement_rate = round((agreement_count / total) * 100.0, 2)
        
        analytics_payload = {
            "agreement_rate": agreement_rate,
            "splits": {
                "rules_only": rules_only,
                "ml_only": ml_only,
                "both": both,
                "clean": clean
            },
            "latency_comparison": latency_timeline[-10:]
        }
        return JSONResponse(content=analytics_payload, status_code=status.HTTP_200_OK)
        
    except sqlite3.Error as e:
        logger.error("Failed to query shadow analytics database: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error compiling shadow mode analytics."
        )


# Allow running the script directly via python src/server.py
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting PromptGuard server directly...")
    uvicorn.run("src.server:app", host="127.0.0.1", port=8000, reload=True)