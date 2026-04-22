#!/usr/bin/env sh
# Print a random value suitable for ADMIN_API_KEY (Bearer token for POST /v1/station/apikey).
# Usage: ./scripts/generate-admin-api-key.sh
#        ADMIN_API_KEY=$(./scripts/generate-admin-api-key.sh)
set -e
openssl rand -hex 32
