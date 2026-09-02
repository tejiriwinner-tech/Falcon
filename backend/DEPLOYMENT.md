# Falcon Backend Deployment Guide

## Prerequisites

- Docker and Docker Compose installed
- PostgreSQL database (or use SQLite for development)
- API keys for data providers (TwelveData, FMP, Alpha Vantage)
- Environment variables configured

## Environment Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` with your actual values:
```bash
# Database
DATABASE_URL=postgresql://user:password@host:port/database

# API Keys
TWELVEDATA_API_KEY=your_key_here
FMP_API_KEY=your_key_here
ALPHA_VANTAGE_API_KEY=your_key_here

# Security
FALCON_API_KEY=your_secure_api_key
CORS_ORIGINS=https://yourdomain.com
RATE_LIMIT_PER_MINUTE=100
```

## Docker Deployment

### Build and Run with Docker Compose

```bash
# Build the image
docker-compose build

# Start the service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

### Manual Docker Deployment

```bash
# Build the image
docker build -t falcon-backend .

# Run the container
docker run -d \
  --name falcon-backend \
  -p 8000:8000 \
  --env-file .env \
  falcon-backend
```

## Production Considerations

### Security
- Set `FALCON_API_KEY` in production to enable authentication
- Restrict `CORS_ORIGINS` to your actual domain
- Use strong passwords for database
- Enable HTTPS (use reverse proxy like nginx)
- Regularly update dependencies

### Performance
- Configure `DB_POOL_SIZE` based on your database capacity
- Adjust `RATE_LIMIT_PER_MINUTE` based on expected traffic
- Enable response caching headers (already configured)
- Use PostgreSQL instead of SQLite for production

### Monitoring
- Monitor container health via Docker health checks
- Check logs regularly: `docker-compose logs -f`
- Set up logging aggregation (ELK, Loki, etc.)
- Monitor API response times and error rates

### Scaling
- Use Docker Swarm or Kubernetes for horizontal scaling
- Consider using a load balancer
- Implement database read replicas if needed
- Use Redis for distributed caching

## Health Check

The application includes a health check endpoint:
```bash
curl http://localhost:8000/api/v1/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "4.2.0",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## Troubleshooting

### Container won't start
- Check logs: `docker-compose logs`
- Verify environment variables are set
- Ensure ports are not already in use

### Database connection issues
- Verify `DATABASE_URL` is correct
- Check database is accessible from container
- Ensure database credentials are valid

### API errors
- Verify API keys are valid and not expired
- Check rate limits for data providers
- Review logs for specific error messages

## Backup and Recovery

### Database Backup
```bash
# PostgreSQL
pg_dump $DATABASE_URL > backup.sql

# Restore
psql $DATABASE_URL < backup.sql
```

### Application Backup
```bash
# Backup code and configuration
tar -czf falcon-backup-$(date +%Y%m%d).tar.gz .

# Backup environment variables
cp .env .env.backup
```