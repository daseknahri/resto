#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Remove STALE DUPLICATE containers of the Kepoli stack — the 2026-09-18 outage fix.

Background (see infra/COOLIFY_ORPHAN_CONTAINER_CLEANUP.md and
docs/INCIDENT_2026-09-18_db_connection_exhaustion.md): Coolify's Docker Compose
deploy did not reap superseded containers, so 8 orphaned `admin-*` containers from
old deploys stayed "Up 4 months", each holding persistent Postgres connections
(CONN_MAX_AGE) until `max_connections` was exhausted and every /api/* returned 500.

Ordinary `docker container prune` does NOT help: those orphans were RUNNING, and
prune only removes STOPPED containers. This script instead finds, per stateless
app service, every running container and keeps only the NEWEST — removing the older
duplicates that hog connections.

SAFETY:
  * Stateful services (postgres, redis) are NEVER touched — data risk. If you somehow
    have duplicate postgres/redis containers, resolve those by hand.
  * Dry-run by DEFAULT. You must pass --apply to actually remove anything.
  * Only containers whose name matches --prefix are considered, so this cannot reach
    other Coolify apps on the same host.

Usage:
  prune_stale_stack_containers.sh --prefix <name-substring> [--apply] [options]

Options:
  --prefix <str>     REQUIRED. Substring that identifies this stack's containers
                     (e.g. the Coolify resource name/uuid, or "ibnbatoutaweb").
                     Match it against `docker ps --format '{{.Names}}'` first.
  --services <list>  Comma-separated service names to dedupe
                     (default: api,admin,frontend,worker,beat).
  --apply            Actually remove stale duplicates (default: dry-run only).
  --keep <n>         Keep the newest N per service (default: 1).
  -h, --help         Show help.

Wire-up options (pick one — see the runbook):
  * Best: make Coolify pass `--remove-orphans` on `docker compose up` so this is
    never needed (fixes the root cause).
  * Safety net: run this from a host cron / Coolify server-level Scheduled Task,
    e.g. every 15 min:  prune_stale_stack_containers.sh --prefix <name> --apply
EOF
}

PREFIX=""
SERVICES="api,admin,frontend,worker,beat"
APPLY=0
KEEP=1

while [ $# -gt 0 ]; do
  case "$1" in
    --prefix)   PREFIX="${2:-}"; shift 2 ;;
    --services) SERVICES="${2:-}"; shift 2 ;;
    --keep)     KEEP="${2:-}"; shift 2 ;;
    --apply)    APPLY=1; shift ;;
    -h|--help)  usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

if [ -z "$PREFIX" ]; then
  echo "ERROR: --prefix is required (a substring that identifies THIS stack's containers)." >&2
  echo "Run 'docker ps --format \"{{.Names}}\"' and pick a stable substring." >&2
  exit 2
fi

# Never dedupe stateful services even if asked.
PROTECTED="postgres redis"

removed_any=0
IFS=',' read -r -a svc_arr <<< "$SERVICES"
for svc in "${svc_arr[@]}"; do
  svc="$(echo "$svc" | tr -d '[:space:]')"
  [ -z "$svc" ] && continue
  for p in $PROTECTED; do
    if [ "$svc" = "$p" ]; then
      echo "SKIP protected stateful service: $svc"
      continue 2
    fi
  done

  # Running containers for this service in this stack, NEWEST FIRST (CreatedAt desc).
  # Match both the service token and the stack prefix to avoid cross-app collisions.
  mapfile -t names < <(
    docker ps --filter "status=running" --format '{{.CreatedAt}}\t{{.Names}}' \
      | sort -r \
      | awk -F'\t' -v svc="$svc" -v pfx="$PREFIX" '$2 ~ svc && $2 ~ pfx {print $2}'
  )

  count="${#names[@]}"
  if [ "$count" -le "$KEEP" ]; then
    echo "OK   $svc: $count running (<= keep=$KEEP), nothing to prune"
    continue
  fi

  echo "STALE $svc: $count running, keeping newest $KEEP:"
  idx=0
  for n in "${names[@]}"; do
    if [ "$idx" -lt "$KEEP" ]; then
      echo "   keep   $n"
    else
      if [ "$APPLY" -eq 1 ]; then
        echo "   remove $n  -> docker rm -f"
        docker rm -f "$n" >/dev/null
        removed_any=1
      else
        echo "   would-remove $n  (dry-run; pass --apply)"
      fi
    fi
    idx=$((idx + 1))
  done
done

if [ "$APPLY" -eq 1 ] && [ "$removed_any" -eq 1 ]; then
  echo
  echo "Removed stale duplicates. If Postgres slots were exhausted, the freed"
  echo "connections may linger briefly until Postgres reaps them — if /api/health/"
  echo "still reports db down, restart the postgres container to clear idle sessions."
fi
