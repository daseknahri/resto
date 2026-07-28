# Postgres Point-in-Time Recovery (PITR) — OPS-1 runbook

> **Status: apply-ready runbook — owner provisions + runs the restore drill.** This closes RISK
> **OPS-1** (single Postgres, nightly `pg_dump` only → ~24 h RPO → up to a full day of wallet
> top-ups / orders / payouts unrecoverable on a disk failure). Target after enabling:
> **RPO ≤ 5 min** for the money tables.
>
> **Prereq / companion — do OPS-2 first.** PITR is only as safe as *where* the WAL + base backups
> live. The off-box shipping mechanism already exists — reuse the same object-store bucket via
> [`install_backup_cron.sh --remote-copy-cmd`](coolify/install_backup_cron.sh) and
> [`COOLIFY_DB_BACKUP_RUNBOOK.md`](COOLIFY_DB_BACKUP_RUNBOOK.md). WAL that only lives on the VPS does
> **not** improve durability — it must ship off-box continuously.

## Why the current setup isn't enough

`infra/coolify/backup_postgres.sh` takes a logical `pg_dump` on a cron (default nightly, 14-day
retention). That is a fine *second* line of defense, but between two dumps every committed
transaction is at risk: a 14:00 disk loss with a 02:00 dump = **12 h of money movement gone**. PITR
fixes this by continuously archiving the **write-ahead log (WAL)** so you can restore a base backup
and *replay* WAL forward to any second before the incident.

The Postgres service is `postgres:16-alpine` in `docker-compose.coolify.yml` (service `postgres`,
named volume `postgres_data`, tuned via `-c` command flags, `expose: 5432` only). Paths 2 and 3
below are **additive** to that service; Path 1 replaces it with a managed service.

---

## The decision: pick one path

| | **Path 1 — Managed Postgres** | **Path 2 — pgBackRest (self-hosted)** | **Path 3 — native WAL archiving** |
|---|---|---|---|
| RPO | seconds (provider streams WAL) | ≤ 5 min | ≤ 5 min |
| DR ops burden | **lowest** — provider runs + tests it | medium — you run stanza + drills | **highest** — you build ship + prune + alert |
| PITR restore | provider console, one action | `pgbackrest ... restore` (one command) | manual base-restore + WAL replay |
| New moving parts | none (DB leaves the VPS) | a `pgbackrest` sidecar + config | an off-box WAL-ship loop you maintain |
| Cost | **$$ / month** (managed instance) | reuses the OPS-2 bucket (~free) | reuses the OPS-2 bucket (~free) |
| Migration needed | **yes** — move DB off the container | no | no |
| Best when | money app, want DR to be someone else's tested job | must stay on the VPS, want robust self-hosted DR | you want zero new tooling and accept manual recovery |

**Recommendation.** For a money app on a single VPS, **Path 1 (managed Postgres)** is the strongest
choice: it deletes the entire class of "my DR was silently misconfigured" failures — the provider
does *tested* continuous archiving, PITR, and replicas, and a restore is a console action instead of
a runbook you hope works. The monthly cost buys correctness on the one system that *is* the business.
If you must stay self-hosted, use **Path 2 (pgBackRest)** — it's purpose-built for exactly this and
gives one-command PITR. **Path 3** is the fallback when you want no new dependencies and accept a
more manual recovery.

Whichever you pick, **keep the OPS-2 nightly `pg_dump` running** as an independent, format-portable
second line of defense (a logical dump survives a corrupt-WAL / bad-upgrade scenario that PITR can't).

---

## Path 1 — Managed Postgres with built-in PITR (recommended)

Move the database off the Coolify container to a managed Postgres 16 with built-in PITR. DR becomes
the provider's job; the app only changes its connection string.

**Candidate providers** (any Postgres 16 with PITR + daily automated backups): DigitalOcean Managed
Databases, AWS RDS / Aurora, Supabase, Crunchy Bridge, Neon. Pick one **in the same region** as the
VPS to keep latency low.

### Cutover steps (run in a maintenance window)

1. **Provision** a Postgres 16 instance. Enable automated backups + PITR (most default to a 7-day
   window). Note the connection string, and **allowlist the VPS's egress IP** (or use the provider's
   private network).
2. **Freeze writes**: put the app in maintenance / scale the `api` + `worker` + `beat` services to 0
   in Coolify so no new transactions land mid-migration.
3. **Dump → load** (schemas included — this app is multi-tenant `django-tenants`, so *all* schemas
   must come across, not just `public`):
   ```bash
   # from the VPS, against the live container
   docker exec "$PG_CONTAINER" pg_dumpall -U "$POSTGRES_USER" --clean --if-exists > /tmp/full.sql
   # load into the managed instance (psql client or the provider console)
   psql "$MANAGED_DATABASE_URL" < /tmp/full.sql
   ```
   > `pg_dumpall` (not `pg_dump`) captures every tenant schema + roles in one pass. For a large DB,
   > prefer per-database `pg_dump -Fc` + `pg_restore -j <N>` for parallelism, but `pg_dumpall` is the
   > simplest correct default here.
4. **Repoint the app** — in Coolify env, set `DATABASE_URL` to the managed connection string and
   update `POSTGRES_HOST` / `POSTGRES_*` accordingly. If the managed provider requires TLS, append
   `?sslmode=require` (RDS/DO/Supabase all do).
5. **Verify before unfreezing** (see [Verification](#verification-the-drill-is-the-proof)):
   ```bash
   python manage.py migrate_schemas --list        # every tenant schema present & migrated
   python manage.py check_schema_health           # returns 0
   python manage.py reconcile_wallet_balances     # balance == sum(ledger), no drift
   ```
6. **Unfreeze**: scale `api`/`worker`/`beat` back up. Run the production smoke
   (`infra/production_tenant_smoke.ps1`).
7. **Retire the container DB**: stop the `postgres` service in compose (leave the `postgres_data`
   volume for a few weeks as a rollback anchor, then remove). Keep a logical-dump cron against the
   **managed** DB as the OPS-2 second line of defense — note that `backup_postgres.sh` currently
   dumps a *local container* via `docker exec`, so for a managed host run `pg_dump` directly instead
   (e.g. a cron doing `pg_dump "$MANAGED_DATABASE_URL" --format=custom … | rclone rcat …`), or add a
   remote-host branch to the script. Don't assume the existing script works unchanged against a
   remote DB.

### What DR looks like afterward
A disk/host loss no longer touches the database. Recovery from data corruption = provider console →
"restore to timestamp". RPO is the provider's WAL-streaming granularity (seconds). Your only ongoing
job is the OPS-2 logical dump + a periodic drill of the provider's restore.

---

## Path 2 — pgBackRest self-hosted (recommended if staying on the VPS)

pgBackRest gives parallel compressed incrementals, automatic retention, integrity checks, and
**one-command PITR** with the WAL + backups living on the OPS-2 S3 bucket *by construction*.

### 1. Config — `infra/coolify/pgbackrest.conf.example`

A companion template is provided at
[`coolify/pgbackrest.conf.example`](coolify/pgbackrest.conf.example). Copy it to `/etc/pgbackrest/`
on the VPS and fill the repo bucket/creds from Coolify env (never bake creds into the image). Key
settings: `repo1-type=s3`, `repo1-path=/pgbackrest`, `repo1-retention-full=2`,
`repo1-retention-diff=6`, `repo1-s3-*` from the same bucket OPS-2 ships dumps to (a separate prefix).

### 2. Turn on archiving (add to the `postgres` service `command:` in `docker-compose.coolify.yml`)

```yaml
    command: >
      postgres
      # …existing tuning flags (shared_buffers, max_connections, etc.)…
      -c wal_level=replica
      -c archive_mode=on
      -c archive_timeout=300                                   # force a segment ≥ every 5 min → caps RPO
      -c archive_command='pgbackrest --stanza=kepoli archive-push %p'
```

`archive_command` **must** return non-zero on failure so Postgres retains the segment and retries —
pgBackRest does this correctly. Mount the pgBackRest config + a spool dir into the container (or run
pgBackRest in a sidecar that shares the PGDATA volume).

### 3. Create the stanza + schedule backups (cron on the host)

```bash
pgbackrest --stanza=kepoli stanza-create        # once, after archiving is on
pgbackrest --stanza=kepoli check                 # confirms archive + repo reachable

# cron:
0 3 * * 0  pgbackrest --stanza=kepoli --type=full backup     # weekly full
0 3 * * 1-6 pgbackrest --stanza=kepoli --type=diff backup    # daily diff
```
Retention is automatic from `repo1-retention-*`; no manual prune needed.

### 4. PITR restore (the drill — on a scratch host, never prod)

```bash
pgbackrest --stanza=kepoli --type=time \
  "--target=2026-07-12 13:59:30+00" \
  --target-action=promote restore
# start Postgres against the restored PGDATA; it replays WAL to the target and promotes.
```

### 5. Alert on archiver lag
A stalled `archive_command` silently reverts you to dump-only RPO. Add a probe (mirror
`backup_freshness_probe.sh`) that alerts if `SELECT last_archived_time FROM pg_stat_archiver` falls
behind or `failed_count` rises.

---

## Path 3 — native WAL archiving (lightweight, most manual)

No new tooling — archive each completed WAL segment to a local dir, ship it off-box yourself, and
recover by restoring a `pg_basebackup` + replaying WAL.

```yaml
    command: >
      postgres
      # …existing tuning flags…
      -c wal_level=replica
      -c archive_mode=on
      -c archive_timeout=300
      -c archive_command='test ! -f /wal_archive/%f && cp %p /wal_archive/%f'
    volumes:
      - pg_wal_archive:/wal_archive      # add this named volume under top-level `volumes:` too
```

Then **you must build and maintain**: a 60 s loop that ships `/wal_archive` off-box (rclone/rsync,
mirroring `--remote-copy-cmd`) with lag alerting, a weekly `pg_basebackup -Ft -z -Xs` shipped
off-box, and `pg_archivecleanup` to prune segments older than the oldest base you keep. Recovery uses
`restore_command = 'cp /wal_archive/%f %p'` + `recovery_target_time` + `recovery.signal` (see the
git history of this file for the full snippet). This works, but you own every fragile part — prefer
Path 1 or 2 unless "zero new dependencies" is a hard constraint.

---

## Owner action checklist

- [ ] **OPS-2 off-box shipping confirmed working** (dumps land off-box + freshness probe green) — do this first.
- [ ] **Decide the path** (1 managed / 2 pgBackRest / 3 native) and record it in `docs/adr/` with the reason.
- [ ] **Path 1:** provision managed PG16 + PITR; dump→load all schemas; repoint `DATABASE_URL`; verify; unfreeze; retire container DB.
- [ ] **Path 2:** fill `pgbackrest.conf` from env; enable `archive_mode` on **staging** first; `stanza-create` + `check`; schedule full/diff; add archiver-lag alert.
- [ ] **Path 3:** enable archiving on staging; build + alert the off-box WAL-ship loop; schedule base backups + `pg_archivecleanup`.
- [ ] **Run a real restore/PITR drill** to a chosen timestamp on a scratch host (see below). This drill is the **only** thing that proves the RPO — an untested backup is a hope, not a plan.
- [ ] Add archiver-lag / off-box-ship-lag to alerting (treat a stalled archiver like the backup-freshness probe).
- [ ] Update the **OPS-1 register entry** in `docs/RISK_REGISTER.md` to ✅ once the drill passes, noting the chosen path + retention window.

## Verification (the drill is the proof)

On the restored DB — whichever path — these three must pass before you trust it:

1. `python manage.py migrate_schemas --list` — every tenant schema present and at head.
2. `python manage.py check_schema_health` — returns 0.
3. `python manage.py reconcile_wallet_balances` — `balance == sum(ledger)` with no drift, **and** spot-check
   that the last wallet transaction / order that existed just before your target timestamp is present.

The money invariant passing on the *restored* database is the acceptance criterion for OPS-1.

## What an agent can't do here (why this needs you)

Provisioning the managed instance or the object-store repo + credentials, editing the live Coolify
Postgres service, and running the restore drill against real infrastructure are owner/ops actions
(no cloud creds, no prod access, no local Postgres to exercise this against). This runbook is the
map and the exact commands; **the drill is the proof.**
