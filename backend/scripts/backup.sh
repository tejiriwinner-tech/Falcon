#!/bin/bash
# Backup script for Falcon backend
# Backs up database and configuration files

set -e

# Configuration
BACKUP_DIR="/backups/falcon"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo "Starting backup at $(date)"

# Backup database if DATABASE_URL is set (PostgreSQL)
if [ -n "$DATABASE_URL" ]; then
    echo "Backing up PostgreSQL database..."
    pg_dump "$DATABASE_URL" > "$BACKUP_DIR/database_$DATE.sql"
    gzip "$BACKUP_DIR/database_$DATE.sql"
    echo "Database backup completed: database_$DATE.sql.gz"
else
    echo "Backing up SQLite database..."
    cp falcon_market_data.db "$BACKUP_DIR/database_$DATE.db"
    gzip "$BACKUP_DIR/database_$DATE.db"
    echo "Database backup completed: database_$DATE.db.gz"
fi

# Backup configuration
echo "Backing up configuration files..."
cp .env "$BACKUP_DIR/env_$DATE"
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" .env.example app/core/config/

echo "Configuration backup completed: config_$DATE.tar.gz"

# Clean old backups
echo "Cleaning backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -type f -mtime +$RETENTION_DAYS -delete

echo "Backup completed successfully at $(date)"
echo "Backup location: $BACKUP_DIR"