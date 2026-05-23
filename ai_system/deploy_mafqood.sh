#!/bin/bash
# ====================================================================
#         Mafqood AI System Deployment & Startup Orchestrator
# ====================================================================
# Coordinates:
# - Virtual Environment
# - Dependency Installation (including gunicorn for production)
# - Database Migrations
# - Redis Broker
# - Celery Worker (Daemonized)
# - Celery Beat (Daemonized)
# - ngrok Tunnel (Daemonized)
# - Django Production Server (Gunicorn Daemonized)
#
# Usage:
#   ./deploy.sh start         Start all services in background
#   ./deploy.sh stop          Stop all services
#   ./deploy.sh restart       Restart all services
#   ./deploy.sh status        Check running status of services
#   ./deploy.sh logs [svc]    Tail logs (django, celery, beat, ngrok, all)
# ====================================================================

# Directory context
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

mkdir -p logs

LOCKFILE="/tmp/mafqood_orchestrator.lock"

# Colors for terminal output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Detect Python Command
PYTHON_CMD="python"
if ! command -v python &>/dev/null; then
    if command -v python3 &>/dev/null; then
        PYTHON_CMD="python3"
    else
        echo -e "${RED}[ERROR] Python is not installed or available in PATH.${NC}"
        exit 1
    fi
fi

show_help() {
    echo -e "${BLUE}====================================================${NC}"
    echo -e "         ${GREEN}Mafqood AI Orchestrator CLI Helper${NC}"
    echo -e "${BLUE}====================================================${NC}"
    echo "Usage: $0 {start|stop|restart|status|logs}"
    echo ""
    echo "Commands:"
    echo "  start         Start all services in the background (Django, Celery, ngrok)"
    echo "  stop          Stop all background services safely"
    echo "  restart       Stop and then start all services"
    echo "  status        Check the running status of each subsystem"
    echo "  logs [svc]    Tail log files for a specific service"
    echo "                Services: django, celery, beat, ngrok, all"
    echo ""
    echo "Examples:"
    echo "  $0 start      # Starts everything"
    echo "  $0 status     # Inspects running processes"
    echo "  $0 logs all   # Tails worker and server outputs simultaneously"
    echo -e "${BLUE}====================================================${NC}"
}

# --------------------------------------------------------------------
# Virtual Environment Activation
# --------------------------------------------------------------------
activate_venv() {
    VENV_DIR="mafqood_venv"
    if [ -d "$VENV_DIR" ]; then
        echo -e "${BLUE}[*] Activating virtual environment...${NC}"
        if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
            source "$VENV_DIR/Scripts/activate"
        else
            source "$VENV_DIR/bin/activate"
        fi
        echo -e "${GREEN}[+] Virtual environment activated.${NC}"
        # Update python command to point to venv
        PYTHON_CMD="python"
    else
        echo -e "${YELLOW}[!] Virtual environment '$VENV_DIR' not found. Using system Python.${NC}"
    fi
}

# --------------------------------------------------------------------
# Dependency Check
# --------------------------------------------------------------------
check_dependencies() {
    echo -e "${BLUE}[*] Checking Python dependencies...${NC}"
    if ! $PYTHON_CMD -c "import django" &>/dev/null || ! $PYTHON_CMD -c "import gunicorn" &>/dev/null || ! $PYTHON_CMD -c "import whitenoise" &>/dev/null; then
        echo -e "${YELLOW}[!] Required dependencies or Gunicorn/Whitenoise missing. Installing...${NC}"
        $PYTHON_CMD -m pip install --upgrade pip
        if [ -f "requirements.txt" ]; then
            echo -e "${BLUE}[*] Installing dependencies from requirements.txt...${NC}"
            $PYTHON_CMD -m pip install -r requirements.txt
        fi
        echo -e "${BLUE}[*] Installing production dependencies (Gunicorn, Celery, Redis, pyngrok, Whitenoise)...${NC}"
        $PYTHON_CMD -m pip install django djangorestframework django-environ celery redis httpx pyngrok gunicorn whitenoise
        echo -e "${GREEN}[+] Dependencies installed successfully.${NC}"
    else
        echo -e "${GREEN}[+] Dependencies already satisfied.${NC}"
    fi
}

# --------------------------------------------------------------------
# Database Migrations
# --------------------------------------------------------------------
run_migrations() {
    echo -e "${BLUE}[*] Running database migrations...${NC}"
    $PYTHON_CMD app/manage.py makemigrations
    $PYTHON_CMD app/manage.py migrate
    echo -e "${GREEN}[+] Database schema is up-to-date.${NC}"
}

# --------------------------------------------------------------------
# Collect Static Files
# --------------------------------------------------------------------
collect_static() {
    echo -e "${BLUE}[*] Collecting static files...${NC}"
    $PYTHON_CMD app/manage.py collectstatic --noinput
    echo -e "${GREEN}[+] Static files collected successfully.${NC}"
}

# --------------------------------------------------------------------
# Redis Connection & Daemonization Check
# --------------------------------------------------------------------
check_start_redis() {
    echo -e "${BLUE}[*] Verifying Redis connection on port 6379...${NC}"
    if ! command -v redis-server &>/dev/null; then
        if command -v apt-get &>/dev/null; then
            echo -e "${YELLOW}[!] Redis not found. Installing via apt...${NC}"
            SUDO_CMD=""
            if command -v sudo &>/dev/null; then
                SUDO_CMD="sudo"
            fi
            $SUDO_CMD apt-get update
            $SUDO_CMD apt-get install -y redis-server
        fi
    fi

    # Connect to verify availability
    if $PYTHON_CMD - <<'PY'
import socket
s = socket.socket()
try:
    s.connect(("127.0.0.1", 6379))
    exit(0)
except Exception:
    exit(1)
PY
    then
        echo -e "${GREEN}[+] Redis is running.${NC}"
    else
        echo -e "${YELLOW}[!] Redis is NOT running. Attempting to start...${NC}"
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
}

# --------------------------------------------------------------------
# Port Utilities
# --------------------------------------------------------------------
port_free() {
    $PYTHON_CMD - "$1" <<'PY' 2>/dev/null
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
# Start Action
# --------------------------------------------------------------------
start_services() {
    if [ -f "$LOCKFILE" ]; then
        local lock_pid=$(cat "$LOCKFILE" 2>/dev/null || true)
        if [ ! -z "$lock_pid" ] && ps -p "$lock_pid" > /dev/null 2>&1; then
            echo -e "${RED}[!] An orchestrator process (PID $lock_pid) is already running.${NC}"
            exit 1
        fi
    fi
    echo $$ > "$LOCKFILE"

    echo -e "${BLUE}====================================================${NC}"
    echo -e "         ${GREEN}Starting Mafqood AI Services${NC}"
    echo -e "${BLUE}====================================================${NC}"

    activate_venv
    check_dependencies
    run_migrations
    collect_static
    check_start_redis

    # Detect Celery command
    CELERY_CMD=""
    if command -v celery &>/dev/null; then
        CELERY_CMD="celery"
    elif $PYTHON_CMD -c "import celery" &>/dev/null; then
        CELERY_CMD="$PYTHON_CMD -m celery"
    fi
    if [ -z "$CELERY_CMD" ]; then
        echo -e "${RED}[ERROR] Celery is not installed or available in PATH.${NC}"
        rm -f "$LOCKFILE"
        exit 1
    fi

    # Clean old instances to prevent conflicts
    echo -e "${BLUE}[*] Clearing running project instances...${NC}"
    stop_services_silent

    # 1. Start Celery Worker
    echo -e "${BLUE}[*] Starting Celery worker...${NC}"
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
        PYTHONPATH=app $CELERY_CMD -A app.celery_app worker --loglevel=info -P solo > logs/celery_worker.log 2>&1 &
        echo $! > logs/celery_worker.pid
    else
        PYTHONPATH=app $CELERY_CMD -A app.celery_app worker --loglevel=info > logs/celery_worker.log 2>&1 &
        echo $! > logs/celery_worker.pid
    fi
    echo -e "${GREEN}[+] Celery worker process started (PID $(cat logs/celery_worker.pid)).${NC}"

    # 2. Start Celery Beat
    echo -e "${BLUE}[*] Starting Celery Beat scheduler...${NC}"
    PYTHONPATH=app $CELERY_CMD -A app.celery_app beat --loglevel=info > logs/celery_beat.log 2>&1 &
    echo $! > logs/celery_beat.pid
    echo -e "${GREEN}[+] Celery Beat process started (PID $(cat logs/celery_beat.pid)).${NC}"

    # 3. Port Selection
    RUNSERVER_PORT=${DJANGO_PORT:-8001}
    if port_free "$RUNSERVER_PORT"; then
        echo -e "${GREEN}[+] Using Django port: $RUNSERVER_PORT${NC}"
    else
        echo -e "${YELLOW}[!] Port $RUNSERVER_PORT already in use. Finding a free port...${NC}"
        RUNSERVER_PORT=$(find_available_port 8001 8100)
        if [ -z "$RUNSERVER_PORT" ]; then
            echo -e "${RED}[ERROR] No free ports available in range 8001-8100.${NC}"
            rm -f "$LOCKFILE"
            exit 1
        fi
        echo -e "${GREEN}[+] Selected alternative port: $RUNSERVER_PORT${NC}"
    fi
    export NGROK_PORT="$RUNSERVER_PORT"

    # 4. Start ngrok
    echo -e "${BLUE}[*] Launching ngrok tunnel manager...${NC}"
    $PYTHON_CMD infra/ngrok_tunnel.py > logs/ngrok.log 2>&1 &
    echo $! > logs/ngrok.pid
    echo -e "${GREEN}[+] ngrok manager started (PID $(cat logs/ngrok.pid)).${NC}"

    # 5. Start Django Server (Production Gunicorn or fallback)
    echo -e "${BLUE}[*] Starting Django server...${NC}"
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
        $PYTHON_CMD app/manage.py runserver 0.0.0.0:$RUNSERVER_PORT > logs/django.log 2>&1 &
        echo $! > logs/django.pid
    elif command -v gunicorn &>/dev/null || $PYTHON_CMD -c "import gunicorn" &>/dev/null; then
        echo -e "${GREEN}[+] Gunicorn detected. Starting production server...${NC}"
        PYTHONPATH=app gunicorn \
            --bind 0.0.0.0:$RUNSERVER_PORT \
            --workers 3 \
            --timeout 120 \
            mafqood_project.wsgi:application \
            > logs/django.log 2>&1 &
        echo $! > logs/django.pid
    else
        echo -e "${YELLOW}[!] Gunicorn not available. Falling back to Django dev server...${NC}"
        $PYTHON_CMD app/manage.py runserver 0.0.0.0:$RUNSERVER_PORT > logs/django.log 2>&1 &
        echo $! > logs/django.pid
    fi
    echo -e "${GREEN}[+] Django server process started (PID $(cat logs/django.pid)).${NC}"

    # 6. Wait for ngrok public URL
    echo -e "${BLUE}[*] Fetching public endpoint url...${NC}"
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

    echo -e "${BLUE}----------------------------------------------------${NC}"
    if [ ! -z "$PUBLIC_URL" ]; then
        echo -e "${GREEN}[+] Public Webhook Target: $PUBLIC_URL${NC}"
    else
        echo -e "${YELLOW}[!] ngrok tunnel is up, but URL extraction timed out.${NC}"
        echo -e "${YELLOW}    Please check 'logs/ngrok.log' for details.${NC}"
    fi
    echo -e "${GREEN}[+] Local REST API:        http://localhost:$RUNSERVER_PORT${NC}"
    echo -e "${GREEN}[+] API Authorization Key: mafqood-ai-secure-token-2026${NC}"
    echo -e "${BLUE}----------------------------------------------------${NC}"
    echo -e "${GREEN}[+] Deployment successful. All services run in the background.${NC}"
    
    rm -f "$LOCKFILE"
}

# --------------------------------------------------------------------
# Stop Action
# --------------------------------------------------------------------
stop_services() {
    echo -e "${BLUE}====================================================${NC}"
    echo -e "         ${RED}Stopping Mafqood AI Services${NC}"
    echo -e "${BLUE}====================================================${NC}"

    # Kill Django
    if [ -f "logs/django.pid" ]; then
        local pid=$(cat logs/django.pid)
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${BLUE}[*] Stopping Django (PID $pid)...${NC}"
            kill "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null
        fi
        rm -f logs/django.pid
    fi
    pkill -f "mafqood_project.wsgi" 2>/dev/null || true
    pkill -f "manage.py runserver" 2>/dev/null || true

    # Kill Celery Worker
    if [ -f "logs/celery_worker.pid" ]; then
        local pid=$(cat logs/celery_worker.pid)
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${BLUE}[*] Stopping Celery Worker (PID $pid)...${NC}"
            kill "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null
        fi
        rm -f logs/celery_worker.pid
    fi
    pkill -f "app.celery_app worker" 2>/dev/null || true

    # Kill Celery Beat
    if [ -f "logs/celery_beat.pid" ]; then
        local pid=$(cat logs/celery_beat.pid)
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${BLUE}[*] Stopping Celery Beat (PID $pid)...${NC}"
            kill "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null
        fi
        rm -f logs/celery_beat.pid
    fi
    pkill -f "app.celery_app beat" 2>/dev/null || true

    # Kill ngrok
    if [ -f "logs/ngrok.pid" ]; then
        local pid=$(cat logs/ngrok.pid)
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${BLUE}[*] Stopping ngrok tunnel (PID $pid)...${NC}"
            kill "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null
        fi
        rm -f logs/ngrok.pid
    fi
    pkill -f "infra/ngrok_tunnel.py" 2>/dev/null || true

    rm -f "$LOCKFILE"
    echo -e "${GREEN}[+] All services stopped successfully.${NC}"
}

stop_services_silent() {
    if [ -f "logs/django.pid" ]; then
        local pid=$(cat logs/django.pid)
        kill "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null
        rm -f logs/django.pid
    fi
    pkill -f "mafqood_project.wsgi" 2>/dev/null || true
    pkill -f "manage.py runserver" 2>/dev/null || true

    if [ -f "logs/celery_worker.pid" ]; then
        local pid=$(cat logs/celery_worker.pid)
        kill "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null
        rm -f logs/celery_worker.pid
    fi
    pkill -f "app.celery_app worker" 2>/dev/null || true

    if [ -f "logs/celery_beat.pid" ]; then
        local pid=$(cat logs/celery_beat.pid)
        kill "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null
        rm -f logs/celery_beat.pid
    fi
    pkill -f "app.celery_app beat" 2>/dev/null || true

    if [ -f "logs/ngrok.pid" ]; then
        local pid=$(cat logs/ngrok.pid)
        kill "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null
        rm -f logs/ngrok.pid
    fi
    pkill -f "infra/ngrok_tunnel.py" 2>/dev/null || true
}

# --------------------------------------------------------------------
# Status Checker
# --------------------------------------------------------------------
check_status() {
    activate_venv
    
    echo -e "${BLUE}====================================================${NC}"
    echo -e "         ${GREEN}Mafqood AI Subsystems Status Check${NC}"
    echo -e "${BLUE}====================================================${NC}"

    # 1. Redis
    if $PYTHON_CMD - <<'PY'
import socket
s = socket.socket()
try:
    s.connect(("127.0.0.1", 6379))
    exit(0)
except Exception:
    exit(1)
PY
    then
        echo -e "Redis Message Broker: \t ${GREEN}[RUNNING]${NC} (Port 6379)"
    else
        echo -e "Redis Message Broker: \t ${RED}[STOPPED]${NC} (Port 6379)"
    fi

    # 2. Django Server
    local django_status="${RED}[STOPPED]${NC}"
    if [ -f "logs/django.pid" ]; then
        local pid=$(cat logs/django.pid)
        if ps -p "$pid" > /dev/null 2>&1; then
            django_status="${GREEN}[RUNNING]${NC} (PID: $pid)"
        fi
    fi
    echo -e "Django Web Server:    \t $django_status"

    # 3. Celery Worker
    local worker_status="${RED}[STOPPED]${NC}"
    if [ -f "logs/celery_worker.pid" ]; then
        local pid=$(cat logs/celery_worker.pid)
        if ps -p "$pid" > /dev/null 2>&1; then
            worker_status="${GREEN}[RUNNING]${NC} (PID: $pid)"
        fi
    fi
    echo -e "Celery Task Worker:   \t $worker_status"

    # 4. Celery Beat
    local beat_status="${RED}[STOPPED]${NC}"
    if [ -f "logs/celery_beat.pid" ]; then
        local pid=$(cat logs/celery_beat.pid)
        if ps -p "$pid" > /dev/null 2>&1; then
            beat_status="${GREEN}[RUNNING]${NC} (PID: $pid)"
        fi
    fi
    echo -e "Celery Beat Scheduler:\t $beat_status"

    # 5. ngrok Tunnel
    local ngrok_status="${RED}[STOPPED]${NC}"
    if [ -f "logs/ngrok.pid" ]; then
        local pid=$(cat logs/ngrok.pid)
        if ps -p "$pid" > /dev/null 2>&1; then
            local url=""
            if [ -f "logs/ngrok.log" ]; then
                url=$(grep -o -E "https://[a-zA-Z0-9.-]+\.ngrok-free\.app" logs/ngrok.log | head -n 1 || true)
            fi
            if [ ! -z "$url" ]; then
                ngrok_status="${GREEN}[RUNNING]${NC} (PID: $pid, URL: $url)"
            else
                ngrok_status="${GREEN}[RUNNING]${NC} (PID: $pid, URL: detecting...)"
            fi
        fi
    fi
    echo -e "ngrok Tunnel:         \t $ngrok_status"
    echo -e "${BLUE}====================================================${NC}"
}

# --------------------------------------------------------------------
# Log Tailing Helper
# --------------------------------------------------------------------
show_logs() {
    local service=$1
    if [ -z "$service" ]; then
        echo -e "${YELLOW}Please specify a service to inspect. Choose from: django, celery, beat, ngrok, all${NC}"
        echo "Example: $0 logs django"
        exit 1
    fi

    case "$service" in
        django)
            echo -e "${GREEN}=== Tailing Django Logs (logs/django.log) ===${NC}"
            tail -n 50 -f logs/django.log
            ;;
        celery)
            echo -e "${GREEN}=== Tailing Celery Worker Logs (logs/celery_worker.log) ===${NC}"
            tail -n 50 -f logs/celery_worker.log
            ;;
        beat)
            echo -e "${GREEN}=== Tailing Celery Beat Logs (logs/celery_beat.log) ===${NC}"
            tail -n 50 -f logs/celery_beat.log
            ;;
        ngrok)
            echo -e "${GREEN}=== Tailing ngrok Logs (logs/ngrok.log) ===${NC}"
            tail -n 50 -f logs/ngrok.log
            ;;
        all)
            echo -e "${GREEN}=== Tailing All Logs (logs/*) ===${NC}"
            tail -n 20 -f logs/django.log logs/celery_worker.log logs/celery_beat.log logs/ngrok.log
            ;;
        *)
            echo -e "${RED}[ERROR] Invalid log target: '$service'. Choose from: django, celery, beat, ngrok, all${NC}"
            exit 1
            ;;
    esac
}

# --------------------------------------------------------------------
# Restart Action
# --------------------------------------------------------------------
restart_services() {
    stop_services
    sleep 2
    start_services
}

# --------------------------------------------------------------------
# Main CLI Router
# --------------------------------------------------------------------
ACTION=${1:-"start"}

case "$ACTION" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    status)
        check_status
        ;;
    logs)
        show_logs "$2"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}Invalid command: '$ACTION'${NC}"
        show_help
        exit 1
        ;;
esac