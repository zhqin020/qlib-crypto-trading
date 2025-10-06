# 🚀 Deployment Guide

Complete guide for deploying the Qlib Crypto Trading Platform in production.

## Table of Contents

1. [Local Development](#local-development)
2. [Docker Deployment](#docker-deployment)
3. [Cloud Deployment](#cloud-deployment)
4. [MCP Server Setup](#mcp-server-setup)
5. [Security](#security)
6. [Monitoring](#monitoring)
7. [Scaling](#scaling)

## Local Development

### Prerequisites

- Python 3.8+
- 4GB RAM minimum (8GB recommended)
- 10GB disk space

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Validate setup
python scripts/validate_setup.py

# Create directories
make setup

# Run tests
make test
```

### Running Services

```bash
# API server
make api

# MCP server
make mcp
```

## Docker Deployment

### Quick Start

```bash
# Build and start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

### Services

- **API Server**: Port 5100
- **PostgreSQL**: Port 5110
- **Redis**: Port 5120
- **MCP Server**: stdio interface

### Persistent Data

Volumes are mounted for:
- `./data` → `/app/data`
- `./models` → `/app/models`
- `./logs` → `/app/logs`

### Environment Variables

Create `.env` from `.env.example`:

```bash
cp .env.example .env
# Edit .env with your configuration
```

## Cloud Deployment

### AWS Deployment

#### EC2 Instance

```bash
# Launch EC2 instance (t3.medium or larger)
# Install Docker
sudo yum update -y
sudo yum install docker -y
sudo service docker start
sudo usermod -a -G docker ec2-user

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Clone and deploy
git clone <your-repo>
cd qlib-2
docker-compose up -d
```

#### Security Groups

Open ports:
- 5100 (API)
- 22 (SSH)

#### RDS for PostgreSQL (Optional)

```bash
# Update docker-compose.yml
environment:
  DATABASE_URL: postgresql://user:pass@your-rds-endpoint:5110/qlib_crypto
```

### Google Cloud Platform

```bash
# Create Compute Engine instance
gcloud compute instances create qlib-crypto \
  --machine-type=n1-standard-2 \
  --image-family=ubuntu-2004-lts \
  --image-project=ubuntu-os-cloud

# SSH and deploy
gcloud compute ssh qlib-crypto
# Follow EC2 deployment steps
```

### Azure

```bash
# Create VM
az vm create \
  --resource-group qlib-rg \
  --name qlib-vm \
  --image UbuntuLTS \
  --size Standard_D2s_v3

# Deploy
az vm run-command invoke \
  --resource-group qlib-rg \
  --name qlib-vm \
  --command-id RunShellScript \
  --scripts @deploy.sh
```

## MCP Server Setup

### Claude Desktop Integration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "qlib-trading": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/absolute/path/to/qlib-2",
      "env": {
        "PYTHONPATH": "/absolute/path/to/qlib-2/src"
      }
    }
  }
}
```

### Testing MCP Server

```bash
# Start server
./scripts/start_mcp_server.sh

# Test with MCP inspector
npx @modelcontextprotocol/inspector python -m src.mcp_server
```

## Security

### API Authentication

Add JWT authentication to `src/ui/api_enhanced.py`:

```python
from fastapi.security import HTTPBearer
from jose import jwt

security = HTTPBearer()

@app.get("/api/protected")
async def protected_route(token: str = Depends(security)):
    # Verify JWT token
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    return {"user": payload["sub"]}
```

### Exchange API Keys

Store in environment variables, never in code:

```bash
# .env
BINANCE_API_KEY=your_key_here
BINANCE_API_SECRET=your_secret_here
```

Load in code:

```python
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")
```

### HTTPS/TLS

Use nginx as reverse proxy:

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:5100;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Monitoring

### Prometheus Metrics

Add to `src/ui/api_enhanced.py`:

```python
from prometheus_client import Counter, Histogram, generate_latest

request_count = Counter('requests_total', 'Total requests')
request_duration = Histogram('request_duration_seconds', 'Request duration')

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

### Logging

Configure structured logging:

```python
import logging
from pythonjsonlogger import jsonlogger

logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger = logging.getLogger()
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)
```

### Health Checks

```bash
# API health
curl http://localhost:5100/api/health

# Docker health check
docker-compose ps
```

## Scaling

### Horizontal Scaling

Use multiple API instances behind load balancer:

```yaml
# docker-compose.yml
services:
  api:
    deploy:
      replicas: 3
    
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
```

### Database Optimization

```sql
-- Add indexes for common queries
CREATE INDEX idx_predictions_date ON predictions(prediction_date);
CREATE INDEX idx_models_status ON models(status);
```

### Caching

Use Redis for caching:

```python
import redis

cache = redis.Redis(host='redis', port=5120)

@app.get("/api/quote/{symbol}")
async def get_quote(symbol: str):
    # Check cache
    cached = cache.get(f"quote:{symbol}")
    if cached:
        return json.loads(cached)
    
    # Fetch and cache
    quote = await fetch_quote(symbol)
    cache.setex(f"quote:{symbol}", 60, json.dumps(quote))
    return quote
```

### Async Workers

Use Celery for background tasks:

```python
from celery import Celery

celery_app = Celery('qlib_crypto', broker='redis://redis:5120')

@celery_app.task
def train_model_async(dataset, handler):
    # Long-running training task
    return train_model(dataset, handler)
```

## Backup & Recovery

### Database Backups

```bash
# Backup PostgreSQL
docker-compose exec postgres pg_dump -U qlib qlib_crypto > backup.sql

# Restore
docker-compose exec -T postgres psql -U qlib qlib_crypto < backup.sql
```

### Model Backups

```bash
# Backup models and data
tar -czf backup_$(date +%Y%m%d).tar.gz \
  models/trained \
  data/qlib \
  config

# Upload to S3
aws s3 cp backup_$(date +%Y%m%d).tar.gz s3://your-bucket/backups/
```

## Troubleshooting

### Common Issues

**API won't start:**
```bash
# Check logs
docker-compose logs api

# Verify dependencies
python scripts/validate_setup.py
```

**Out of memory:**
```bash
# Increase Docker memory limit
# Docker Desktop → Settings → Resources → Memory
```

**Model training fails:**
```bash
# Check available RAM
free -h

# Reduce batch size in model config
```

### Debug Mode

```bash
# Start API in debug mode
uvicorn src.ui.api_enhanced:app --reload --log-level debug
```

## Performance Tuning

### API Optimization

```python
# Enable gzip compression
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Connection pooling
from sqlalchemy.pool import QueuePool
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=40
)
```

### Qlib Optimization

```python
# Use binary cache
import qlib
qlib.init(
    provider_uri="data/qlib",
    mount_path="/tmp/qlib_cache",
    auto_mount=True
)
```

## Maintenance

### Regular Tasks

```bash
# Update dependencies
pip install -r requirements.txt --upgrade

# Clean old predictions
find predictions -name "*.json" -mtime +30 -delete

# Vacuum database
docker-compose exec postgres vacuumdb -U qlib qlib_crypto
```

### Monitoring Checklist

- [ ] API response times < 200ms
- [ ] Model training completes successfully
- [ ] Disk usage < 80%
- [ ] Memory usage < 80%
- [ ] No error spikes in logs
- [ ] Data pipeline running daily

---

For more information, see [README.md](README.md) and [QUICKSTART.md](QUICKSTART.md).
