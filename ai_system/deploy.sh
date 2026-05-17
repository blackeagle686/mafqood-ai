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

# 2. Apply migrations
echo "[*] Applying SQLite database migrations..."
python app/manage.py makemigrations
python app/manage.py migrate
echo "[+] Database schemas are up-to-date."

# 3. Verify Redis Broker Connectivity
echo "[*] Verifying Redis connection on port 6379..."
if nc -z localhost 6379 2>/dev/null; then
    echo "[+] Local Redis instance is running."
else
    echo "[!] Redis is NOT running on port 6379."
    echo "    Attempting to start Redis using docker-compose..."
    if command -v docker-compose &> /dev/null; then
        docker-compose up -d redis
        echo "[+] Successfully launched Redis container via docker-compose."
    elif command -v docker &> /dev/null; then
        docker run -d --name mafqood-redis -p 6379:6379 redis:alpine
        echo "[+] Successfully launched Redis container via raw docker."
    else
        echo "[WARNING] Docker/docker-compose not found. Celery task queue might fail if Redis is unreachable."
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
echo "[*] Setting up ngrok tunnel..."
NGROK_TOKEN="3DqGR1alEbozJwsc2X1qhKUAJtC_4CEjQRnaypvLAz8jPoMgW"

if command -v ngrok &> /dev/null; then
    echo "[*] Configuring ngrok authtoken..."
    ngrok config add-authtoken "$NGROK_TOKEN"
    
    echo "[*] Cleaning up lingering ngrok instances..."
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
        taskkill //IM "ngrok.exe" //F 2>/dev/null || true
    else
        pkill -f "ngrok http" 2>/dev/null || true
    fi
    
    echo "[*] Launching ngrok HTTP tunnel on port 8000..."
    ngrok http 8000 > logs/ngrok.log 2>&1 &
    
    # Wait for ngrok to establish tunnel connection
    sleep 3
    
    # Extract and display the live public URL
    if command -v curl &> /dev/null; then
        PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels | python -c "import sys, json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])" 2>/dev/null || true)
        if [ ! -z "$PUBLIC_URL" ]; then
            echo "[+] Public ngrok URL: $PUBLIC_URL"
        else
            echo "[+] ngrok tunnel launched in background. Check http://localhost:4040 or logs/ngrok.log for URL."
        fi
    else
        echo "[+] ngrok tunnel launched in background. Check http://localhost:4040 or logs/ngrok.log for URL."
    fi
else
    echo "[WARNING] ngrok command not found. Skipping public tunnel exposure."
fi

# 8. Start Django App development server
echo "[*] Starting Django application server..."
echo "[+] Mafqood AI endpoints will be available at: http://localhost:8000"
echo "----------------------------------------------------"
python app/manage.py runserver 0.0.0.0:8000

