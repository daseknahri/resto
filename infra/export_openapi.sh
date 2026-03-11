#!/usr/bin/env bash
set -euo pipefail

BACKEND_DIR="${1:-backend}"
OUTPUT_FILE="${2:-openapi.json}"

pushd "$BACKEND_DIR" >/dev/null
if [[ -x ".venv/bin/python" ]]; then
  PY=".venv/bin/python"
else
  PY="python"
fi

"$PY" manage.py generateschema --format openapi-json --file "$OUTPUT_FILE"
echo "OpenAPI schema exported to $(pwd)/$OUTPUT_FILE"
popd >/dev/null
