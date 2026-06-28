#!/usr/bin/env python3
"""
ngrok_launcher.py  — starts ngrok, gets the public URL, patches the frontend,
generates a QR code, and prints a clean summary.
Run AFTER the backend is already running (python app.py).
EcoComply | IBM Bobathon 2025
"""

import subprocess
import threading
import time
import json
import sys
import os
import re
import urllib.request

BACKEND_PORT  = 5000
FRONTEND_PORT = 8888
BACKEND_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR   = os.path.dirname(BACKEND_DIR)
FRONTEND_DIR  = os.path.join(PROJECT_DIR, "frontend")
DATA_DIR      = os.path.join(PROJECT_DIR, "data")


def get_ngrok_url(port: int, retries: int = 15) -> str:
    """Poll ngrok local API until the public URL is available."""
    for i in range(retries):
        try:
            with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=3) as r:
                data = json.loads(r.read())
                for t in data.get("tunnels", []):
                    if str(port) in t.get("config", {}).get("addr", ""):
                        url = t["public_url"]
                        if url.startswith("https://"):
                            return url
                # Also accept any https tunnel if port not matched
                for t in data.get("tunnels", []):
                    if t["public_url"].startswith("https://"):
                        return t["public_url"]
        except Exception:
            pass
        time.sleep(1)
        print(f"  Waiting for ngrok tunnel… ({i+1}/{retries})", end="\r")
    return ""


def patch_frontend(api_url: str):
    """Patch main.js so the frontend always points to the ngrok backend URL."""
    main_js = os.path.join(FRONTEND_DIR, "js", "main.js")
    with open(main_js, encoding="utf-8") as f:
        content = f.read()

    # Replace the dynamic API_BASE block with a hardcoded ngrok URL
    patched = re.sub(
        r"const _host.*?const API_BASE = [^;]+;",
        f'// Patched by ngrok_launcher.py\nconst API_BASE = "{api_url}/api";',
        content,
        flags=re.DOTALL
    )

    if patched == content:
        # Fallback: replace any existing API_BASE line
        patched = re.sub(
            r'const API_BASE\s*=\s*["\`][^"\`]+["\`];',
            f'const API_BASE = "{api_url}/api";',
            content
        )

    with open(main_js, "w", encoding="utf-8") as f:
        f.write(patched)
    print(f"  ✅ main.js patched → API_BASE = {api_url}/api")


def restore_frontend():
    """Restore main.js to dynamic mode after session ends."""
    main_js = os.path.join(FRONTEND_DIR, "js", "main.js")
    with open(main_js, encoding="utf-8") as f:
        content = f.read()

    restored = re.sub(
        r"// Patched by ngrok_launcher\.py\nconst API_BASE = \"[^\"]+\";",
        """// ── Dynamic API base: works on localhost AND from phone on same WiFi ──────────
// If the page is loaded from a non-localhost origin, use that same host for the API.
const _host   = window.location.hostname;
const API_BASE = (_host === "localhost" || _host === "127.0.0.1")
  ? "http://localhost:5000/api"
  : `http://${_host}:5000/api`;""",
        content
    )
    with open(main_js, "w", encoding="utf-8") as f:
        f.write(restored)
    print("  main.js restored to dynamic mode.")


def start_ngrok(port: int) -> subprocess.Popen:
    proc = subprocess.Popen(
        ["ngrok", "http", str(port), "--log=stdout"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    return proc


def start_frontend_server(port: int) -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port)],
        cwd=FRONTEND_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    return proc


def generate_qr(url: str):
    try:
        sys.path.insert(0, BACKEND_DIR)
        from generate_qr import write_qr_page
        os.makedirs(DATA_DIR, exist_ok=True)
        write_qr_page(
            url,
            out_html=os.path.join(DATA_DIR, "demo_qr.html"),
            out_png=os.path.join(DATA_DIR, "demo_qr.png"),
        )
    except Exception as e:
        print(f"  QR generation skipped: {e}")


def print_banner(backend_url: str, frontend_url: str, onboard_url: str):
    sep = "═" * 58
    print(f"\n  {sep}")
    print(f"  🛡️  REGULATORY RADAR — LIVE DEPLOYMENT")
    print(f"  {sep}")
    print(f"  🌍  Backend  API   →  {backend_url}/api/health")
    print(f"  🌐  Frontend       →  {frontend_url}")
    print(f"  📱  Onboarding     →  {onboard_url}")
    print(f"  📊  Dashboard      →  {frontend_url}/dashboard.html")
    print(f"  ⚡  Pipeline       →  {frontend_url}/pipeline.html")
    print(f"  {sep}")
    print(f"  QR code → Project/data/demo_qr.html  (open in browser)")
    print(f"  QR PNG  → Project/data/demo_qr.png   (show on screen / print)")
    print(f"  {sep}")
    print(f"  Press Ctrl+C to stop all services.\n")


def main():
    print("\n🚀 Starting Regulatory Radar deployment…\n")

    # 1. Start ngrok tunnel for backend (port 5000)
    print("  [1/4] Starting ngrok tunnel for backend…")
    ngrok_proc = start_ngrok(BACKEND_PORT)
    time.sleep(2)

    backend_ngrok_url = get_ngrok_url(BACKEND_PORT)
    if not backend_ngrok_url:
        print("  ❌ Could not get ngrok URL. Is ngrok authenticated?")
        print("     Run:  ngrok config add-authtoken <your-token>")
        print("     Get a free token at: https://dashboard.ngrok.com/authtokens")
        ngrok_proc.terminate()
        sys.exit(1)
    print(f"\n  ✅ Backend ngrok URL: {backend_ngrok_url}")

    # 2. Patch frontend to point to ngrok backend
    print("  [2/4] Patching frontend API base…")
    patch_frontend(backend_ngrok_url)

    # 3. Start frontend HTTP server
    print(f"  [3/4] Starting frontend server on port {FRONTEND_PORT}…")
    fe_proc = start_frontend_server(FRONTEND_PORT)
    time.sleep(1)

    # 4. Generate QR code for the onboarding page
    # Use ngrok URL for backend; frontend served locally (same WiFi) or via another tunnel
    onboard_url = f"http://192.168.0.127:{FRONTEND_PORT}/onboard.html"
    print(f"  [4/4] Generating QR code for {onboard_url}…")
    generate_qr(onboard_url)

    frontend_url = f"http://192.168.0.127:{FRONTEND_PORT}"
    print_banner(backend_ngrok_url, frontend_url, onboard_url)

    # Keep running
    try:
        while True:
            time.sleep(5)
            # Check if ngrok is still alive
            if ngrok_proc.poll() is not None:
                print("  ⚠️  ngrok tunnel dropped. Restarting…")
                ngrok_proc = start_ngrok(BACKEND_PORT)
                time.sleep(3)
                new_url = get_ngrok_url(BACKEND_PORT)
                if new_url and new_url != backend_ngrok_url:
                    backend_ngrok_url = new_url
                    patch_frontend(backend_ngrok_url)
                    generate_qr(f"http://192.168.0.127:{FRONTEND_PORT}/onboard.html")
                    print(f"  ✅ New ngrok URL: {backend_ngrok_url}")
    except KeyboardInterrupt:
        print("\n\n  Stopping services…")
        restore_frontend()
        ngrok_proc.terminate()
        fe_proc.terminate()
        print("  ✅ Clean shutdown. Goodbye.\n")


if __name__ == "__main__":
    main()
