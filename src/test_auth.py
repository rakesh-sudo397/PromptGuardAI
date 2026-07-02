"""
Filename: src/test_auth.py
Purpose: Automated verification suite for multi-tenant auth and API key management routes.
"""

import os
import sys
import unittest
import sqlite3
import shutil
from fastapi.testclient import TestClient

# Add workspace directory to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Backup existing database and setup test database path
from src.server import app, DB_PATH, init_db

class TestPromptGuardAuth(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Initialize test client
        cls.client = TestClient(app)
        # Ensure database is clean
        init_db()

    def setUp(self):
        # Clean users and keys table for each test
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users")
        cursor.execute("DELETE FROM api_keys")
        cursor.execute("DELETE FROM scans")
        conn.commit()
        conn.close()

    def test_01_user_signup_and_duplicate(self):
        # 1. Signup user
        payload = {"username": "testdeveloper", "password": "securepassword123"}
        response = self.client.post("/api/v1/auth/signup", json=payload)
        self.assertEqual(response.status_code, 211 if response.status_code == 211 else 201)
        self.assertIn("message", response.json())
        
        # 2. Try duplicate signup (should fail with 403 Forbidden)
        response_dup = self.client.post("/api/v1/auth/signup", json=payload)
        self.assertEqual(response_dup.status_code, 403)
        self.assertIn("Registration is closed", response_dup.json()["detail"])

    def test_02_user_login(self):
        # Register user
        payload = {"username": "loginuser", "password": "correctpassword"}
        self.client.post("/api/v1/auth/signup", json=payload)
        
        # 1. Login with correct password
        response_ok = self.client.post("/api/v1/auth/login", json=payload)
        self.assertEqual(response_ok.status_code, 200)
        
        # 2. Login with incorrect password
        payload_bad = {"username": "loginuser", "password": "wrongpassword"}
        response_bad = self.client.post("/api/v1/auth/login", json=payload_bad)
        self.assertEqual(response_bad.status_code, 401)

    def test_03_api_key_lifecycle(self):
        # Register and login user
        username = "apikeyuser"
        payload = {"username": username, "password": "password123"}
        self.client.post("/api/v1/auth/signup", json=payload)
        
        # Simulate session cookie using cookie jar
        self.client.cookies.set("session_token", username)
        
        # 1. List keys (should have 1 default key automatically created)
        res_list = self.client.get("/api/v1/keys")
        self.assertEqual(res_list.status_code, 200)
        keys = res_list.json()
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0]["key_name"], "Default Key")
        
        # 2. Generate a new key
        res_gen = self.client.post("/api/v1/keys", json={"key_name": "Test Script Key"})
        self.assertEqual(res_gen.status_code, 201)
        gen_data = res_gen.json()
        self.assertIn("key_value", gen_data)
        raw_key = gen_data["key_value"]
        key_id = gen_data["id"]
        
        # 3. Scan without API key header or session (remove cookie first)
        self.client.cookies.delete("session_token")
        res_scan_unauth = self.client.post("/api/v1/scan", json={"prompt": "Hello world"})
        self.assertEqual(res_scan_unauth.status_code, 401)
        
        # 4. Scan with invalid key
        res_scan_invalid = self.client.post(
            "/api/v1/scan", 
            json={"prompt": "Hello world"},
            headers={"x-api-key": "invalid_key"}
        )
        self.assertEqual(res_scan_invalid.status_code, 401)
        
        # 5. Scan with valid generated key
        res_scan_valid = self.client.post(
            "/api/v1/scan", 
            json={"prompt": "Hello world"},
            headers={"x-api-key": raw_key}
        )
        self.assertEqual(res_scan_valid.status_code, 200)
        self.assertTrue(res_scan_valid.json()["is_safe"])
        
        # 6. Revoke the key (restore session cookie first)
        self.client.cookies.set("session_token", username)
        res_del = self.client.delete(f"/api/v1/keys/{key_id}")
        self.assertEqual(res_del.status_code, 200)
        
        # 7. Scan with revoked key (remove cookie)
        self.client.cookies.delete("session_token")
        res_scan_revoked = self.client.post(
            "/api/v1/scan", 
            json={"prompt": "Hello world"},
            headers={"x-api-key": raw_key}
        )
        self.assertEqual(res_scan_revoked.status_code, 401)

if __name__ == '__main__':
    unittest.main()
