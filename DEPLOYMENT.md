# Production Deployment Guide

This guide covers deploying the Profit Sharing API to production using Docker.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- At least 4GB RAM available
- 20GB disk space

## Quick Start

### 1. Configure Environment Variables

Copy the production environment template and configure it:

```bash
cp .env.production .env
```

Edit `.env` and update the following **REQUIRED** values:

```bash
# MongoDB Root Credentials
MONGO_ROOT_PASSWORD=<generate-strong-password>

# JWT Secrets (use at least 32 characters)
JWT_SECRET=<generate-strong-secret>
JWT_REFRESH_SECRET=<generate-strong-secret>
```

**Generate secure secrets:**
```bash
# On Linux/Mac
openssl rand -hex 32

# On Windows (PowerShell)
[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Minimum 0 -Maximum 256 }))
```

### 2. Prepare ML Models

Ensure your trained models are in place:

```
models/
├── classifier/
│   └── best.pt
├── detector/
│   └── best.pt
├── weight/
│   └── weight_model.joblib
└── price/
    └── price_model.joblib
```

### 3. Build and Deploy

```bash
# Build the Docker image
docker-compose -f docker-compose.prod.yml build

# Start all services
docker-compose -f docker-compose.prod.yml up -d

# Check service status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

### 4. Verify Deployment

```bash
# Health check
curl http://localhost/

# Check API documentation
curl http://localhost/docs
```

## Architecture

The production deployment includes:

1. **API Service** - FastAPI application with 4 Uvicorn workers
2. **MongoDB** - Database with authentication enabled
3. **Nginx** - Reverse proxy with rate limiting and caching

## Security Features

### Docker Image Security

- **Multi-stage build** - Reduces final image size
- **Non-root user** - Application runs as `appuser`
- **Minimal dependencies** - Only runtime dependencies included
- **Security scanning** - Base image regularly updated

### Nginx Security

- Rate limiting (10 req/s per IP)
- Security headers (X-Frame-Options, X-XSS-Protection, etc.)
- Request size limits (50MB max)
- HTTPS support (configure SSL certificates)

### MongoDB Security

- Authentication required
- Root credentials from environment
- Network isolated via Docker network
- Data persistence with volumes

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGO_ROOT_USERNAME` | admin | MongoDB root username |
| `MONGO_ROOT_PASSWORD` | - | MongoDB root password (REQUIRED) |
| `JWT_SECRET` | - | JWT signing secret (REQUIRED) |
| `JWT_REFRESH_SECRET` | - | JWT refresh token secret (REQUIRED) |
| `WORKERS` | 4 | Number of Uvicorn workers |
| `MAX_WORKERS` | 8 | Maximum worker limit |
| `TIMEOUT` | 120 | Request timeout in seconds |

### Resource Limits

Default limits per container:

- **API**: 2 CPU cores, 4GB RAM
- **MongoDB**: System default
- **Nginx**: System default

Adjust in `docker-compose.prod.yml` under `deploy.resources`.

## SSL/TLS Setup (Production)

### 1. Obtain SSL Certificates

Using Let's Encrypt (recommended):

```bash
# Install certbot
sudo apt-get install certbot

# Get certificates
sudo certbot certonly --standalone -d your-domain.com
```

### 2. Copy Certificates

```bash
# Create SSL directory
mkdir -p nginx/ssl

# Copy certificates
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem nginx/ssl/
```

### 3. Enable HTTPS

Edit `nginx/conf.d/api.conf`:

1. Uncomment the HTTPS server block
2. Update `server_name` with your domain
3. Uncomment the HTTP to HTTPS redirect

Restart nginx:

```bash
docker-compose -f docker-compose.prod.yml restart nginx
```

## Monitoring

### View Logs

```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f api

# Last 100 lines
docker-compose -f docker-compose.prod.yml logs --tail=100
```

### Health Checks

All services include health checks:

```bash
# Check container health
docker ps

# Manual health check
curl http://localhost/health
```

### Resource Monitoring

```bash
# Real-time stats
docker stats

# Service-specific stats
docker stats profit-sharing-api
```

## Backup and Recovery

### Database Backup

```bash
# Backup MongoDB
docker exec profit-sharing-mongodb mongodump \
  --username admin \
  --password <your-password> \
  --authenticationDatabase admin \
  --out /data/backup

# Copy backup to host
docker cp profit-sharing-mongodb:/data/backup ./backup-$(date +%Y%m%d)
```

### Database Restore

```bash
# Copy backup to container
docker cp ./backup profit-sharing-mongodb:/data/restore

# Restore MongoDB
docker exec profit-sharing-mongodb mongorestore \
  --username admin \
  --password <your-password> \
  --authenticationDatabase admin \
  /data/restore
```

## Scaling

### Horizontal Scaling

Increase API workers:

```bash
# In .env file
WORKERS=8

# Restart API service
docker-compose -f docker-compose.prod.yml restart api
```

### Load Balancing

For multiple API instances:

1. Update `nginx/conf.d/api.conf` upstream block:
   ```nginx
   upstream api_backend {
       least_conn;
       server api-1:8000;
       server api-2:8000;
       server api-3:8000;
   }
   ```

2. Deploy multiple API containers in compose file

## Troubleshooting

### API Not Starting

```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs api

# Common issues:
# 1. MongoDB not ready - wait for health check
# 2. Missing models - verify models/ directory
# 3. Permission errors - check file ownership
```

### Database Connection Failed

```bash
# Verify MongoDB is running
docker-compose -f docker-compose.prod.yml ps mongodb

# Test connection
docker exec profit-sharing-mongodb mongosh \
  --username admin \
  --password <your-password> \
  --authenticationDatabase admin
```

### Nginx Not Accessible

```bash
# Check nginx logs
docker-compose -f docker-compose.prod.yml logs nginx

# Verify port binding
netstat -tuln | grep 80
```

## Maintenance

### Update Application

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose -f docker-compose.prod.yml up -d --build

# Remove old images
docker image prune -f
```

### Update Dependencies

```bash
# Update requirements.txt
# Rebuild image
docker-compose -f docker-compose.prod.yml build --no-cache api
docker-compose -f docker-compose.prod.yml up -d api
```

### Clean Up

```bash
# Stop all services
docker-compose -f docker-compose.prod.yml down

# Remove volumes (WARNING: deletes data)
docker-compose -f docker-compose.prod.yml down -v

# Remove images
docker-compose -f docker-compose.prod.yml down --rmi all
```

## Production Checklist

- [ ] Configure strong passwords and secrets in `.env`
- [ ] Set up SSL/TLS certificates
- [ ] Configure firewall rules
- [ ] Set up automated backups
- [ ] Configure log rotation
- [ ] Set up monitoring and alerts
- [ ] Review and adjust resource limits
- [ ] Test disaster recovery procedures
- [ ] Document custom configurations
- [ ] Set up CI/CD pipeline

## Support

For issues and questions:
- Check logs: `docker-compose -f docker-compose.prod.yml logs`
- Review health status: `docker ps`
- Verify configuration: `docker-compose -f docker-compose.prod.yml config`
