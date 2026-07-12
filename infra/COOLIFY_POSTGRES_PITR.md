# Postgres Point-in-Time Recovery (PITR) — OPS-1 runbook

> **Status: DRAFT for the owner to review, adapt to the live VPS, and validate with a restore
> drill before relying on it.** This closes RISK **OPS-1** (single Postgres, nightly `pg_dump`
> only → ~24 h RPO → up to a full day of wallet top-ups / orders / payouts unrecoverable on a
> disk failure). Target after enabling: **RPO ≤ 5 min** for the money tables.
>
> Prereq / companion: **OPS-2** (off-box shipping) must be enabled first — PITR is only as safe
> as where the WAL + base backups live. Reuse the existing
> [`install_backup_cron.sh --remote-copy-cmd`](coolify/install_backup_cron.sh) off-box hook and
> [`COOLIFY_DB_BACKUP_RUNBOOK.md`](COOLIFY_DB_BACKUP_RUNBOOK.md). WAL that only lives on the VPS
> does **not** improve durability — it must ship off-box continuously.

## Why the current setup isn't enough

`infra/coolify/backup_postgres.sh` takes a logical `pg_dump` on a cron (default nightly, 14-day
retention). That is a fine *second* line of defense, but between two dumps every committed
transaction is at risk: a 14:00 disk loss with a 02:00 dump = 12 h of money movement gone. PITR
fixes this by continuously archiving the **write-ahead log (WAL)**, so you can restore a base
backup and then *replay* WAL forward to any second before the incident.

The Postgres service is `postgres:16-alpine` in `docker-compose.coolify.yml` (service `postgres`,
tuned via `-c` command flags). Both approaches below are additive to that service.

---

## Approach A — native WAL archiving (lighter; reuses the off-box hook)

Good when you want minimal new tooling. You archive each completed WAL segment off-box and take a
periodic base backup; recovery = restore base + replay WAL.

### 1. Turn on archiving (add to the `postgres` service `command:` in `docker-compose.coolify.yml`)

```yaml
    command: >
      postgres
      # …existing tuning flags…
      -c wal_level=replica
      -c archive_mode=on
      -c archive_timeout=300          # force a WAL segment at least every 5 min → caps RPO at 5 min
      -c archive_command='test ! -f /wal_archive/%f && cp %p /wal_archive/%f'
    volumes:
      - pg_wal_archive:/wal_archive    # add this named volume (+ under top-level `volumes:`)
```

`archive_command` must return non-zero if it fails so Postgres retains the segment and retries —
never let it silently drop WAL. The command above copies to a local archive dir; a **sidecar/cron
then ships `/wal_archive` off-box** (rclone/rsync/scp), mirroring the `--remote-copy-cmd` pattern
already used for dumps. Prune archived-and-shipped segments only *after* a fresh base backup (see
`pg_archivecleanup`).

> Trade-off to decide: archiving straight to the object store inside `archive_command` (simplest,
> but a slow/unreachable store stalls WAL recycling and can fill the data disk) vs. archive-local
> + async off-box ship (a moment's exposure if the VPS dies between copy and ship). For ≤5 min RPO
> with safety, prefer archive-local + a 60 s off-box ship loop with alerting on lag.

### 2. Weekly base backup (the PITR anchor)

```bash
# physical base backup — the point WAL replay starts from
pg_basebackup -h <pg-container> -U "$POSTGRES_USER" -D /var/backups/kepoli/base-$(date +%F) \
  -Ft -z -Xs -P
# then ship the base backup off-box too (same rclone/--remote-copy-cmd hook as the dumps)
```

Keep ≥2 base backups off-box; retain WAL back to the oldest base you keep.

### 3. Restore to a point in time (the drill — do this on a scratch host, not prod)

```bash
# 1. restore the newest base backup that predates the target time into the data dir
# 2. drop the archived WAL where restore_command can reach it, then:
cat > $PGDATA/postgresql.auto.conf <<'EOF'
restore_command = 'cp /wal_archive/%f %p'
recovery_target_time = '2026-07-12 13:59:30+00'   # a few seconds before the incident
recovery_target_action = 'promote'
EOF
touch $PGDATA/recovery.signal
# 3. start Postgres; it replays WAL to the target and promotes. Verify row counts / last wallet txn.
```

---

## Approach B — pgBackRest (recommended for a money app)

More robust: parallel compressed incrementals, retention policy, integrity checks, one-command
PITR, native S3-compatible repo (so WAL + backups are off-box by construction). Worth the extra
setup for a system where the DB *is* the business.

- Run `pgbackrest` as a sidecar (or on the host) with a repo on the same S3-compatible bucket OPS-2
  uses. Point `archive_command = 'pgbackrest --stanza=kepoli archive-push %p'`.
- `pgbackrest --stanza=kepoli stanza-create`, then a weekly `backup --type=full` + daily
  `--type=diff` on cron.
- PITR restore: `pgbackrest --stanza=kepoli --type=time "--target=2026-07-12 13:59:30+00" restore`.
- Set `repo1-retention-full` / `repo1-retention-diff` so retention is automatic.
- See the pgBackRest user guide for the exact `pgbackrest.conf`; keep the stanza name + repo creds
  in Coolify env, never in the image.

---

## Owner action checklist

- [ ] OPS-2 off-box shipping confirmed working (dumps already land off-box + freshness probe green).
- [ ] Pick Approach A or B (B recommended if you can spare the setup time).
- [ ] Apply the config on a **staging** Postgres first; confirm `archive_command` succeeds
      (`SELECT * FROM pg_stat_archiver;` — `failed_count` stays 0, `last_archived_time` advances).
- [ ] Take a base backup; confirm it + WAL are landing off-box.
- [ ] **Run a real restore drill** to a chosen timestamp on a scratch host; verify the last wallet
      transaction / order is present and the balance-vs-ledger check (`reconcile_wallet_balances`)
      passes on the restored DB. This drill is the only thing that proves the RPO.
- [ ] Add archiver-lag + off-box-ship-lag to alerting (a stalled `archive_command` silently reverts
      you to dump-only RPO — treat it like the backup-freshness probe).
- [ ] Record the chosen approach + retention in `docs/adr/` and update the OPS-1 register entry.

## What an agent can't do here (why this is a draft)

Provisioning the object-store repo/credentials, editing the live Coolify Postgres service, and
running the restore drill against real infrastructure are owner/ops actions (no cloud creds, no
prod access, no local Postgres to exercise this against). This runbook is the map; the drill is
the proof.
