#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Install or remove a cron job that runs uptime_probe.sh for Coolify production.

Usage:
  install_uptime_cron.sh [options]
  install_uptime_cron.sh --remove [options]

Options:
  --repo-dir <path>           Repo root path (default: /opt/resto)
  --runner-path <path>        Generated runner script path (default: /usr/local/bin/resto-uptime-run.sh)
  --webhook-env-file <path>   Env file used by runner for webhook URL (default: /etc/default/resto-uptime)
  --webhook-url <url>         Webhook URL to write into env file
  --interval <cron_expr>      Cron schedule (default: */5 * * * *)
  --log-file <path>           Cron output log file (default: /var/log/resto-uptime.log)
  --cooldown-minutes <n>      Repeated down-alert cooldown in minutes (default: 20)
  --state-file <path>         Probe state file path (default: /var/tmp/kepoli-uptime.state)
  --check <url|code>          Check spec (repeatable). Default is kepoli frontend/admin/api health URLs.
  --remove                    Remove installed cron line and generated runner
  --dry-run                   Print actions only, do not write files
  -h, --help                  Show help

Examples:
  install_uptime_cron.sh
  install_uptime_cron.sh --webhook-url "https://hooks.example.com/..."
  install_uptime_cron.sh --remove
EOF
}

REPO_DIR="/opt/resto"
RUNNER_PATH="/usr/local/bin/resto-uptime-run.sh"
WEBHOOK_ENV_FILE="/etc/default/resto-uptime"
INTERVAL="*/5 * * * *"
LOG_FILE="/var/log/resto-uptime.log"
COOLDOWN_MINUTES="20"
STATE_FILE="/var/tmp/kepoli-uptime.state"
WEBHOOK_URL="${UPTIME_ALERT_WEBHOOK:-}"
REMOVE=0
DRY_RUN=0
CHECKS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-dir)
      REPO_DIR="${2:-}"
      shift 2
      ;;
    --runner-path)
      RUNNER_PATH="${2:-}"
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
    --interval)
      INTERVAL="${2:-}"
      shift 2
      ;;
    --log-file)
      LOG_FILE="${2:-}"
      shift 2
      ;;
    --cooldown-minutes)
      COOLDOWN_MINUTES="${2:-20}"
      shift 2
      ;;
    --state-file)
      STATE_FILE="${2:-/var/tmp/kepoli-uptime.state}"
      shift 2
      ;;
    --check)
      CHECKS+=("${2:-}")
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

if [[ ${#CHECKS[@]} -eq 0 ]]; then
  CHECKS=(
    "https://kepoli.com/health|200"
    "https://admin.kepoli.com/health|200"
    "https://api.kepoli.com/api/health/|200"
  )
fi

PROBE_SCRIPT="${REPO_DIR%/}/infra/coolify/uptime_probe.sh"
if [[ "$REMOVE" -eq 0 && ! -f "$PROBE_SCRIPT" ]]; then
  echo "Probe script not found: $PROBE_SCRIPT" >&2
  exit 1
fi

if [[ "$REMOVE" -eq 1 ]]; then
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] would remove cron marker line # resto_uptime_probe"
    echo "[dry-run] would remove runner script: $RUNNER_PATH"
  else
    existing_cron="$(crontab -l 2>/dev/null || true)"
    filtered_cron="$(printf '%s\n' "$existing_cron" | sed '/# resto_uptime_probe[[:space:]]*$/d')"
    printf '%s\n' "$filtered_cron" | crontab -
    rm -f "$RUNNER_PATH"
    echo "Removed uptime cron and runner."
  fi
  exit 0
fi

runner_dir="$(dirname "$RUNNER_PATH")"
if [[ "$DRY_RUN" -eq 0 ]]; then
  mkdir -p "$runner_dir"
fi

if [[ -n "$WEBHOOK_URL" ]]; then
  webhook_env_dir="$(dirname "$WEBHOOK_ENV_FILE")"
  if [[ "$DRY_RUN" -eq 0 ]]; then
    mkdir -p "$webhook_env_dir"
    {
      echo "UPTIME_ALERT_WEBHOOK=$WEBHOOK_URL"
    } > "$WEBHOOK_ENV_FILE"
    chmod 600 "$WEBHOOK_ENV_FILE"
  fi
fi

check_args=()
for spec in "${CHECKS[@]}"; do
  check_args+=(--check "$spec")
done

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] would write runner: $RUNNER_PATH"
else
  {
    echo '#!/usr/bin/env bash'
    echo 'set -euo pipefail'
    echo "if [[ -f \"$WEBHOOK_ENV_FILE\" ]]; then"
    echo "  # shellcheck source=/etc/default/resto-uptime"
    echo "  source \"$WEBHOOK_ENV_FILE\""
    echo 'fi'
    printf '/bin/bash "%s"' "$PROBE_SCRIPT"
    for arg in "${check_args[@]}"; do
      printf ' %q' "$arg"
    done
    printf ' --cooldown-minutes %q --state-file %q\n' "$COOLDOWN_MINUTES" "$STATE_FILE"
  } > "$RUNNER_PATH"
  chmod 750 "$RUNNER_PATH"
fi

CRON_LINE="$INTERVAL $RUNNER_PATH >> $LOG_FILE 2>&1 # resto_uptime_probe"
existing_cron="$(crontab -l 2>/dev/null || true)"
filtered_cron="$(printf '%s\n' "$existing_cron" | sed '/# resto_uptime_probe[[:space:]]*$/d')"
new_cron="$(printf '%s\n%s\n' "$filtered_cron" "$CRON_LINE" | sed '/^[[:space:]]*$/d')"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] cron line:"
  echo "$CRON_LINE"
  if [[ -n "$WEBHOOK_URL" ]]; then
    echo "[dry-run] webhook env file: $WEBHOOK_ENV_FILE"
  fi
else
  printf '%s\n' "$new_cron" | crontab -
  echo "Installed uptime cron:"
  echo "$CRON_LINE"
  if [[ -n "$WEBHOOK_URL" ]]; then
    echo "Webhook saved in: $WEBHOOK_ENV_FILE"
  fi
fi
