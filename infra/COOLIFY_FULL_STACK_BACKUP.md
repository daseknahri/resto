# Coolify Full-Stack Backup and Wildcard Verification

This runbook gives you a single backup flow before risky deploys and a quick check that wildcard tenant routing is still alive after deploys.

## Scripts

- `infra/coolify/backup_full_stack.sh`
- `infra/coolify/check_live_wildcard.sh`

## 1. Full-stack backup

Run on the VPS host:

```bash
cd /opt/resto

bash infra/coolify/backup_full_stack.sh \
  --resource-uuid <RESOURCE_UUID> \
  --db-name kepoli_platform \
  --db-user kepoli_user \
  --base-domain menu.kepoli.com \
  --output-root /var/backups/kepoli
```

This captures:

- current git commit
- git status snapshot
- optional git rollback tag pushed to origin
- PostgreSQL dump + checksum
- API runtime env export
- media volume tarball
- live wildcard proxy file if present
- wildcard cert archive if present
- backup manifest

Output directory example:

```text
/var/backups/kepoli/20260314T101500Z/
```

## 2. Dry run before first use

```bash
bash infra/coolify/backup_full_stack.sh \
  --resource-uuid <RESOURCE_UUID> \
  --dry-run
```

## 3. Live wildcard verification

Run on the VPS host:

```bash
cd /opt/resto

bash infra/coolify/check_live_wildcard.sh \
  --base-domain menu.kepoli.com \
  --tenant-slug smoke
```

This checks:

- live dynamic proxy file exists
- wildcard cert files exist
- proxy rule still targets your base domain
- `coolify-proxy` is running
- `http://<slug>.menu.../health` redirects/answers
- `https://<slug>.menu.../health` answers

## 4. After deploy checklist

Run these after a risky deploy:

```bash
bash infra/coolify/check_live_wildcard.sh --base-domain menu.kepoli.com --tenant-slug smoke
curl -I https://menu.kepoli.com/health
curl -I https://admin.menu.kepoli.com/health
curl -I https://<real-tenant>.menu.kepoli.com/health
```

## 5. Restore notes

Database restore still uses:

```bash
bash infra/coolify/restore_postgres.sh \
  --resource-uuid <RESOURCE_UUID> \
  --backup-file /var/backups/kepoli/<TIMESTAMP>/kepoli_platform_<TIMESTAMP>.dump \
  --db-name kepoli_platform \
  --db-user kepoli_user \
  --admin-user kepoli_user
```

Media restore can be done from the archived tarball inside the backup directory by mounting the current `media` Docker volume into a temporary container and extracting it back.

## 6. Safety

- Run a full-stack backup before schema changes, env changes, or major UI deploys.
- Keep at least one backup copy outside the VPS.
- Keep the git tag created by the backup script. It gives you a fast code rollback point.
