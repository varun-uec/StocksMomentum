# Backup & Restore Strategy

## Overview

Momentum25 uses PostgreSQL for persistent storage and Redis for caching. This document
describes the backup strategy for production deployments.

## Database Backup (PostgreSQL)

### Automated Backups

Configure daily automated backups using `pg_dump`:

```bash
# Full database backup
pg_dump -h localhost -U momentum25 -d momentum25 \
  --format=custom \
  --file=/backups/momentum25_$(date +%Y%m%d_%H%M%S).dump

# Compressed SQL backup (more portable)
pg_dump -h localhost -U momentum25 -d momentum25 \
  --format=plain \
  --no-owner \
  | gzip > /backups/momentum25_$(date +%Y%m%d_%H%M%S).sql.gz
```

### Using Docker

```bash
# Backup from running container
docker exec -t momentum25-db-1 pg_dump \
  -U momentum25 \
  -d momentum25 \
  --format=custom \
  -f /tmp/momentum25_backup.dump

docker cp momentum25-db-1:/tmp/momentum25_backup.dump ./backups/

# Or use the docker compose exec shorthand
docker compose exec -T db pg_dump \
  -U momentum25 \
  -d momentum25 \
  --format=custom \
  > ./backups/momentum25_$(date +%Y%m%d).dump
```

### Backup Schedule

| Frequency | Type | Retention |
|---|---|---|
| Daily | Full database dump | 7 days |
| Weekly | Full database dump | 4 weeks |
| Monthly | Full database dump | 12 months |
| Continuous | WAL archiving (optional) | Depends on recovery requirements |

### Verification

Regularly verify backups by restoring to a test database:

```bash
# Create a test database
createdb -U momentum25 momentum25_restore_test

# Restore backup
pg_restore -U momentum25 -d momentum25_restore_test \
  --no-owner \
  --exit-on-error \
  ./backups/momentum25_latest.dump

# Verify data integrity
psql -U momentum25 -d momentum25_restore_test \
  -c "SELECT count(*) FROM securities;"
psql -U momentum25 -d momentum25_restore_test \
  -c "SELECT count(*) FROM ohlcv_bars;"
```

## Redis Backup

### RDB Snapshots

Redis is configured with AOF persistence in the Docker Compose setup. RDB snapshots
are taken automatically based on the Redis configuration.

### Manual Backup

```bash
# Trigger a background save
redis-cli BGSAVE

# Copy the dump file
cp /data/dump.rdb /backups/redis_$(date +%Y%m%d).rdb
```

### Docker Backup

```bash
# From running container
docker exec momentum25-redis-1 redis-cli SAVE
docker cp momentum25-redis-1:/data/dump.rdb ./backups/redis_$(date +%Y%m%d).rdb
```

## Restore Procedures

### Full Restore (PostgreSQL)

```bash
# 1. Stop the API service (prevent writes during restore)
docker compose stop api

# 2. Drop and recreate the database
docker compose exec db psql -U momentum25 -c "DROP DATABASE IF EXISTS momentum25;"
docker compose exec db psql -U momentum25 -c "CREATE DATABASE momentum25;"

# 3. Restore from backup
docker compose exec -T db pg_restore \
  -U momentum25 \
  -d momentum25 \
  --no-owner \
  --exit-on-error \
  < ./backups/momentum25_latest.dump

# 4. Run any pending migrations
docker compose run --rm api alembic upgrade head

# 5. Start the API service
docker compose start api
```

### Point-in-Time Recovery (if WAL archiving is enabled)

```bash
# 1. Restore base backup
pg_restore -U momentum25 -d momentum25 ./backups/momentum25_base.dump

# 2. Configure recovery.conf or recovery.signal
# 3. Apply WAL archives up to the desired point in time
# 4. Verify data consistency
```

## Disaster Recovery

### RPO (Recovery Point Objective)

- With daily backups: Maximum 24 hours of data loss
- With WAL archiving: Maximum 1 minute of data loss

### RTO (Recovery Time Objective)

- From daily backup: ~30-60 minutes (depending on database size)
- From WAL archiving: ~15-30 minutes

## Backup Automation (Cron)

```bash
# Daily backup script (add to crontab)
# 0 2 * * * /path/to/scripts/backup.sh

#!/bin/bash
BACKUP_DIR="/backups/database"
RETENTION_DAYS=7
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

docker compose exec -T db pg_dump \
  -U momentum25 \
  -d momentum25 \
  --format=custom \
  --file=/tmp/backup_$TIMESTAMP.dump

docker cp momentum25-db-1:/tmp/backup_$TIMESTAMP.dump "$BACKUP_DIR/"

# Clean up old backups
find "$BACKUP_DIR" -name "*.dump" -mtime +$RETENTION_DAYS -delete

# Verify backup integrity
pg_restore -l "$BACKUP_DIR/backup_$TIMESTAMP.dump" > /dev/null 2>&1
if [ $? -eq 0 ]; then
  echo "Backup verified: $TIMESTAMP"
else
  echo "Backup verification FAILED: $TIMESTAMP"
fi