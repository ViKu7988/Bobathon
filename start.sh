#!/bin/bash
# ============================================================
#  start.sh — ONE COMMAND TO START REGULATORY RADAR
#  EcoComply | IBM Bobathon 2025
#  Usage:  bash start.sh
# ============================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
DATA_DIR="$SCRIPT_DIR/data"
LOG_DIR="$SCRIPT_DIR/logs"

BACKEND_PORT=5000
FRONTEND_PORT=8888

BLUE='\033[0;34m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; BOLD='\033[1m'; RESET='\033[0m'

mkdir -p "$LOG_DIR"

banner() {
  echo -e "\n${BLUE}${BOLD}════════════════════════════════════════════════════${RESET}"
  echo -e "${BLUE}${BOLD}  🛡️  Regulatory Radar — Starting Up${RESET}"
  echo -e "${BLUE}${BOLD}  EcoComply · IBM Bobathon 2025${RESET}"
  echo -e "${BLUE}${BOLD}════════════════════════════════════════════════════${RESET}\n"
}

cleanup() {
  echo -e "\n${YELLOW}  Shutting down all services…${RESET}"
  [ -f "$LOG_DIR/backend.pid"  ] && kill $(cat "$LOG_DIR/backend.pid")  2>/dev/null; rm -f "$LOG_DIR/backend.pid"
  [ -f "$LOG_DIR/frontend.pid" ] && kill $(cat "$LOG_DIR/frontend.pid") 2>/dev/null; rm -f "$LOG_DIR/frontend.pid"
  [ -f "$LOG_DIR/ngrok.pid"    ] && kill $(cat "$LOG_DIR/ngrok.pid")    2>/dev/null; rm -f "$LOG_DIR/ngrok.pid"
  # Restore main.js
  cd "$BACKEND_DIR" && source venv/bin/activate && python ngrok_launcher.py --restore-only 2>/dev/null || true
  echo -e "${GREEN}  ✅ Clean shutdown. Goodbye.${RESET}\n"
  exit 0
}
trap cleanup SIGINT SIGTERM

banner

# ── Step 1: Backend ──────────────────────────────────────────────────────────
echo -e "${BOLD}[1/4] Starting Flask backend on port $BACKEND_PORT…${RESET}"
cd "$BACKEND_DIR"
if [ ! -d "venv" ]; then
  echo "  Creating virtual environment…"
  python3 -m venv venv
  source venv/bin/activate
  pip install -q -r requirements.txt
else
  source venv/bin/activate
fi

# Kill anything already on port 5000
fuser -k ${BACKEND_PORT}/tcp 2>/dev/null || true
sleep 0.5

# Start with gunicorn for stability (auto-restarts workers)
gunicorn app:create_app\(\) \
  --bind "0.0.0.0:$BACKEND_PORT" \
  --workers 2 \
  --timeout 60 \
  --log-level info \
  --access-logfile "$LOG_DIR/access.log" \
  --error-logfile "$LOG_DIR/error.log" \
  --daemon \
  --pid "$LOG_DIR/backend.pid"

sleep 2
# Verify it started
if curl -sf "http://localhost:$BACKEND_PORT/api/health" > /dev/null 2>&1; then
  echo -e "${GREEN}  ✅ Backend running on :$BACKEND_PORT${RESET}"
else
  echo -e "${RED}  ❌ Backend failed to start — check logs/error.log${RESET}"
  exit 1
fi

# ── Step 2: Frontend ─────────────────────────────────────────────────────────
echo -e "\n${BOLD}[2/4] Starting frontend server on port $FRONTEND_PORT…${RESET}"
# Kill anything already on that port
fuser -k ${FRONTEND_PORT}/tcp 2>/dev/null || true
sleep 0.5

python3 -m http.server $FRONTEND_PORT --directory "$FRONTEND_DIR" \
  > "$LOG_DIR/frontend.log" 2>&1 &
echo $! > "$LOG_DIR/frontend.pid"
sleep 1
echo -e "${GREEN}  ✅ Frontend running on :$FRONTEND_PORT${RESET}"

# ── Step 3: ngrok tunnel ─────────────────────────────────────────────────────
echo -e "\n${BOLD}[3/4] Starting ngrok public tunnel for backend…${RESET}"
fuser -k 4040/tcp 2>/dev/null || true
sleep 0.5
ngrok http $BACKEND_PORT --log stdout > "$LOG_DIR/ngrok.log" 2>&1 &
echo $! > "$LOG_DIR/ngrok.pid"

# Wait for tunnel URL
NGROK_URL=""
for i in $(seq 1 15); do
  sleep 1
  NGROK_URL=$(curl -sf http://127.0.0.1:4040/api/tunnels 2>/dev/null \
    | python3 -c "import sys,json; d=json.load(sys.stdin); \
      [print(t['public_url']) for t in d.get('tunnels',[]) \
       if t['public_url'].startswith('https')]" 2>/dev/null | head -1)
  [ -n "$NGROK_URL" ] && break
  echo -ne "  Waiting for tunnel… ($i/15)\r"
done

if [ -z "$NGROK_URL" ]; then
  echo -e "${YELLOW}  ⚠️  ngrok tunnel not available.${RESET}"
  echo "  → If you haven't authenticated: ngrok config add-authtoken <token>"
  echo "  → Get a free token at: https://dashboard.ngrok.com/authtokens"
  echo "  → Continuing with local access only (WiFi required for phone)."
  NGROK_URL="http://$(hostname -I | awk '{print $1}'):$BACKEND_PORT"
else
  echo -e "${GREEN}  ✅ ngrok URL: $NGROK_URL${RESET}"
  # Patch frontend to use ngrok URL
  python3 - <<PYEOF
import re, os
js = os.path.join("$FRONTEND_DIR", "js", "main.js")
with open(js) as f: c = f.read()
patched = re.sub(
    r"(// Patched by ngrok_launcher\.py\n)?const API_BASE = [^;]+;",
    f'// Patched by start.sh\nconst API_BASE = "$NGROK_URL/api";', c, flags=re.DOTALL)
if patched == c:
    patched = re.sub(r"const _host.*?`http://\$\{_host\}:5000/api`;",
        f'// Patched by start.sh\nconst API_BASE = "$NGROK_URL/api";', c, flags=re.DOTALL)
with open(js, "w") as f: f.write(patched)
print("  main.js patched → API_BASE = $NGROK_URL/api")
PYEOF
fi

# ── Step 4: QR code ──────────────────────────────────────────────────────────
echo -e "\n${BOLD}[4/4] Generating QR code…${RESET}"
LOCAL_IP=$(hostname -I | awk '{print $1}')
ONBOARD_URL="http://$LOCAL_IP:$FRONTEND_PORT/onboard.html"

cd "$BACKEND_DIR"
python3 generate_qr.py "$ONBOARD_URL" 2>/dev/null && \
  echo -e "${GREEN}  ✅ QR code saved to data/demo_qr.html and data/demo_qr.png${RESET}" || \
  echo -e "${YELLOW}  ⚠️  QR generation skipped${RESET}"

# ── Summary ──────────────────────────────────────────────────────────────────
echo -e "\n${BLUE}${BOLD}════════════════════════════════════════════════════${RESET}"
echo -e "${BLUE}${BOLD}  🛡️  REGULATORY RADAR — RUNNING${RESET}"
echo -e "${BLUE}${BOLD}════════════════════════════════════════════════════${RESET}"
echo -e "  ${GREEN}Backend  API${RESET}  →  ${BOLD}http://localhost:$BACKEND_PORT/api/health${RESET}"
echo -e "  ${GREEN}Frontend    ${RESET}  →  ${BOLD}http://localhost:$FRONTEND_PORT${RESET}"
echo -e "  ${GREEN}Onboarding  ${RESET}  →  ${BOLD}http://$LOCAL_IP:$FRONTEND_PORT/onboard.html${RESET}"
echo -e "  ${GREEN}Dashboard   ${RESET}  →  ${BOLD}http://localhost:$FRONTEND_PORT/dashboard.html${RESET}"
echo -e "  ${GREEN}Pipeline    ${RESET}  →  ${BOLD}http://localhost:$FRONTEND_PORT/pipeline.html${RESET}"
echo -e "  ${GREEN}ngrok API   ${RESET}  →  ${BOLD}$NGROK_URL${RESET}"
echo -e "  ${GREEN}QR Code     ${RESET}  →  ${BOLD}Project/data/demo_qr.html${RESET}"
echo -e ""
echo -e "  ${YELLOW}📱 Phone access URL (same WiFi):${RESET}"
echo -e "     ${BOLD}http://$LOCAL_IP:$FRONTEND_PORT/onboard.html${RESET}"
echo -e ""
echo -e "  ${YELLOW}🌍 Public URL (any device, any network):${RESET}"
echo -e "     ${BOLD}$NGROK_URL${RESET}"
echo -e "${BLUE}${BOLD}════════════════════════════════════════════════════${RESET}"
echo -e "  Press ${BOLD}Ctrl+C${RESET} to stop all services.\n"

# Show QR in terminal if qrencode is available
if command -v qrencode &>/dev/null; then
  qrencode -t UTF8 "$ONBOARD_URL"
fi

# Tail logs
echo -e "${BOLD}  Backend logs (Ctrl+C to stop):${RESET}"
tail -f "$LOG_DIR/access.log" "$LOG_DIR/error.log" 2>/dev/null
