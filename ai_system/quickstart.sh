#!/bin/bash
# Quick start script for Mafqood AI System

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Mafqood AI System - Docker Quick Start             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker found: $(docker --version)${NC}"

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}✗ Docker Compose is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker Compose found: $(docker-compose --version)${NC}"

# Main menu
show_menu() {
    echo -e "\n${BLUE}Select operation:${NC}"
    echo -e "  ${YELLOW}1${NC} - Start all services"
    echo -e "  ${YELLOW}2${NC} - Stop all services"
    echo -e "  ${YELLOW}3${NC} - View logs"
    echo -e "  ${YELLOW}4${NC} - Run tests"
    echo -e "  ${YELLOW}5${NC} - Run tests with coverage"
    echo -e "  ${YELLOW}6${NC} - Scale workers (set number)"
    echo -e "  ${YELLOW}7${NC} - Check service status"
    echo -e "  ${YELLOW}8${NC} - Clean up (remove stopped containers)"
    echo -e "  ${YELLOW}9${NC} - Full reset (WARNING: deletes data)"
    echo -e "  ${YELLOW}0${NC} - Exit"
    read -p "Enter choice [0-9]: " choice
}

# Service management functions
start_services() {
    echo -e "\n${BLUE}Building images...${NC}"
    docker-compose build
    
    echo -e "\n${BLUE}Starting services...${NC}"
    docker-compose up -d
    
    echo -e "\n${GREEN}✓ Services started${NC}"
    sleep 5
    
    echo -e "\n${BLUE}Waiting for services to be ready...${NC}"
    sleep 5
    
    check_health
}

stop_services() {
    echo -e "\n${BLUE}Stopping services...${NC}"
    docker-compose down
    echo -e "${GREEN}✓ Services stopped${NC}"
}

view_logs() {
    read -p "Enter service name (app/worker/redis/flower) or 'all': " service
    
    if [ "$service" == "all" ]; then
        docker-compose logs -f
    else
        docker-compose logs -f "$service"
    fi
}

run_tests() {
    echo -e "\n${BLUE}Running test suite...${NC}"
    docker-compose exec app pytest tests/test_workflow_integration.py -v --tb=short
}

run_tests_coverage() {
    echo -e "\n${BLUE}Running tests with coverage...${NC}"
    docker-compose exec app pytest tests/ --cov=app --cov-report=html --cov-report=term-missing
    echo -e "\n${GREEN}✓ Coverage report generated in htmlcov/${NC}"
}

scale_workers() {
    read -p "Enter number of workers (1-10): " num_workers
    
    if [[ ! "$num_workers" =~ ^[0-9]+$ ]] || [ "$num_workers" -lt 1 ] || [ "$num_workers" -gt 10 ]; then
        echo -e "${RED}✗ Invalid number${NC}"
        return
    fi
    
    echo -e "\n${BLUE}Scaling workers to $num_workers...${NC}"
    docker-compose up -d --scale worker=$num_workers
    echo -e "${GREEN}✓ Workers scaled${NC}"
}

check_status() {
    echo -e "\n${BLUE}Service Status:${NC}"
    docker-compose ps
    
    echo -e "\n${BLUE}Service Health:${NC}"
    check_health
}

check_health() {
    echo -e "\nChecking API health..."
    if curl -s http://localhost:8000/cv/health > /dev/null; then
        echo -e "${GREEN}✓ API is healthy${NC}"
    else
        echo -e "${RED}✗ API is not responding${NC}"
    fi
    
    echo -e "\nAvailable endpoints:"
    echo "  API:    http://localhost:8000"
    echo "  Docs:   http://localhost:8000/docs"
    echo "  Flower: http://localhost:5555"
    echo "  Redis:  localhost:6379"
}

cleanup() {
    echo -e "\n${BLUE}Cleaning up stopped containers...${NC}"
    docker-compose down --volumes
    docker system prune -f
    echo -e "${GREEN}✓ Cleanup complete${NC}"
}

reset_all() {
    echo -e "${RED}WARNING: This will delete all data including ChromaDB!${NC}"
    read -p "Are you sure? (yes/no): " confirm
    
    if [ "$confirm" == "yes" ]; then
        echo -e "\n${BLUE}Performing full reset...${NC}"
        docker-compose down -v
        docker system prune -af
        rm -rf ./chroma_db/*
        rm -rf ./temp_uploads/*
        echo -e "${GREEN}✓ Full reset complete${NC}"
    else
        echo -e "${YELLOW}Reset cancelled${NC}"
    fi
}

# Main loop
while true; do
    show_menu
    
    case $choice in
        1) start_services ;;
        2) stop_services ;;
        3) view_logs ;;
        4) run_tests ;;
        5) run_tests_coverage ;;
        6) scale_workers ;;
        7) check_status ;;
        8) cleanup ;;
        9) reset_all ;;
        0) 
            echo -e "\n${GREEN}Goodbye!${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}✗ Invalid choice${NC}"
            ;;
    esac
done
