#!/usr/bin/env bash

set -euo pipefail

# Configuration (can be overridden via environment variables)
SERVER_HOST="${SERVER_HOST:-62.60.176.194}"
SERVER_USER="${SERVER_USER:-root}"
DEPLOY_PATH="${DEPLOY_PATH:-/root/task}"
# SECURITY: Prefer exporting SERVER_PASSWORD env var instead of hardcoding.
SERVER_PASSWORD="${SERVER_PASSWORD:-}"

if [[ -z "${SERVER_PASSWORD}" ]]; then
  read -r -s -p "Enter server password for ${SERVER_USER}@${SERVER_HOST}: " SERVER_PASSWORD
  echo
fi

require() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Error: required command '$1' not found." >&2
    return 1
  fi
}

ensure_sshpass() {
  if command -v sshpass >/dev/null 2>&1; then
    return 0
  fi
  echo "sshpass not found. Attempting to install..."
  if [[ "${OSTYPE:-}" == darwin* ]]; then
    if command -v brew >/dev/null 2>&1; then
      # Try official formula first; if not available, use tap
      if ! brew list sshpass >/dev/null 2>&1; then
        brew install hudochenkov/sshpass/sshpass || brew install esolitos/ipa/sshpass || true
      fi
    fi
  fi
  if ! command -v sshpass >/dev/null 2>&1; then
    echo "Please install 'sshpass' manually and re-run. On macOS: 'brew install hudochenkov/sshpass/sshpass'" >&2
    exit 1
  fi
}

main() {
  require tar
  require ssh
  require scp
  ensure_sshpass

  local archive
  archive="$(mktemp -t deploy.tar.gz)"

  echo "Creating deploy archive..."
  # On macOS, prevent AppleDouble (._*) and extended attributes from being archived
  COPYFILE_DISABLE=1 tar czf "${archive}" \
    --exclude='.git' \
    --exclude='.github' \
    --exclude='front/node_modules' \
    --exclude='**/.DS_Store' \
    --exclude='**/._*' \
    --exclude='._*' \
    --exclude='**/dist' \
    --exclude='**/build' \
    --exclude='back/var/*' \
    .

  echo "Uploading archive to ${SERVER_USER}@${SERVER_HOST}..."
  export SSHPASS="${SERVER_PASSWORD}"
  sshpass -e \
    scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        -o PreferredAuthentications=password -o PubkeyAuthentication=no -o KbdInteractiveAuthentication=no \
        -P 22 "${archive}" "${SERVER_USER}@${SERVER_HOST}:/root/deploy.tar.gz"

  echo "Deploying on remote host and restarting containers..."
  sshpass -e \
    ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        -o PreferredAuthentications=password -o PubkeyAuthentication=no -o KbdInteractiveAuthentication=no \
        -p 22 "${SERVER_USER}@${SERVER_HOST}" \
        "set -euo pipefail; \
         mkdir -p '${DEPLOY_PATH}'; \
         tar xzf /root/deploy.tar.gz -C '${DEPLOY_PATH}'; \
         # Cleanup potential macOS metadata files if any slipped in
         find '${DEPLOY_PATH}' -type f -name '._*' -delete || true; \
         find '${DEPLOY_PATH}' -type f -name '.DS_Store' -delete || true; \
         rm -f /root/deploy.tar.gz; \
         cd '${DEPLOY_PATH}'; \
         if docker compose version >/dev/null 2>&1; then \
           docker compose down || true; \
           docker compose up -d --build; \
         elif docker-compose version >/dev/null 2>&1; then \
           docker-compose down || true; \
           docker-compose up -d --build; \
         else \
           echo 'Docker Compose not found on remote host.' >&2; \
           exit 1; \
         fi"

  rm -f "${archive}"
  echo "Done."
}

main "$@"


