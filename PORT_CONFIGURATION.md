# 🔌 Port Configuration Guide

## Port Mapping

The Qlib Crypto Trading Platform uses the following ports:

| Service | Port | Protocol | Description |
|---------|------|----------|-------------|
| **Web UI / API** | **5100** | HTTP/WebSocket | Main dashboard and REST API |
| **PostgreSQL** | **5110** | TCP | Database for metadata storage |
| **Redis** | **5120** | TCP | Cache and pub/sub |

## Service URLs

### Web Interface
- **Dashboard**: http://localhost:5100
- **API Documentation**: http://localhost:5100/docs
- **OpenAPI Spec**: http://localhost:5100/openapi.json

### WebSocket
- **Live Events**: ws://localhost:5100/ws/events
- **Market Data**: ws://localhost:5100/ws/market-data

### Database Connections
- **PostgreSQL**: `postgresql://qlib:qlib_password@localhost:5110/qlib_crypto`
- **Redis**: `redis://localhost:5120/0`

## Quick Access

```bash
# Open dashboard in browser
open http://localhost:5100

# Test API health
curl http://localhost:5100/api/health

# View API documentation
open http://localhost:5100/docs
```

## Docker Port Mapping

When running with Docker Compose:
- Container port `5100` → Host port `5100` (API)
- Container port `5432` → Host port `5110` (PostgreSQL)
- Container port `6379` → Host port `5120` (Redis)

## Firewall Configuration

If running on a server, ensure these ports are accessible:

```bash
# Allow API/Web UI
sudo ufw allow 5100/tcp

# Allow PostgreSQL (if accessing externally)
sudo ufw allow 5110/tcp

# Allow Redis (if accessing externally)
sudo ufw allow 5120/tcp
```

## Environment Variables

Configure ports in `.env`:

```bash
# API
API_PORT=5100

# Database
DATABASE_URL=postgresql://qlib:qlib_password@localhost:5110/qlib_crypto

# Redis
REDIS_URL=redis://localhost:5120/0
```

## Troubleshooting

### Port Already in Use

If you see "Address already in use" errors:

```bash
# Check what's using port 5100
lsof -i :5100

# Kill the process
kill -9 <PID>

# Or use a different port
python -m uvicorn src.ui.api_enhanced:app --port 5101
```

### Cannot Connect to Services

```bash
# Verify services are running
docker-compose ps

# Check logs
docker-compose logs api
docker-compose logs postgres
docker-compose logs redis

# Restart services
docker-compose restart
```

## Production Deployment

For production, consider:
- Using HTTPS (port 443) with reverse proxy
- Restricting database/Redis ports to internal network
- Using environment-specific ports
- Implementing rate limiting

### Nginx Reverse Proxy Example

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:5100;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Summary

**Remember**: All services now run on ports in the **5100 series**:
- 🌐 Web/API: **5100**
- 🗄️ PostgreSQL: **5110**  
- 💾 Redis: **5120**

This avoids conflicts with common development ports (3000, 8000, 8080, etc.).
