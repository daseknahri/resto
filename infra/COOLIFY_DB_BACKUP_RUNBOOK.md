# Coolify Postgres Backup and Restore Runbook

This runbook covers manual backup, restore drill, and suggested schedule for the live stack.

## 1. Prerequisites

- Access to Coolify server terminal (Docker host).
- Running app with postgres service container.
- `docker` available on the server.

Scripts:

- `infra/coolify/backup_postgres.sh` — create a dump + checksum, prune by retention
- `infra/coolify/restore_postgres.sh` — restore a dump into a (throwaway or live) DB
- `infra/coolify/install_backup_cron.sh` — install/remove the daily-backup + freshness-probe crons (Section 6)
- `infra/coolify/backup_freshness_probe.sh` — alert if the newest dump is stale/missing

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
  --db-name ibnbatoutaweb_platform \
  --db-user ibnbatoutaweb_user \
  --output-dir /var/backups/ibnbatoutaweb \
  --retention-days 14
```

Expected output:

- `.dump` file in `/var/backups/ibnbatoutaweb`
- `.sha256` checksum file next to it

## 4. Restore Drill (Required)

Run a restore drill at least once after each major schema change.

Example restore:

```bash
./infra/coolify/restore_postgres.sh \
  --resource-uuid <RESOURCE_UUID> \
  --backup-file /var/backups/ibnbatoutaweb/ibnbatoutaweb_platform_<TIMESTAMP>.dump \
  --db-name ibnbatoutaweb_platform \
  --db-user ibnbatoutaweb_user \
  --admin-user ibnbatoutaweb_user
```

Notes:

- This defaults to drop/recreate target DB for clean restore.
- Use `--no-drop-recreate` only when you explicitly need in-place restore.

## 5. Post-Restore Verification

After restore:

1. Redeploy app or restart API service.
2. Confirm health:
   - `https://menu.ibnbatoutaweb.com/health`
   - `https://admin.menu.ibnbatoutaweb.com/health`
3. Validate critical app paths:
   - `https://yassernahri7.menu.ibnbatoutaweb.com/menu`
   - `https://admin.menu.ibnbatoutaweb.com/admin-console`

## 6. Automated backups (install once)

> A backup you never schedule + never verify is not a backup. Section 6 below
> schedules it; Section 8 is the drill that proves it can actually be restored.

`infra/coolify/install_backup_cron.sh` installs the whole backup automation in one
command. It mirrors `install_uptime_cron.sh`: it generates runner scripts, writes a
single shared webhook env file, and edits the crontab with distinct marker comments
so it never touches the uptime cron or any other crontab line.

It installs **two** cron jobs:

| Cron | Marker | Default schedule | What it does |
| --- | --- | --- | --- |
| Daily backup | `# kepoli_db_backup` | `30 2 * * *` (02:30 daily) | Runs `backup_postgres.sh`, logs to `--log-file`, alerts the webhook if the dump **fails**, and optionally copies the dump off-VPS. |
| Freshness probe | `# kepoli_backup_freshness` | `0 */6 * * *` (every 6h) | Runs `backup_freshness_probe.sh`; alerts if the newest dump is **missing or older than `--max-age-hours` (default 26h)**. |

Why both? The daily backup's on-failure alert can only fire **if cron actually runs
it**. If the backup cron silently dies (host reboot, crontab wiped, runner deleted),
no failure alert ever fires — the database just quietly stops being backed up. The
freshness probe is the independent watchdog: it alerts when the newest dump goes
stale, catching exactly that "cron stopped running" case. One webhook covers both.

### Install

```bash
cd /opt/resto

bash infra/coolify/install_backup_cron.sh \
  --resource-uuid <RESOURCE_UUID> \
  --db-name ibnbatoutaweb_platform \
  --db-user ibnbatoutaweb_user \
  --output-dir /var/backups/ibnbatoutaweb \
  --retention-days 14 \
  --webhook-url "https://hooks.slack.com/services/XXXX" \
  --alert-format slack
```

Dry-run first to see exactly what would be written (no files/cron touched):

```bash
bash infra/coolify/install_backup_cron.sh --resource-uuid <RESOURCE_UUID> --dry-run
```

The webhook URL/format are written to `/etc/default/kepoli-backup` (chmod 600). The
same env vars (`UPTIME_ALERT_WEBHOOK` / `UPTIME_ALERT_FORMAT`) are reused by the
uptime probe, so ops configures **one** alert destination for everything.

### Off-VPS copy (3-2-1: do not keep backups only on the same VPS)

`install_backup_cron.sh` does **not** ship hardcoded storage credentials. Supply
your own copy command with `--remote-copy-cmd`; the literal token `{DUMP_DIR}` is
replaced with the backup output directory. A copy failure also triggers a webhook
alert.

```bash
bash infra/coolify/install_backup_cron.sh \
  --resource-uuid <RESOURCE_UUID> \
  --db-name ibnbatoutaweb_platform \
  --db-user ibnbatoutaweb_user \
  --output-dir /var/backups/ibnbatoutaweb \
  --retention-days 14 \
  --webhook-url "https://hooks.slack.com/services/XXXX" \
  --alert-format slack \
  --remote-copy-cmd "rclone copy {DUMP_DIR} remote:kepoli-backups --max-age 25h"
```

The owner is responsible for configuring the remote (e.g. `rclone config`, SSH keys
for `rsync`/`scp`) on the VPS beforehand. The command runs only after a **successful**
local dump.

### Verify / inspect / remove

```bash
crontab -l | grep kepoli                       # confirm both marker lines present
tail -n 50 /var/log/kepoli-backup.log          # backup + freshness output
ls -lt /var/backups/ibnbatoutaweb/*.dump | head # newest dump on disk

# manual one-off freshness check (exit 1 == stale/missing):
bash infra/coolify/backup_freshness_probe.sh \
  --output-dir /var/backups/ibnbatoutaweb --db-name ibnbatoutaweb_platform

# remove BOTH crons + BOTH generated runners (idempotent; leaves uptime cron intact):
bash infra/coolify/install_backup_cron.sh --remove
```

## 7. Manual daily scheduling (alternative to Section 6)

If you do not use `install_backup_cron.sh`, a plain server cron job also works.

Example cron (03:15 UTC):

```cron
15 3 * * * /bin/bash /opt/resto/infra/coolify/backup_postgres.sh --resource-uuid <RESOURCE_UUID> --db-name ibnbatoutaweb_platform --db-user ibnbatoutaweb_user --output-dir /var/backups/ibnbatoutaweb --retention-days 14 >> /var/log/resto/db-backup.log 2>&1
```

This route has **no freshness alarm** — prefer Section 6.

## 8. RESTORE DRILL (run once before launch, then quarterly)

**An unrehearsed restore is not a backup.** A `.dump` file you have never restored is
an unverified assumption, not a recovery plan. This drill is the **R1 (DURABILITY)
completion gate**: it is an OWNER task executed on the VPS — it cannot be run from a
dev machine, CI, or by an assistant (no VPS/Docker/Postgres access). R1 is not
"done" until this drill passes at least once **before launch**, and it must be
repeated **quarterly** (and after any major schema change).

Restore into a **THROWAWAY** database — never the live DB.

Checklist:

1. **Take a fresh dump** (do not reuse an old one — you are also testing today's backup path):

   ```bash
   cd /opt/resto
   bash infra/coolify/backup_postgres.sh \
     --resource-uuid <RESOURCE_UUID> \
     --db-name ibnbatoutaweb_platform \
     --db-user ibnbatoutaweb_user \
     --output-dir /var/backups/ibnbatoutaweb \
     --no-prune
   # note the printed dump path: /var/backups/ibnbatoutaweb/ibnbatoutaweb_platform_<TS>.dump
   ```

2. **Restore into a throwaway DB** (NOT the live database name):

   ```bash
   bash infra/coolify/restore_postgres.sh \
     --resource-uuid <RESOURCE_UUID> \
     --backup-file /var/backups/ibnbatoutaweb/ibnbatoutaweb_platform_<TS>.dump \
     --db-name ibnbatoutaweb_restore_drill \
     --db-user ibnbatoutaweb_user \
     --admin-user ibnbatoutaweb_user
   ```

   This drops/recreates `ibnbatoutaweb_restore_drill` (throwaway) and `pg_restore`s
   into it with `--exit-on-error`. The script verifies the `.sha256` checksum first.

3. **Run the schema-health check against the restored DB.** This is the strongest
   proof the data is structurally usable (it derives expected columns for the
   money/identity tables from the models and asserts they physically exist):

   ```bash
   # Point Django at the restored DB and run the check inside the api container.
   # Adjust the DB env var names to match your settings (DATABASE_URL or PG* vars).
   docker exec -e POSTGRES_DB=ibnbatoutaweb_restore_drill <api-container> \
     python manage.py check_schema_health
   ```

   Expect exit 0 ("schema OK"). A non-zero exit means the restored schema is
   incomplete — the backup is NOT trustworthy; stop and investigate before launch.

4. **Smoke the live endpoints** (these confirm the running stack itself is healthy —
   the drill restored into a throwaway DB, so live is untouched):

   ```bash
   curl -I https://menu.ibnbatoutaweb.com/api/health/        # SSL-redirect-exempt; expect 200
   curl -I https://<real-tenant>.menu.ibnbatoutaweb.com/menu # one tenant menu; expect 200
   ```

5. **Drop the throwaway DB** when done:

   ```bash
   docker exec <postgres-container> psql -U ibnbatoutaweb_user -d postgres \
     -c 'DROP DATABASE IF EXISTS ibnbatoutaweb_restore_drill;'
   ```

6. **Record the drill** (keep this log; it is the audit trail R1 requires):

   | Field | Value |
   | --- | --- |
   | Dump file restored | `/var/backups/.../ibnbatoutaweb_platform_<TS>.dump` |
   | Dump timestamp | `<TS>` |
   | Restore target DB | `ibnbatoutaweb_restore_drill` |
   | `check_schema_health` result | PASS / FAIL |
   | Endpoints verified | `/api/health/` 200, `<tenant>/menu` 200 |
   | Who / when | `<name>` / `<date>` |
   | Off-VPS copy confirmed present | yes / no |

## 9. Safety

- Keep backup directory outside container writable layers.
- Do not store backups only on same VPS long-term; copy to external storage.
- Test restore regularly, not only backup creation.
