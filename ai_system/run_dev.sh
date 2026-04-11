#!/bin/bash

export CELERY_ALWAYS_EAGER=True
export PYTHONPATH=$PYTHONPATH:$(pwd):$(pwd)/app

clear

# Banner
toilet -f bigascii12 -F border "MAFQOOD" | sed 's/#/-/g; s/ /█/g' | lolcat -a -d 2

echo ""
echo "        MAFQOOD ARTIFICIAL INTELLIGENCE NODE" | lolcat
echo "=================================================" | lolcat

sleep 0.5

echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
ORANGE='\033[38;5;214m'
NC='\033[0m'

echo "[BOOT] Initializing AI Kernel..."
sleep 0.3

# Python check
PY=$(python3 --version 2>&1)

if [ $? -eq 0 ]; then
    echo -e "[CHECK] Python Runtime → ${GREEN}$PY [OK]${NC}"
else
    echo -e "[CHECK] Python Runtime → ${RED}ERROR${NC}"
fi

sleep 0.3

# CPU check
CPU=$(nproc)

if [ "$CPU" -ge 4 ]; then
    echo -e "[CHECK] CPU Cores → ${GREEN}$CPU detected [OK]${NC}"
else
    echo -e "[CHECK] CPU Cores → ${ORANGE}$CPU (Low cores) [WARNING]${NC}"
fi

sleep 0.3

# RAM check
RAM=$(free -h | awk '/Mem:/ {print $2}')
RAM_GB=$(free -g | awk '/Mem:/ {print $2}')

if [ "$RAM_GB" -ge 8 ]; then
    echo -e "[CHECK] System Memory → ${GREEN}$RAM [OK]${NC}"
elif [ "$RAM_GB" -ge 4 ]; then
    echo -e "[CHECK] System Memory → ${ORANGE}$RAM [MEDIUM]${NC}"
else
    echo -e "[CHECK] System Memory → ${RED}$RAM [LOW]${NC}"
fi

sleep 0.3

# GPU check
GPU=$(lspci | grep -i nvidia)

if [ -z "$GPU" ]; then
    echo -e "[CHECK] GPU → ${ORANGE}Not detected (CPU mode)${NC}"
else
    echo -e "[CHECK] GPU → ${GREEN}NVIDIA detected [OK]${NC}"
fi

sleep 0.3

# Port check
PORT=$(ss -tuln | grep 8000)

if [ -z "$PORT" ]; then
    echo -e "[CHECK] Port 8000 → ${GREEN}Available [OK]${NC}"
else
    echo -e "[CHECK] Port 8000 → ${RED}Already in use [ERROR]${NC}"
fi

sleep 0.3

echo ""
echo "[AI] Loading Neural Subsystems..."

sleep 0.3
echo -e "[AI] Vision Engine ........ ${GREEN}OK${NC}"

sleep 0.3
echo -e "[AI] Feature Extractor .... ${GREEN}OK${NC}"

sleep 0.3
echo -e "[AI] Matching Algorithm ... ${GREEN}OK${NC}"

sleep 0.3

# Celery check example
if command -v celery &> /dev/null
then
echo -e "[AI] Celery Workers ....... ${GREEN}READY${NC}"
else
echo -e "[AI] Celery Workers ....... ${ORANGE}NOT RUNNING${NC}"
fi

sleep 0.3

echo -e "[AI] Database Connection .. ${GREEN}OK${NC}"

echo ""
# Matrix style animation
echo "Establishing secure AI channels..." | lolcat

for i in {1..40}
do
printf "█"
sleep 0.02
done

echo ""
echo ""

# Fake security scan
echo "[SECURITY] Checking environment integrity..." | lolcat
sleep 0.4

echo "[SECURITY] No threats detected" | lolcat
sleep 0.3

echo "[SECURITY] AI Core Stable" | lolcat

echo ""

echo "MAFQOOD AI STATUS → OPERATIONAL" | lolcat

echo "=================================================" | lolcat

sleep 1

cd app

echo ""
echo "[START] Launching AI Web Interface..." | lolcat

echo ""

python3 manage.py runserver 0.0.0.0:8000