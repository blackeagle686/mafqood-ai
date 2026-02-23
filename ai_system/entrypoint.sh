#!/bin/bash
# Docker entrypoint script for managing different service startup modes

set -e

echo "==================================="
echo "Mafqood AI System - Docker Startup"
echo "==================================="

# Function to check Redis connection
check_redis() {
    echo "Checking Redis connection..."
    redis-cli -h redis -p 6379 ping > /dev/null 2>&1 || {
        echo "⚠️  Warning: Could not connect to Redis"
        return 1
    }
    echo "✓ Redis is running"
    return 0
}

# Function to start FastAPI server
start_api() {
    echo "Starting FastAPI server..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
}

# Function to start Celery worker
start_worker() {
    echo "Waiting for Redis..."
    sleep 5
    check_redis
    echo "Starting Celery worker..."
    exec celery -A app.celery_app worker --loglevel=info --autoscale=10,3 --time-limit=3600
}

# Function to start Celery beat
start_beat() {
    echo "Waiting for Redis..."
    sleep 5
    check_redis
    echo "Starting Celery beat..."
    exec celery -A app.celery_app beat --loglevel=info
}

# Function to run tests
run_tests() {
    echo "Running test suite..."
    pytest tests/ -v --tb=short
}

# Main logic - check command line argument
SERVICE=${1:-api}

case $SERVICE in
    api)
        check_redis
        start_api
        ;;
    worker)
        start_worker
        ;;
    beat)
        start_beat
        ;;
    test)
        run_tests
        ;;
    *)
        echo "Unknown service: $SERVICE"
        echo "Available services: api, worker, beat, test"
        exit 1
        ;;
esac
