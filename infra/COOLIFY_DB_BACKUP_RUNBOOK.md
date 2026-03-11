# Coolify Postgres Backup and Restore Runbook

This runbook covers manual backup, restore drill, and suggested schedule for the live stack.

## 1. Prerequisites

- Access to Coolify server terminal (Docker host).
- Running app with postgres service container.
- `docker` available on the server.

Scripts:

- `infra/coolify/backup_postgres.sh`
- `infra/coolify/restore_postgres.sh`

## 2. Find Postgres Container

If you know resource UUID:

```bash
docker ps --format '{{.Names}}' | grep '^postgres-<RESOURCE_UUID>-'
```

Or list all postgres containers:

```bash
docker ps --format '{{.Names}}' | grep '^postgres-'
```

## 3. Create Backup

Recommended command:

```bash
./infra/coolify/backup_postgres.sh \
  --resource-uuid <RESOURCE_UUID> \
  --db-name kepoli_platform \
  --db-user kepoli_user \
  --output-dir /var/backups/kepoli \
  --retention-days 14
```

Expected output:

- `.dump` file in `/var/backups/kepoli`
- `.sha256` checksum file next to it

## 4. Restore Drill (Required)

Run a restore drill at least once after each major schema change.

Example restore:

```bash
./infra/coolify/restore_postgres.sh \
  --resource-uuid <RESOURCE_UUID> \
  --backup-file /var/backups/kepoli/kepoli_platform_<TIMESTAMP>.dump \
  --db-name kepoli_platform \
  --db-user kepoli_user \
  --admin-user kepoli_user
```

Notes:

- This defaults to drop/recreate target DB for clean restore.
- Use `--no-drop-recreate` only when you explicitly need in-place restore.

## 5. Post-Restore Verification

After restore:

1. Redeploy app or restart API service.
2. Confirm health:
   - `https://menu.kepoli.com/health`
   - `https://admin.menu.kepoli.com/health`
3. Validate critical app paths:
   - `https://yassernahri7.menu.kepoli.com/menu`
   - `https://admin.menu.kepoli.com/admin-console`

## 6. Scheduling (Daily)

Use a server cron job (or Coolify scheduled task on host) to run daily backup.

Example cron (03:15 UTC):

```cron
15 3 * * * /bin/bash /opt/resto/infra/coolify/backup_postgres.sh --resource-uuid <RESOURCE_UUID> --db-name kepoli_platform --db-user kepoli_user --output-dir /var/backups/kepoli --retention-days 14 >> /var/log/resto/db-backup.log 2>&1
```

## 7. Safety

- Keep backup directory outside container writable layers.
- Do not store backups only on same VPS long-term; copy to external storage.
- Test restore regularly, not only backup creation.
