#!/bin/bash
# ====================================================================
#         Mafqood AI System Deployment & Startup Orchestrator         
# ====================================================================
# Coordinates the virtualenv, database migrations, Redis broker,
# Celery worker, Celery beat, and the Django REST server.

set -e # Exit immediately on error

echo "===================================================="
echo "         Mafqood AI System Orchestrator Script      "
echo "===================================================="

# Create logs directory if it doesn't exist
mkdir -p logs

# 1. Virtual Environment Activation
VENV_DIR="mafqood_venv"
if [ -d "$VENV_DIR" ]; then
    echo "[*] Activating virtual environment..."
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
        source $VENV_DIR/Scripts/activate
    else
        source $VENV_DIR/bin/activate
    fi
    echo "[+] Virtual environment successfully activated."
else
    echo "[!] Virtual environment '$VENV_DIR' not found. Proceeding with system python..."
fi

# 1.5. Automatic Dependency Check & Installation
echo "[*] Checking python dependencies..."
if ! python -c "import django" &>/dev/null; then
    echo "[!] Django or required libraries not found in active python environment."
    if [ -f "requirements.txt" ]; then
        echo "[*] Installing dependencies from requirements.txt..."
        python -m pip install --upgrade pip
        python -m pip install -r requirements.txt
    else
        echo "[*] Installing core dependencies manually..."
        python -m pip install --upgrade pip
        python -m pip install django djangorestframework django-environ celery redis httpx
    fi
    echo "[+] Dependencies successfully installed."
else
    echo "[+] All python dependencies are satisfied."
fi


# 2. Apply migrations
echo "[*] Applying SQLite database migrations..."
python app/manage.py makemigrations
python app/manage.py migrate
echo "[+] Database schemas are up-to-date."

# 3. Verify Redis Broker Connectivity
echo "[*] Verifying Redis connection on port 6379..."

# Auto-install Redis if missing in Linux (Debian/Ubuntu) environments
if ! command -v redis-server &> /dev/null; then
    if command -v apt-get &> /dev/null; then
        echo "[!] redis-server command not found. Attempting automatic installation..."
        SUDO_CMD=""
        if command -v sudo &> /dev/null; then SUDO_CMD="sudo"; fi
        $SUDO_CMD apt-get update && $SUDO_CMD apt-get install -y redis-server
    fi
fi

if python -c "import socket; s = socket.socket(); s.connect(('127.0.0.1', 6379))" 2>/dev/null; then
    echo "[+] Local Redis instance is running."
else
    echo "[!] Redis is NOT running on port 6379."
    # Attempt to start local redis-server
    if command -v redis-server &> /dev/null; then
        echo "[*] Launching local redis-server in background..."
        SUDO_CMD=""
        if command -v sudo &> /dev/null; then SUDO_CMD="sudo"; fi
        if command -v service &> /dev/null; then
            $SUDO_CMD service redis-server start || true
        else
            redis-server --daemonize yes || redis-server &
        fi
        sleep 2
    fi
    
    # Re-verify or fall back to docker
    if python -c "import socket; s = socket.socket(); s.connect(('127.0.0.1', 6379))" 2>/dev/null; then
        echo "[+] Redis successfully launched and active."
    else
        echo "    Attempting to start Redis using docker-compose..."
        if command -v docker-compose &> /dev/null; then
            docker-compose up -d redis
            echo "[+] Successfully launched Redis container via docker-compose."
        elif command -v docker &> /dev/null; then
            docker run -d --name mafqood-redis -p 6379:6379 redis:alpine
            echo "[+] Successfully launched Redis container via raw docker."
        else
            echo "[WARNING] Could not start Redis. Celery task queue might fail if Redis is unreachable."
        fi
    fi
fi

# 4. Stop lingering Celery worker & beat instances
echo "[*] Cleaning up lingering Celery workers..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
    taskkill //IM "celery.exe" //F 2>/dev/null || true
else
    pkill -f "celery -A celery_app" 2>/dev/null || true
fi

# 5. Start Celery worker in the background
echo "[*] Starting Celery background worker..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
    # On Windows Celery requires the -P solo execution pool to process background tasks without spawning locks
    celery -A celery_app -C app worker --loglevel=info -P solo > logs/celery_worker.log 2>&1 &
else
    celery -A celery_app -C app worker --loglevel=info > logs/celery_worker.log 2>&1 &
fi
echo "[+] Celery worker launched. Logs: logs/celery_worker.log"

# 6. Start Celery Beat scheduler in the background
echo "[*] Starting Celery Beat scheduler..."
celery -A celery_app -C app beat --loglevel=info > logs/celery_beat.log 2>&1 &
echo "[+] Celery Beat scheduler launched. Logs: logs/celery_beat.log"

# 7. Start ngrok tunnel for public exposure
echo "[*] Setting up ngrok tunnel via pyngrok SDK..."

# Clean up lingering ngrok instances to avoid conflicts
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
    taskkill //IM "ngrok.exe" //F 2>/dev/null || true
else
    pkill -f "infra/ngrok_tunnel.py" 2>/dev/null || true
    pkill -f "ngrok http" 2>/dev/null || true
fi

# Run the python-native ngrok tunnel manager in the background
python infra/ngrok_tunnel.py > logs/ngrok.log 2>&1 &

# Wait for tunnel initialization and retrieve the URL (handles first-time download delay)
echo "[*] Waiting for ngrok tunnel to establish..."
PUBLIC_URL=""
for i in {1..20}; do
    if [ -f "logs/ngrok.log" ]; then
        PUBLIC_URL=$(grep -o -E "https://[a-zA-Z0-9.-]+\.ngrok-free\.app" logs/ngrok.log | head -n 1 || true)
        if [ ! -z "$PUBLIC_URL" ]; then
            break
        fi
    fi
    sleep 1
done

echo "----------------------------------------------------"
if [ ! -z "$PUBLIC_URL" ]; then
    echo "[+] Public ngrok URL: $PUBLIC_URL"
else
    echo "[+] ngrok tunnel launched in background. Check logs/ngrok.log for URL."
fi
echo "[+] Mafqood API Key (X-Api-Key): mafqood-ai-secure-token-2026"
echo "----------------------------------------------------"

# 8. Start Django App development server
echo "[*] Starting Django application server..."
echo "[+] Mafqood AI local endpoints will be available at: http://localhost:8000"
echo "----------------------------------------------------"
python app/manage.py runserver 0.0.0.0:8000

