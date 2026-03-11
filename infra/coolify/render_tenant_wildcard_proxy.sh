#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Render a Coolify/Traefik wildcard tenant proxy config for *.menu domains.

Usage:
  render_tenant_wildcard_proxy.sh [options]

Options:
  --resource-uuid <uuid>      Coolify resource UUID used to auto-detect frontend container
  --frontend-container <name> Explicit frontend container name
  --base-domain <domain>      Tenant namespace base domain (default: menu.kepoli.com)
  --cert-dir <path>           Cert directory mounted in proxy (default: /traefik/certs/menu.kepoli.com)
  --output <path>             Write YAML to file instead of stdout
  --prefer-ip                 Resolve frontend IP on the proxy-shared network and use direct IP target
  --dry-run                   Print chosen target metadata to stderr
  -h, --help                  Show help

Examples:
  bash infra/coolify/render_tenant_wildcard_proxy.sh --resource-uuid n0sg80s0oc8w8kkk4osg4s88
  bash infra/coolify/render_tenant_wildcard_proxy.sh --frontend-container frontend-xxx --output /tmp/wildcard.yml
EOF
}

RESOURCE_UUID=""
FRONTEND_CONTAINER=""
BASE_DOMAIN="menu.kepoli.com"
CERT_DIR="/traefik/certs/menu.kepoli.com"
OUTPUT_PATH=""
PREFER_IP=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --resource-uuid)
      RESOURCE_UUID="${2:-}"
      shift 2
      ;;
    --frontend-container)
      FRONTEND_CONTAINER="${2:-}"
      shift 2
      ;;
    --base-domain)
      BASE_DOMAIN="${2:-}"
      shift 2
      ;;
    --cert-dir)
      CERT_DIR="${2:-}"
      shift 2
      ;;
    --output)
      OUTPUT_PATH="${2:-}"
      shift 2
      ;;
    --prefer-ip)
      PREFER_IP=1
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
      usage >&2
      exit 2
      ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "docker command not found" >&2
  exit 1
fi

detect_frontend_container() {
  if [[ -n "$FRONTEND_CONTAINER" ]]; then
    echo "$FRONTEND_CONTAINER"
    return 0
  fi

  local pattern='^frontend-'
  if [[ -n "$RESOURCE_UUID" ]]; then
    pattern="^frontend-${RESOURCE_UUID}-"
  fi

  local matches
  matches="$(docker ps --format '{{.Names}}' | grep -E "$pattern" || true)"
  local count
  count="$(echo "$matches" | awk 'NF>0{c++} END{print c+0}')"
  if [[ "$count" -eq 0 ]]; then
    echo "No matching frontend container found. Pass --frontend-container explicitly." >&2
    exit 1
  fi
  if [[ "$count" -gt 1 ]]; then
    echo "Multiple frontend containers matched. Pass --frontend-container explicitly." >&2
    echo "$matches" >&2
    exit 1
  fi
  echo "$matches"
}

detect_shared_ip() {
  local frontend_container="$1"
  python - "$frontend_container" <<'PY'
import json
import subprocess
import sys

frontend = sys.argv[1]

def inspect(name):
    out = subprocess.check_output(["docker", "inspect", name], text=True)
    return json.loads(out)[0]["NetworkSettings"]["Networks"]

proxy_networks = inspect("coolify-proxy")
frontend_networks = inspect(frontend)

shared = sorted(set(proxy_networks) & set(frontend_networks))
if not shared:
    raise SystemExit("No shared Docker network between coolify-proxy and frontend container.")

for network in shared:
    ip = frontend_networks[network].get("IPAddress") or ""
    if ip:
        print(ip)
        raise SystemExit(0)

raise SystemExit("No frontend IP found on shared network.")
PY
}

FRONTEND_CONTAINER="$(detect_frontend_container)"
TARGET_URL=""
TARGET_MODE=""

if [[ "$PREFER_IP" -eq 1 ]]; then
  FRONTEND_IP="$(detect_shared_ip "$FRONTEND_CONTAINER")"
  TARGET_URL="http://${FRONTEND_IP}:3000"
  TARGET_MODE="shared-network-ip"
else
  if docker exec coolify-proxy sh -lc "wget -qO- http://${FRONTEND_CONTAINER}:3000/health >/dev/null" 2>/dev/null; then
    TARGET_URL="http://${FRONTEND_CONTAINER}:3000"
    TARGET_MODE="container-name"
  else
    FRONTEND_IP="$(detect_shared_ip "$FRONTEND_CONTAINER")"
    TARGET_URL="http://${FRONTEND_IP}:3000"
    TARGET_MODE="shared-network-ip"
  fi
fi

CERT_FILE="${CERT_DIR%/}/fullchain.pem"
KEY_FILE="${CERT_DIR%/}/privkey.pem"

YAML_CONTENT="$(cat <<EOF
http:
  routers:
    kepoli-tenant-wildcard-http:
      entryPoints:
        - http
      ruleSyntax: v2
      rule: HostRegexp(\`{tenant:[a-z0-9-]+}.${BASE_DOMAIN}\`)
      middlewares:
        - kepoli-tenant-https-redirect
      service: noop@internal

    kepoli-tenant-wildcard-https:
      entryPoints:
        - https
      ruleSyntax: v2
      rule: HostRegexp(\`{tenant:[a-z0-9-]+}.${BASE_DOMAIN}\`)
      service: kepoli-tenant-frontend-direct
      priority: 100
      tls: true

  services:
    kepoli-tenant-frontend-direct:
      loadBalancer:
        passHostHeader: true
        servers:
          - url: ${TARGET_URL}

  middlewares:
    kepoli-tenant-https-redirect:
      redirectScheme:
        scheme: https
        permanent: true

tls:
  certificates:
    - certFile: ${CERT_FILE}
      keyFile: ${KEY_FILE}
EOF
)"

if [[ "$DRY_RUN" -eq 1 ]]; then
  {
    echo "Frontend container: ${FRONTEND_CONTAINER}"
    echo "Target mode: ${TARGET_MODE}"
    echo "Target URL: ${TARGET_URL}"
    echo "Base domain: ${BASE_DOMAIN}"
    echo "Cert dir: ${CERT_DIR}"
  } >&2
fi

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  printf '%s\n' "$YAML_CONTENT" > "$OUTPUT_PATH"
  echo "Wrote wildcard proxy config to: $OUTPUT_PATH"
else
  printf '%s\n' "$YAML_CONTENT"
fi
