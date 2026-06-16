#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Install or remove the Kepoli database backup automation on a Coolify VPS.

Installs TWO cron jobs via generated runner scripts plus a shared webhook env file:
  (a) a DAILY backup cron that runs backup_postgres.sh, logs to a file, alerts on
      failure via webhook, and OPTIONALLY copies the dump off-VPS.
  (b) a FRESHNESS-PROBE cron that runs backup_freshness_probe.sh and alerts if the
      newest dump goes stale (this catches a silently-dead backup cron).

Both crons reuse ONE webhook (env file at --webhook-env-file) so ops configures a
single destination. Distinct cron markers (# kepoli_db_backup,
# kepoli_backup_freshness) mean this never clobbers the uptime cron or any other
crontab lines.

Usage:
  install_backup_cron.sh [options]
  install_backup_cron.sh --remove [options]

Options:
  --repo-dir <path>             Repo root path (default: /opt/resto)
  --backup-runner-path <path>   Generated backup runner (default: /usr/local/bin/kepoli-db-backup-run.sh)
  --freshness-runner-path <path> Generated freshness runner (default: /usr/local/bin/kepoli-backup-freshness-run.sh)
  --webhook-env-file <path>     Env file used by runners for webhook URL (default: /etc/default/kepoli-backup)
  --webhook-url <url>           Webhook URL to write into env file
  --alert-format <name>         Alert payload format: generic|slack|discord
  --backup-interval <cron_expr> Daily backup schedule (default: 30 2 * * *)
  --freshness-interval <cron_expr> Freshness probe schedule (default: 0 */6 * * *)
  --max-age-hours <n>           Freshness staleness threshold in hours (default: 26)
  --log-file <path>             Cron output log file (default: /var/log/kepoli-backup.log)

Backup target (passed through to backup_postgres.sh / backup_freshness_probe.sh):
  --resource-uuid <uuid>        Coolify resource UUID (auto-detect postgres container)
  --container <name>            Explicit postgres container name
  --db-name <name>              Database name (default: backup script default)
  --db-user <name>              Database user for pg_dump (default: backup script default)
  --output-dir <path>          Backup output directory (default: /var/backups/kepoli)
  --retention-days <days>       Prune older backups (default: 14)

Off-VPS copy (optional, owner-supplied -- NEVER hardcoded credentials):
  --remote-copy-cmd "<cmd>"     Command run AFTER a successful backup to copy the
                                dump off-VPS (e.g. an rclone/rsync/scp the owner
                                provides). The literal token {DUMP_DIR} in the cmd
                                is replaced with the backup output directory. A copy
                                failure also triggers a webhook alert. Skipped if
                                not provided.

Control:
  --remove                      Remove BOTH installed cron lines and BOTH runners
  --dry-run                     Print actions only, do not write files
  -h, --help                    Show help

Examples:
  install_backup_cron.sh \
    --resource-uuid <RESOURCE_UUID> \
    --db-name ibnbatoutaweb_platform \
    --db-user ibnbatoutaweb_user \
    --output-dir /var/backups/ibnbatoutaweb \
    --retention-days 14 \
    --webhook-url "https://hooks.example.com/..."

  install_backup_cron.sh \
    --resource-uuid <RESOURCE_UUID> \
    --output-dir /var/backups/ibnbatoutaweb \
    --remote-copy-cmd "rclone copy {DUMP_DIR} remote:kepoli-backups --max-age 25h"

  install_backup_cron.sh --remove
EOF
}

REPO_DIR="/opt/resto"
BACKUP_RUNNER_PATH="/usr/local/bin/kepoli-db-backup-run.sh"
FRESHNESS_RUNNER_PATH="/usr/local/bin/kepoli-backup-freshness-run.sh"
WEBHOOK_ENV_FILE="/etc/default/kepoli-backup"
BACKUP_INTERVAL="30 2 * * *"
FRESHNESS_INTERVAL="0 */6 * * *"
MAX_AGE_HOURS="26"
LOG_FILE="/var/log/kepoli-backup.log"
WEBHOOK_URL="${UPTIME_ALERT_WEBHOOK:-}"
ALERT_FORMAT="${UPTIME_ALERT_FORMAT:-}"

RESOURCE_UUID=""
POSTGRES_CONTAINER=""
DB_NAME=""
DB_USER=""
OUTPUT_DIR="/var/backups/kepoli"
RETENTION_DAYS="14"
REMOTE_COPY_CMD=""

REMOVE=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-dir)
      REPO_DIR="${2:-}"
      shift 2
      ;;
    --backup-runner-path)
      BACKUP_RUNNER_PATH="${2:-}"
      shift 2
      ;;
    --freshness-runner-path)
      FRESHNESS_RUNNER_PATH="${2:-}"
      shift 2
      ;;
    --webhook-env-file)
      WEBHOOK_ENV_FILE="${2:-}"
      shift 2
      ;;
    --webhook-url)
      WEBHOOK_URL="${2:-}"
      shift 2
      ;;
    --alert-format)
      ALERT_FORMAT="${2:-}"
      shift 2
      ;;
    --backup-interval)
      BACKUP_INTERVAL="${2:-}"
      shift 2
      ;;
    --freshness-interval)
      FRESHNESS_INTERVAL="${2:-}"
      shift 2
      ;;
    --max-age-hours)
      MAX_AGE_HOURS="${2:-26}"
      shift 2
      ;;
    --log-file)
      LOG_FILE="${2:-}"
      shift 2
      ;;
    --resource-uuid)
      RESOURCE_UUID="${2:-}"
      shift 2
      ;;
    --container)
      POSTGRES_CONTAINER="${2:-}"
      shift 2
      ;;
    --db-name)
      DB_NAME="${2:-}"
      shift 2
      ;;
    --db-user)
      DB_USER="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --retention-days)
      RETENTION_DAYS="${2:-}"
      shift 2
      ;;
    --remote-copy-cmd)
      REMOTE_COPY_CMD="${2:-}"
      shift 2
      ;;
    --remove)
      REMOVE=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -n "$ALERT_FORMAT" ]]; then
  case "${ALERT_FORMAT,,}" in
    generic|slack|discord)
      ALERT_FORMAT="${ALERT_FORMAT,,}"
      ;;
    *)
      echo "Invalid --alert-format: $ALERT_FORMAT (expected: generic|slack|discord)" >&2
      exit 2
      ;;
  esac
fi

BACKUP_SCRIPT="${REPO_DIR%/}/infra/coolify/backup_postgres.sh"
FRESHNESS_SCRIPT="${REPO_DIR%/}/infra/coolify/backup_freshness_probe.sh"

if [[ "$REMOVE" -eq 1 ]]; then
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] would remove cron marker line # kepoli_db_backup"
    echo "[dry-run] would remove cron marker line # kepoli_backup_freshness"
    echo "[dry-run] would remove runner script: $BACKUP_RUNNER_PATH"
    echo "[dry-run] would remove runner script: $FRESHNESS_RUNNER_PATH"
  else
    existing_cron="$(crontab -l 2>/dev/null || true)"
    filtered_cron="$(printf '%s\n' "$existing_cron" \
      | sed '/# kepoli_db_backup[[:space:]]*$/d' \
      | sed '/# kepoli_backup_freshness[[:space:]]*$/d')"
    printf '%s\n' "$filtered_cron" | crontab -
    rm -f "$BACKUP_RUNNER_PATH"
    rm -f "$FRESHNESS_RUNNER_PATH"
    echo "Removed backup cron, freshness cron, and generated runners."
  fi
  exit 0
fi

if [[ ! -f "$BACKUP_SCRIPT" ]]; then
  echo "Backup script not found: $BACKUP_SCRIPT" >&2
  exit 1
fi
if [[ ! -f "$FRESHNESS_SCRIPT" ]]; then
  echo "Freshness probe script not found: $FRESHNESS_SCRIPT" >&2
  exit 1
fi

# Assemble pass-through args for the backup script.
backup_args=()
if [[ -n "$RESOURCE_UUID" ]]; then
  backup_args+=(--resource-uuid "$RESOURCE_UUID")
fi
if [[ -n "$POSTGRES_CONTAINER" ]]; then
  backup_args+=(--container "$POSTGRES_CONTAINER")
fi
if [[ -n "$DB_NAME" ]]; then
  backup_args+=(--db-name "$DB_NAME")
fi
if [[ -n "$DB_USER" ]]; then
  backup_args+=(--db-user "$DB_USER")
fi
if [[ -n "$OUTPUT_DIR" ]]; then
  backup_args+=(--output-dir "$OUTPUT_DIR")
fi
if [[ -n "$RETENTION_DAYS" ]]; then
  backup_args+=(--retention-days "$RETENTION_DAYS")
fi

# Assemble pass-through args for the freshness probe script.
freshness_args=()
if [[ -n "$OUTPUT_DIR" ]]; then
  freshness_args+=(--output-dir "$OUTPUT_DIR")
fi
if [[ -n "$DB_NAME" ]]; then
  freshness_args+=(--db-name "$DB_NAME")
fi
if [[ -n "$MAX_AGE_HOURS" ]]; then
  freshness_args+=(--max-age-hours "$MAX_AGE_HOURS")
fi

backup_runner_dir="$(dirname "$BACKUP_RUNNER_PATH")"
freshness_runner_dir="$(dirname "$FRESHNESS_RUNNER_PATH")"
if [[ "$DRY_RUN" -eq 0 ]]; then
  mkdir -p "$backup_runner_dir"
  mkdir -p "$freshness_runner_dir"
fi

if [[ -n "$WEBHOOK_URL" || -n "$ALERT_FORMAT" ]]; then
  webhook_env_dir="$(dirname "$WEBHOOK_ENV_FILE")"
  if [[ "$DRY_RUN" -eq 0 ]]; then
    mkdir -p "$webhook_env_dir"
    : > "$WEBHOOK_ENV_FILE"
    if [[ -n "$WEBHOOK_URL" ]]; then
      echo "UPTIME_ALERT_WEBHOOK=$WEBHOOK_URL" >> "$WEBHOOK_ENV_FILE"
    fi
    if [[ -n "$ALERT_FORMAT" ]]; then
      echo "UPTIME_ALERT_FORMAT=$ALERT_FORMAT" >> "$WEBHOOK_ENV_FILE"
    fi
    chmod 600 "$WEBHOOK_ENV_FILE"
  fi
fi

# --- Generate the backup runner ---------------------------------------------
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] would write runner: $BACKUP_RUNNER_PATH"
else
  {
    echo '#!/usr/bin/env bash'
    echo 'set -uo pipefail'
    echo "if [[ -f \"$WEBHOOK_ENV_FILE\" ]]; then"
    echo "  # shellcheck source=/etc/default/kepoli-backup"
    echo "  source \"$WEBHOOK_ENV_FILE\""
    echo 'fi'
    echo 'ALERT_FORMAT="${UPTIME_ALERT_FORMAT:-generic}"'
    echo 'ALERT_WEBHOOK="${UPTIME_ALERT_WEBHOOK:-}"'
    echo 'HOSTNAME_SAFE="$(hostname 2>/dev/null || echo unknown-host)"'
    echo ''
    echo 'json_escape() {'
    echo '  local raw="$1"'
    echo '  raw="${raw//\\/\\\\}"'
    echo '  raw="${raw//\"/\\\"}"'
    echo '  raw="${raw//$'"'"'\n'"'"'/\\n}"'
    echo '  raw="${raw//$'"'"'\r'"'"'/}"'
    echo '  printf "%s" "$raw"'
    echo '}'
    echo ''
    echo 'send_alert() {'
    echo '  local msg="$1"'
    echo '  local ts body'
    echo '  ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"'
    echo '  if [[ -z "$ALERT_WEBHOOK" ]]; then'
    echo '    return 0'
    echo '  fi'
    echo '  case "$ALERT_FORMAT" in'
    echo '    slack)'
    echo '      body="$(printf '"'"'{"text":"%s\nTime: %s"}'"'"' "$(json_escape "$msg")" "$(json_escape "$ts")")"'
    echo '      ;;'
    echo '    discord)'
    echo '      body="$(printf '"'"'{"content":"%s\nTime: %s"}'"'"' "$(json_escape "$msg")" "$(json_escape "$ts")")"'
    echo '      ;;'
    echo '    *)'
    echo '      body="$(printf '"'"'{"event":"backup_failed","timestamp":"%s","message":"%s"}'"'"' "$ts" "$(json_escape "$msg")")"'
    echo '      ;;'
    echo '  esac'
    echo '  if command -v curl >/dev/null 2>&1; then'
    echo '    curl -sS -X POST -H "Content-Type: application/json" --data "$body" "$ALERT_WEBHOOK" >/dev/null || true'
    echo '  fi'
    echo '}'
    echo ''
    printf '/bin/bash "%s"' "$BACKUP_SCRIPT"
    for arg in "${backup_args[@]}"; do
      printf ' %q' "$arg"
    done
    printf '\n'
    echo 'BACKUP_RC=$?'
    echo 'if [[ "$BACKUP_RC" -ne 0 ]]; then'
    echo '  send_alert "Kepoli DB backup FAILED on $HOSTNAME_SAFE (exit $BACKUP_RC)"'
    echo '  exit "$BACKUP_RC"'
    echo 'fi'
    if [[ -n "$REMOTE_COPY_CMD" ]]; then
      # Substitute the {DUMP_DIR} token at install time with the configured output dir.
      resolved_copy_cmd="${REMOTE_COPY_CMD//\{DUMP_DIR\}/$OUTPUT_DIR}"
      echo ''
      echo '# Optional off-VPS copy (owner-supplied command).'
      printf '%s\n' "$resolved_copy_cmd"
      echo 'COPY_RC=$?'
      echo 'if [[ "$COPY_RC" -ne 0 ]]; then'
      echo '  send_alert "Kepoli DB backup off-VPS copy FAILED on $HOSTNAME_SAFE (exit $COPY_RC)"'
      echo '  exit "$COPY_RC"'
      echo 'fi'
    fi
  } > "$BACKUP_RUNNER_PATH"
  chmod 750 "$BACKUP_RUNNER_PATH"
fi

# --- Generate the freshness runner ------------------------------------------
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] would write runner: $FRESHNESS_RUNNER_PATH"
else
  {
    echo '#!/usr/bin/env bash'
    echo 'set -euo pipefail'
    echo "if [[ -f \"$WEBHOOK_ENV_FILE\" ]]; then"
    echo "  # shellcheck source=/etc/default/kepoli-backup"
    echo "  source \"$WEBHOOK_ENV_FILE\""
    echo 'fi'
    printf '/bin/bash "%s"' "$FRESHNESS_SCRIPT"
    for arg in "${freshness_args[@]}"; do
      printf ' %q' "$arg"
    done
    printf '\n'
  } > "$FRESHNESS_RUNNER_PATH"
  chmod 750 "$FRESHNESS_RUNNER_PATH"
fi

# --- Install the two cron lines ---------------------------------------------
BACKUP_CRON_LINE="$BACKUP_INTERVAL $BACKUP_RUNNER_PATH >> $LOG_FILE 2>&1 # kepoli_db_backup"
FRESHNESS_CRON_LINE="$FRESHNESS_INTERVAL $FRESHNESS_RUNNER_PATH >> $LOG_FILE 2>&1 # kepoli_backup_freshness"

existing_cron="$(crontab -l 2>/dev/null || true)"
filtered_cron="$(printf '%s\n' "$existing_cron" \
  | sed '/# kepoli_db_backup[[:space:]]*$/d' \
  | sed '/# kepoli_backup_freshness[[:space:]]*$/d')"
new_cron="$(printf '%s\n%s\n%s\n' "$filtered_cron" "$BACKUP_CRON_LINE" "$FRESHNESS_CRON_LINE" | sed '/^[[:space:]]*$/d')"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] backup cron line:"
  echo "$BACKUP_CRON_LINE"
  echo "[dry-run] freshness cron line:"
  echo "$FRESHNESS_CRON_LINE"
  if [[ -n "$REMOTE_COPY_CMD" ]]; then
    echo "[dry-run] off-VPS copy enabled (command embedded in backup runner)."
  fi
  if [[ -n "$WEBHOOK_URL" || -n "$ALERT_FORMAT" ]]; then
    echo "[dry-run] webhook env file: $WEBHOOK_ENV_FILE"
  fi
else
  printf '%s\n' "$new_cron" | crontab -
  echo "Installed backup cron:"
  echo "$BACKUP_CRON_LINE"
  echo "Installed freshness cron:"
  echo "$FRESHNESS_CRON_LINE"
  if [[ -n "$REMOTE_COPY_CMD" ]]; then
    echo "Off-VPS copy enabled (command embedded in backup runner)."
  else
    echo "Off-VPS copy NOT configured (pass --remote-copy-cmd to enable)."
  fi
  if [[ -n "$WEBHOOK_URL" || -n "$ALERT_FORMAT" ]]; then
    echo "Alert settings saved in: $WEBHOOK_ENV_FILE"
    if [[ -n "$ALERT_FORMAT" ]]; then
      echo "Alert format: $ALERT_FORMAT"
    fi
  fi
fi
