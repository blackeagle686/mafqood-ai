# Docker Setup and Deployment Guide

This guide covers setting up and running the Mafqood AI System using Docker and Docker Compose.

## Prerequisites

- Docker >= 20.10
- Docker Compose >= 1.29
- At least 4GB RAM allocated to Docker
- Free disk space for ChromaDB and temporary uploads

## Quick Start

### 1. Build Images

```bash
docker-compose build
```

This will:
- Build the main application image with all dependencies
- Install Python requirements from requirements.txt
- Install system dependencies (OpenCV, face libraries)
- Create necessary directories for data persistence

### 2. Start All Services

```bash
docker-compose up -d
```

This will start:
- **Redis** (port 6379): Message broker for Celery
- **FastAPI App** (port 8000): Main API server
- **Celery Worker**: Background task processor
- **Celery Beat** (optional): Scheduled task runner
- **Flower** (port 5555): Celery monitoring dashboard

### 3. Verify Services

Check that all services are running:

```bash
docker-compose ps
```

Check API health:

```bash
curl http://localhost:8000/cv/health
```

Expected response:
```json
{"status": "healthy", "service": "cv_pipeline"}
```

## Service Details

### FastAPI Application (Port 8000)

Main API server with the following endpoints:
- `POST /cv/process` - Process image with face detection
- `POST /cv/search` - Search for similar faces
- `POST /cv/process_video` - Process video files
- `GET /cv/health` - Health check
- `GET /cv/database/info` - Database statistics
- `DELETE /cv/faces` - Delete faces from database

**View logs:**
```bash
docker-compose logs -f app
```

### Celery Worker

Processes background tasks like image processing and face searches.

**View logs:**
```bash
docker-compose logs -f worker
```

**Scale workers:**
```bash
docker-compose up -d --scale worker=3
```

### Redis (Port 6379)

Message broker and result backend for Celery.
- Default password: `mafqood_redis_password`

**Access Redis CLI:**
```bash
docker exec -it mafqood_redis redis-cli
```

### Flower Monitoring (Port 5555)

Real-time Celery monitoring dashboard.

Access at: http://localhost:5555

## Testing

### Run Tests

```bash
# Using docker-compose
docker-compose -f docker-compose.test.yml up --abort-on-container-exit

# Or directly in the running container
docker-compose exec app pytest tests/ -v
```

### Run Specific Tests

```bash
# Test utils functions
docker-compose exec app pytest tests/test_workflow_integration.py::TestUtilsFunctions -v

# Test CV pipeline
docker-compose exec app pytest tests/test_workflow_integration.py::TestCVPipeline -v

# Test endpoints
docker-compose exec app pytest tests/test_workflow_integration.py::TestCVEndpoints -v

# Test complete workflow
docker-compose exec app pytest tests/test_workflow_integration.py::TestWorkflowIntegration -v
```

## Development Workflow

### 1. Code Changes Auto-Reload

The FastAPI container has auto-reload enabled. Changes to Python files will automatically reload:

```bash
# Watch logs for changes
docker-compose logs -f app
```

### 2. Debugging

Access Python shell in running container:

```bash
docker-compose exec app python
```

### 3. View Application Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f app
docker-compose logs -f worker
```

## Production Deployment

### Update docker-compose.yml for Production

```yaml
# app service changes:
command: uvicorn app.main:app --host 0.0.0.0 --port 8000  # Remove --reload
environment:
  - REDIS_URL=redis://:YOUR_SECURE_PASSWORD@redis:6379/0  # Change password

# worker service changes:
restart: always  # from unless-stopped
```

### Generate Strong Redis Password

```bash
openssl rand -base64 32
```

### Enable SSL/TLS

Use a reverse proxy like Nginx or Traefik:

```bash
# Example with Nginx (add to docker-compose.yml)
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
```

### Resource Limits

Add to docker-compose.yml for each service:

```yaml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

## Troubleshooting

### Services Won't Start

1. Check Docker logs:
```bash
docker-compose logs app
```

2. Ensure Redis is healthy:
```bash
docker-compose ps
```

3. Rebuild images:
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Out of Memory

Increase Docker memory limit:
- Docker Desktop: Preferences → Resources → Memory (increase to 8GB+)
- Docker on Linux: Check system memory

### Redis Connection Failed

```bash
# Check Redis container
docker-compose logs redis

# Test connection
docker-compose exec app redis-cli -h redis ping
```

### Celery Workers Not Processing Tasks

1. Check worker is running:
```bash
docker-compose logs worker
```

2. Check Redis connection:
```bash
docker-compose exec worker celery -A app.celery_app inspect active
```

3. Restart workers:
```bash
docker-compose restart worker
```

## Cleanup

### Stop All Services

```bash
docker-compose down
```

### Remove Volumes (WARNING: Deletes data)

```bash
docker-compose down -v
```

### Remove Images

```bash
docker-compose down --rmi all
```

### Clean Everything

```bash
docker system prune -a
```

## Environment Variables

Key environment variables used in Docker:

| Variable | Default | Description |
|----------|---------|-------------|
| REDIS_URL | redis://redis:6379/0 | Redis connection URL |
| CHROMA_DB_PATH | /app/chroma_db | ChromaDB data directory |
| CV_CTX_ID | -1 | CPU (-1) or GPU (0+) context |
| PYTHONUNBUFFERED | 1 | Direct logging output |

## Performance Tips

1. **Enable GPU Support**: Set `CV_CTX_ID=0` in environment
2. **Scale Workers**: Adjust `--autoscale=10,3` worker parameter
3. **Redis Persistence**: Already enabled with appendonly=yes
4. **Monitor with Flower**: Access dashboard at http://localhost:5555
5. **Use Named Volumes**: Ensures data persistence across restarts

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Celery Documentation](https://docs.celeryproject.io/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [ChromaDB Documentation](https://docs.trychroma.com/)

## Support

For issues or questions:
1. Check Docker logs: `docker-compose logs app`
2. Review test output: `docker-compose exec app pytest tests/ -v`
3. Monitor Celery: http://localhost:5555 (Flower dashboard)
