.PHONY: help build up down logs test clean restart health scale-workers

help:
	@echo "╔════════════════════════════════════════════════════════╗"
	@echo "║     Mafqood AI System - Docker Commands               ║"
	@echo "╚════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Available commands:"
	@echo ""
	@echo "  make help              - Show this help message"
	@echo "  make build             - Build Docker images"
	@echo "  make up                - Start all services"
	@echo "  make down              - Stop all services"
	@echo "  make restart           - Restart all services"
	@echo "  make logs              - View logs from all services"
	@echo "  make logs-app          - View app logs"
	@echo "  make logs-worker       - View worker logs"
	@echo "  make logs-redis        - View Redis logs"
	@echo "  make test              - Run test suite"
	@echo "  make test-coverage     - Run tests with coverage report"
	@echo "  make test-utils        - Test utils functions only"
	@echo "  make test-pipeline     - Test CV pipeline only"
	@echo "  make test-endpoints    - Test API endpoints only"
	@echo "  make test-workflow     - Test complete workflow only"
	@echo "  make health            - Check service health"
	@echo "  make status            - Show service status"
	@echo "  make scale-workers     - Scale workers (e.g., make scale-workers NUM=3)"
	@echo "  make shell-app         - Open shell in app container"
	@echo "  make shell-worker      - Open shell in worker container"
	@echo "  make redis-cli         - Access Redis CLI"
	@echo "  make clean             - Remove stopped containers"
	@echo "  make reset             - Full reset (WARNING: deletes data)"
	@echo "  make fast-start        - Quick start all services"
	@echo ""

build:
	@echo "Building Docker images..."
	docker-compose build

up:
	@echo "Starting all services..."
	docker-compose up -d
	@sleep 5
	@make health

down:
	@echo "Stopping all services..."
	docker-compose down

restart: down up
	@echo "Services restarted"

logs:
	docker-compose logs -f

logs-app:
	docker-compose logs -f app

logs-worker:
	docker-compose logs -f worker

logs-redis:
	docker-compose logs -f redis

test:
	@echo "Running test suite..."
	docker-compose exec app pytest tests/test_workflow_integration.py -v --tb=short

test-coverage:
	@echo "Running tests with coverage..."
	docker-compose exec app pytest tests/ --cov=app --cov-report=html --cov-report=term-missing
	@echo "Coverage report generated in htmlcov/"

test-utils:
	@echo "Testing utils functions..."
	docker-compose exec app pytest tests/test_workflow_integration.py::TestUtilsFunctions -v

test-pipeline:
	@echo "Testing CV pipeline..."
	docker-compose exec app pytest tests/test_workflow_integration.py::TestCVPipeline -v

test-endpoints:
	@echo "Testing API endpoints..."
	docker-compose exec app pytest tests/test_workflow_integration.py::TestCVEndpoints -v

test-workflow:
	@echo "Testing complete workflow..."
	docker-compose exec app pytest tests/test_workflow_integration.py::TestWorkflowIntegration -v

health:
	@echo "Checking service health..."
	@curl -s http://localhost:8000/cv/health | python3 -m json.tool || echo "API not responding"
	@echo ""
	@echo "Services:"
	@echo "  API Documentation: http://localhost:8000/docs"
	@echo "  API Redoc:        http://localhost:8000/redoc"
	@echo "  Celery Flower:    http://localhost:5555"

status:
	@echo "Service Status:"
	docker-compose ps
	@echo ""
	@make health

scale-workers:
	@if [ -z "$(NUM)" ]; then \
		echo "Usage: make scale-workers NUM=<number>"; \
	else \
		echo "Scaling workers to $(NUM)..."; \
		docker-compose up -d --scale worker=$(NUM); \
	fi

shell-app:
	docker-compose exec app bash

shell-worker:
	docker-compose exec worker bash

redis-cli:
	docker-compose exec redis redis-cli

clean:
	@echo "Cleaning up stopped containers..."
	docker-compose down
	docker system prune -f
	@echo "Cleanup complete"

reset:
	@echo "WARNING: This will delete all data!"
	@read -p "Are you sure? (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		docker-compose down -v; \
		docker system prune -af; \
		rm -rf ./chroma_db/*; \
		rm -rf ./temp_uploads/*; \
		echo "Full reset complete"; \
	else \
		echo "Reset cancelled"; \
	fi

fast-start: build up
	@echo ""
	@echo "╔════════════════════════════════════════════════════════╗"
	@echo "║            System Started Successfully!                ║"
	@echo "╚════════════════════════════════════════════════════════╝"
	@echo ""
	@make health

.DEFAULT_GOAL := help
