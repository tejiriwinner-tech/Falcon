# Falcon Monitoring & Maintenance Guide

## Monitoring

### Application Health

### Health Check Endpoint
The application provides a health check endpoint:
```bash
curl http://localhost:8000/api/v1/health
```

Response:
```json
{
  "status": "healthy",
  "version": "4.2.0",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### Monitoring Metrics

#### Key Metrics to Monitor
1. **API Response Times**
   - Average response time per endpoint
   - P95 and P99 response times
   - Slow request identification

2. **Error Rates**
   - HTTP 4xx errors (client errors)
   - HTTP 5xx errors (server errors)
   - Error rate by endpoint

3. **Rate Limiting**
   - Number of rate-limited requests
   - Top rate-limited IPs
   - Rate limit utilization

4. **Database Performance**
   - Connection pool utilization
   - Query execution times
   - Database connection errors

5. **External API Calls**
   - TwelveData API call success rate
   - FMP API call success rate
   - Alpha Vantage API call success rate
   - API quota usage

### Log Monitoring

#### Log Levels
- **INFO**: Normal operation messages
- **WARNING**: Potentially harmful situations
- **ERROR**: Error events that might still allow the application to continue
- **CRITICAL**: Critical errors that may cause application failure

#### Important Log Patterns
- Rate limit violations
- API authentication failures
- Database connection errors
- External API failures
- Validation errors

### Recommended Monitoring Tools

#### Docker Native Monitoring
```bash
# Container stats
docker stats falcon-backend

# Container logs
docker logs -f falcon-backend

# Health check
docker inspect --format='{{.State.Health.Status}}' falcon-backend
```

#### Prometheus + Grafana (Recommended for Production)
- Set up Prometheus to scrape metrics
- Use Grafana for visualization
- Create dashboards for:
  - API performance
  - Error rates
  - Rate limiting
  - Database health

#### CloudWatch / Datadog / New Relic
- Use cloud-native monitoring if deploying to cloud platforms
- Set up alerts for:
  - High error rates (> 5%)
  - Slow response times (> 2s)
  - High rate limit violations
  - Database connection failures

## Maintenance

### Regular Maintenance Tasks

#### Daily
- Review error logs
- Check rate limit utilization
- Monitor API quota usage
- Verify data freshness

#### Weekly
- Review performance metrics
- Check database storage usage
- Review external API costs
- Update security patches

#### Monthly
- Rotate API keys (if required)
- Review and update rate limits
- Audit access logs
- Backup database

### Database Maintenance

#### PostgreSQL
```bash
# Vacuum and analyze
VACUUM ANALYZE;

# Reindex
REINDEX DATABASE falcon;

# Check table sizes
SELECT 
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

#### SQLite
```bash
# Vacuum to reclaim space
sqlite3 falcon_market_data.db "VACUUM;"

# Check database integrity
sqlite3 falcon_market_data.db "PRAGMA integrity_check;"
```

### Log Rotation

#### Docker Logs
```bash
# Configure log rotation in docker-compose.yml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

#### Application Logs
Configure log rotation in your logging configuration to prevent disk space issues.

### Security Maintenance

#### Dependency Updates
```bash
# Check for outdated packages
pip list --outdated

# Update packages
pip install --upgrade package_name

# Run security audit
pip-audit
```

#### API Key Rotation
1. Generate new API keys
2. Update environment variables
3. Restart application
4. Verify functionality
5. Revoke old keys

### Backup Procedures

#### Database Backup
```bash
# PostgreSQL
pg_dump $DATABASE_URL > backup-$(date +%Y%m%d).sql

# SQLite
cp falcon_market_data.db backup-$(date +%Y%m%d).db
```

#### Configuration Backup
```bash
# Backup environment variables
cp .env .env.backup-$(date +%Y%m%d)

# Backup configuration files
tar -czf config-backup-$(date +%Y%m%d).tar.gz .env.example settings.py
```

### Disaster Recovery

#### Recovery Checklist
1. Restore database from backup
2. Restore configuration files
3. Verify environment variables
4. Start application
5. Run health checks
6. Monitor logs for errors

#### Testing Backups
- Test database restore monthly
- Verify backup integrity
- Document recovery procedures
- Keep offsite backups

## Alerting

### Critical Alerts
- Application down (health check fails)
- Error rate > 10%
- Database connection failures
- API key authentication failures

### Warning Alerts
- Error rate > 5%
- Response time > 2s
- Rate limit violations > 100/hour
- Database connection pool > 80% utilization

### Informational Alerts
- Scheduled maintenance completed
- Backup completed
- Security patches applied

## Performance Tuning

### Database Tuning
- Adjust connection pool size based on load
- Add indexes for frequently queried columns
- Partition large tables if needed
- Enable query caching

### API Tuning
- Adjust rate limits based on traffic patterns
- Tune cache durations for different endpoints
- Optimize expensive queries
- Implement request batching where possible

### Application Tuning
- Adjust worker processes based on CPU cores
- Tune timeout values
- Optimize async operations
- Profile and optimize slow code paths