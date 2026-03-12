#!/usr/bin/env bash
set -euo pipefail

SKIP_BACKEND_TESTS="${SKIP_BACKEND_TESTS:-0}"
SKIP_FRONTEND_LINT="${SKIP_FRONTEND_LINT:-0}"
SKIP_FRONTEND_BUILD="${SKIP_FRONTEND_BUILD:-0}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"

BACKEND_PYTHON="${BACKEND_PYTHON:-$BACKEND_DIR/.venv/bin/python}"
if [[ ! -x "$BACKEND_PYTHON" ]]; then
  BACKEND_PYTHON="$(command -v python3 || command -v python || true)"
fi

if [[ -z "${BACKEND_PYTHON:-}" ]]; then
  echo "Backend Python executable not found." >&2
  exit 1
fi

NPM_COMMAND="${NPM_COMMAND:-npm}"

run_step() {
  local label="$1"
  shift
  echo
  echo "==> $label"
  "$@"
  echo "OK: $label"
}

echo "Release candidate freeze validation"
echo "Repo root: $REPO_ROOT"

pushd "$BACKEND_DIR" >/dev/null
run_step "Backend system check" "$BACKEND_PYTHON" manage.py check
run_step "Migration drift check" "$BACKEND_PYTHON" manage.py makemigrations --check --dry-run
if [[ "$SKIP_BACKEND_TESTS" != "1" ]]; then
  run_step "Backend test suite" "$BACKEND_PYTHON" manage.py test tests -v 1
else
  echo "Skipping backend tests"
fi
popd >/dev/null

pushd "$FRONTEND_DIR" >/dev/null
if [[ "$SKIP_FRONTEND_LINT" != "1" ]]; then
  run_step "Frontend lint" "$NPM_COMMAND" run lint
else
  echo "Skipping frontend lint"
fi

if [[ "$SKIP_FRONTEND_BUILD" != "1" ]]; then
  run_step "Frontend production build" "$NPM_COMMAND" run build
else
  echo "Skipping frontend build"
fi
popd >/dev/null

echo
echo "Release candidate freeze validation completed successfully."
