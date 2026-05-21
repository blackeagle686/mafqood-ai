#!/bin/bash
# ====================================================================
#         Mafqood AI System Deployment & Startup Orchestrator
# ====================================================================
# Coordinates:
# - Virtual Environment
# - Dependency Installation
# - Database Migrations
# - Redis Broker
# - Celery Worker
# - Celery Beat
# - ngrok Tunnel
# - Django Development Server
#
# Safe for running alongside production services.
# Production on port 8000 will NOT be touched.
# ====================================================================

set -e

echo "===================================================="
echo "         Mafqood AI System Orchestrator             "
echo "===================================================="

# --------------------------------------------------------------------
# Prevent duplicate orchestrator instances
# --------------------------------------------------------------------
LOCKFILE="/tmp/mafqood_orchestrator.lock"

if [ -f "$LOCKFILE" ]; then
    echo "[!] Another orchestrator instance is already running."
    exit 1
fi

trap "rm -f $LOCKFILE" EXIT
touch "$LOCKFILE"

# --------------------------------------------------------------------
# Create logs directory
# --------------------------------------------------------------------
mkdir -p logs

# --------------------------------------------------------------------
# Virtual Environment Activation
# --------------------------------------------------------------------
VENV_DIR="mafqood_venv"

if [ -d "$VENV_DIR" ]; then
    echo "[*] Activating virtual environment..."

    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
        source "$VENV_DIR/Scripts/activate"
    else
        source "$VENV_DIR/bin/activate"
    fi

    echo "[+] Virtual environment activated."
else
    echo "[!] Virtual environment '$VENV_DIR' not found."
    echo "[!] Proceeding with system Python..."
fi

# --------------------------------------------------------------------
# Dependency Check
# --------------------------------------------------------------------
echo "[*] Checking Python dependencies..."

if ! python -c "import django" &>/dev/null; then

    echo "[!] Required dependencies missing."

    python -m pip install --upgrade pip

    if [ -f "requirements.txt" ]; then
        echo "[*] Installing from requirements.txt..."
        python -m pip install -r requirements.txt
    else
        echo "[*] Installing core dependencies..."
        python -m pip install \
            django \
            djangorestframework \
            django-environ \
            celery \
            redis \
            httpx \
            pyngrok
    fi

    echo "[+] Dependencies installed."
else
    echo "[+] Dependencies already satisfied."
fi

# --------------------------------------------------------------------
# Database Migrations
# --------------------------------------------------------------------
echo "[*] Applying database migrations..."

python app/manage.py makemigrations
python app/manage.py migrate

echo "[+] Database is up-to-date."

# --------------------------------------------------------------------
# Redis Check
# --------------------------------------------------------------------
echo "[*] Verifying Redis connection on port 6379..."

if ! command -v redis-server &>/dev/null; then

    if command -v apt-get &>/dev/null; then

        echo "[!] redis-server not found. Installing..."

        SUDO_CMD=""
        if command -v sudo &>/dev/null; then
            SUDO_CMD="sudo"
        fi

        $SUDO_CMD apt-get update
        $SUDO_CMD apt-get install -y redis-server
    fi
fi

# --------------------------------------------------------------------
# Celery Command Detection
# --------------------------------------------------------------------
CELERY_CMD=""

if command -v celery &>/dev/null; then
    CELERY_CMD="celery"

elif python -c "import celery" &>/dev/null; then
    CELERY_CMD="python -m celery"

fi

if [ -z "$CELERY_CMD" ]; then
    echo "[ERROR] Celery is not installed."
    exit 1
fi

echo "[+] Using Celery command: $CELERY_CMD"

# --------------------------------------------------------------------
# Check Redis Socket
# --------------------------------------------------------------------
if python - <<'PY'
import socket

s = socket.socket()

try:
    s.connect(("127.0.0.1", 6379))
    print("Redis reachable")
    exit(0)

except Exception:
    exit(1)
PY
then
    echo "[+] Redis is running."
else

    echo "[!] Redis is NOT running."
    echo "[*] Attempting to start Redis..."

    if command -v service &>/dev/null; then

        SUDO_CMD=""
        if command -v sudo &>/dev/null; then
            SUDO_CMD="sudo"
        fi

        $SUDO_CMD service redis-server start || true

    elif command -v redis-server &>/dev/null; then

        redis-server --daemonize yes

    fi

    sleep 2
fi

# --------------------------------------------------------------------
# Cleanup old Celery instances ONLY for current project
# --------------------------------------------------------------------
echo "[*] Cleaning old Celery processes..."

pkill -f "app.celery_app worker" 2>/dev/null || true
pkill -f "app.celery_app beat" 2>/dev/null || true

# --------------------------------------------------------------------
# Start Celery Worker
# --------------------------------------------------------------------
echo "[*] Starting Celery worker..."

if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then

    $CELERY_CMD -A app.celery_app worker \
        --loglevel=info \
        -P solo \
        > logs/celery_worker.log 2>&1 &

else

    $CELERY_CMD -A app.celery_app worker \
        --loglevel=info \
        > logs/celery_worker.log 2>&1 &
fi

echo "[+] Celery worker started."

# --------------------------------------------------------------------
# Start Celery Beat
# --------------------------------------------------------------------
echo "[*] Starting Celery Beat..."

$CELERY_CMD -A app.celery_app beat \
    --loglevel=info \
    > logs/celery_beat.log 2>&1 &

echo "[+] Celery Beat started."

# --------------------------------------------------------------------
# Port Utilities
# --------------------------------------------------------------------
port_free() {

    python - "$1" <<'PY' 2>/dev/null
import socket
import sys

port = int(sys.argv[1])

s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

try:
    s.bind(("0.0.0.0", port))
    s.close()
    exit(0)

except OSError:
    exit(1)
PY
}

find_available_port() {

    local start_port=${1:-8001}
    local end_port=${2:-8100}

    for port in $(seq "$start_port" "$end_port"); do

        if port_free "$port"; then
            echo "$port"
            return 0
        fi

    done

    return 1
}

# --------------------------------------------------------------------
# Dynamic Django Port Selection
# --------------------------------------------------------------------
RUNSERVER_PORT=${DJANGO_PORT:-8001}

if port_free "$RUNSERVER_PORT"; then

    echo "[+] Using Django port: $RUNSERVER_PORT"

else

    echo "[!] Port $RUNSERVER_PORT already in use."
    echo "[*] Searching for another port..."

    RUNSERVER_PORT=$(find_available_port 8001 8100)

    if [ -z "$RUNSERVER_PORT" ]; then
        echo "[ERROR] No free ports available."
        exit 1
    fi

    echo "[+] Selected alternative port: $RUNSERVER_PORT"
fi

export NGROK_PORT="$RUNSERVER_PORT"

# --------------------------------------------------------------------
# ngrok Setup
# --------------------------------------------------------------------
echo "[*] Setting up ngrok tunnel..."

# Kill ONLY current project tunnel manager
pkill -f "infra/ngrok_tunnel.py" 2>/dev/null || true

python infra/ngrok_tunnel.py \
    > logs/ngrok.log 2>&1 &

# --------------------------------------------------------------------
# Wait for ngrok URL
# --------------------------------------------------------------------
echo "[*] Waiting for ngrok tunnel..."

PUBLIC_URL=""

for i in {1..20}; do

    if [ -f "logs/ngrok.log" ]; then

        PUBLIC_URL=$(grep -o -E \
            "https://[a-zA-Z0-9.-]+\.ngrok-free\.app" \
            logs/ngrok.log | head -n 1 || true)

        if [ ! -z "$PUBLIC_URL" ]; then
            break
        fi
    fi

    sleep 1
done

# --------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------
echo "----------------------------------------------------"

if [ ! -z "$PUBLIC_URL" ]; then
    echo "[+] Public URL: $PUBLIC_URL"
else
    echo "[!] ngrok started but URL not detected yet."
fi

echo "[+] Local URL: http://localhost:$RUNSERVER_PORT"
echo "[+] API KEY: mafqood-ai-secure-token-2026"

echo "----------------------------------------------------"

# --------------------------------------------------------------------
# Start Django Server
# --------------------------------------------------------------------
echo "[*] Starting Django server..."

python app/manage.py runserver 0.0.0.0:$RUNSERVER_PORT