#!/usr/bin/env bash
# Generate the local secrets BriefAlpha requires at startup.
# Idempotent: skips files that already exist.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SECRETS_DIR="$ROOT/data/.secrets"

mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

ALIAS_KEY="$SECRETS_DIR/alias_key"
if [[ ! -f "$ALIAS_KEY" ]]; then
  # 32 bytes = 256-bit AES-GCM key
  openssl rand -out "$ALIAS_KEY" 32
  chmod 600 "$ALIAS_KEY"
  echo "[init_secrets] created alias_key"
else
  echo "[init_secrets] alias_key already present"
fi

ADMIN_TOKEN="$SECRETS_DIR/admin_token"
if [[ ! -f "$ADMIN_TOKEN" ]]; then
  printf "%s" "$(openssl rand -hex 32)" > "$ADMIN_TOKEN"
  chmod 600 "$ADMIN_TOKEN"
  echo "[init_secrets] created admin_token"
else
  echo "[init_secrets] admin_token already present"
fi

KEYS_JSON="$SECRETS_DIR/llm_api_keys.json"
if [[ ! -f "$KEYS_JSON" ]]; then
  cat > "$KEYS_JSON" <<'JSON'
{
  "anthropic": "sk-ant-replace-me",
  "openai": "sk-replace-me",
  "vision_anthropic": "sk-ant-vision-replace-me"
}
JSON
  chmod 600 "$KEYS_JSON"
  echo "[init_secrets] wrote placeholder llm_api_keys.json — replace before launching API"
else
  echo "[init_secrets] llm_api_keys.json already present"
fi

echo "[init_secrets] done. Files in $SECRETS_DIR:"
ls -la "$SECRETS_DIR"
