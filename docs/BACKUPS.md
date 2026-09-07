# MAFIA BOT FATHER — BACKUPS & DISASTER RECOVERY

## 1. Automated PostgreSQL Backups
Run automated daily compressed database dumps with cron:
```bash
#!/bin/bash
# /opt/scripts/backup_postgres.sh
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="/var/backups/mafiabotfather"
mkdir -p $BACKUP_DIR

docker exec -t mafiabotfather_postgres pg_dump -U postgres mafiabotfather_db | gzip > "$BACKUP_DIR/mafiadb_$TIMESTAMP.sql.gz"

# Retain backups for 30 days
find $BACKUP_DIR -type f -name "*.sql.gz" -mtime +30 -delete
```

## 2. Restore Procedure
```bash
# Decompress and restore
gunzip < /var/backups/mafiabotfather/mafiadb_YYYYMMDD_HHMMSS.sql.gz | docker exec -i mafiabotfather_postgres psql -U postgres -d mafiabotfather_db
```

## 3. Redis Persistence (RDB & AOF)
Redis is configured with both RDB snapshots (`save 900 1`, `save 300 10`) and AOF append-only logs (`appendonly yes`, `appendfsync everysec`) stored on persistent volume `redis_data`.
