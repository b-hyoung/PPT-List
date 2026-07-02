#!/usr/bin/env bash
set -euo pipefail

# Deploy `smart-care-home` to Cloudflare Pages using Wrangler v2
# Requires env vars: CF_ACCOUNT_ID and CF_API_TOKEN

if [ -z "${CF_ACCOUNT_ID:-}" ] || [ -z "${CF_API_TOKEN:-}" ]; then
  echo "이 스크립트를 실행하려면 환경변수 CF_ACCOUNT_ID와 CF_API_TOKEN을 설정하세요."
  echo "예: export CF_ACCOUNT_ID=... && export CF_API_TOKEN=... && ./scripts/deploy.sh"
  exit 1
fi

PROJECT_DIR="./smart-care-home"
PROJECT_NAME="smart-care-home"

if [ ! -d "$PROJECT_DIR" ]; then
  echo "찾을 수 없음: $PROJECT_DIR"
  exit 1
fi

echo "Cloudflare API 토큰을 환경으로 설정합니다 (임시)."
export CLOUDFLARE_API_TOKEN="$CF_API_TOKEN"

echo "Cloudflare Pages에 배포 중: $PROJECT_DIR"

# Prefer npx so user doesn't need global install; fall back to global wrangler if present
if command -v npx >/dev/null 2>&1; then
  npx @cloudflare/wrangler@2 pages publish "$PROJECT_DIR" --project-name "$PROJECT_NAME" --branch main --account-id "$CF_ACCOUNT_ID"
else
  if ! command -v wrangler >/dev/null 2>&1; then
    echo "wrangler가 설치되어 있지 않습니다. 먼저 설치하세요: npm install -g @cloudflare/wrangler@2"
    exit 1
  fi
  wrangler pages publish "$PROJECT_DIR" --project-name "$PROJECT_NAME" --branch main --account-id "$CF_ACCOUNT_ID"
fi

echo "배포 명령이 완료되었습니다. Pages 콘솔에서 빌드/도메인 상태를 확인하세요."
