#!/usr/bin/env bash
# sandoc 의존성 확인 스크립트
# 사용법: bash scripts/check-deps.sh

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

PASS=0
FAIL=0
WARN=0

check() {
  local name="$1"
  local cmd="$2"
  local install_hint="$3"

  printf "%-25s" "$name"
  if command -v "$cmd" &>/dev/null; then
    local ver
    ver=$("$cmd" --version 2>/dev/null | head -1 || echo "installed")
    echo -e "${GREEN}OK${NC}  ($ver)"
    ((PASS++))
  else
    echo -e "${RED}NOT FOUND${NC}  → $install_hint"
    ((FAIL++))
  fi
}

check_optional() {
  local name="$1"
  local cmd="$2"
  local install_hint="$3"

  printf "%-25s" "$name"
  if command -v "$cmd" &>/dev/null; then
    local ver
    ver=$("$cmd" --version 2>/dev/null | head -1 || echo "installed")
    echo -e "${GREEN}OK${NC}  ($ver)"
    ((PASS++))
  else
    echo -e "${YELLOW}OPTIONAL${NC}  → $install_hint"
    ((WARN++))
  fi
}

echo "============================================"
echo " sandoc 의존성 확인"
echo "============================================"
echo ""

echo "[ 필수 도구 ]"
check "uv (Python runner)" "uv" "curl -LsSf https://astral.sh/uv/install.sh | sh"
check "Claude Code" "claude" "npm install -g @anthropic-ai/claude-code"
check "npx (Node.js)" "npx" "https://nodejs.org/ 에서 Node.js 설치"
echo ""

echo "[ MCP 서버 실행 확인 ]"
printf "%-25s" "hwpx-mcp-server"
if uvx hwpx-mcp-server --help &>/dev/null 2>&1; then
  echo -e "${GREEN}OK${NC}"
  ((PASS++))
else
  echo -e "${YELLOW}WARN${NC}  → 첫 실행 시 자동 설치됩니다 (uvx hwpx-mcp-server)"
  ((WARN++))
fi
echo ""

echo "[ 선택 도구 ]"
check_optional "git" "git" "https://git-scm.com/"
check_optional "gh (GitHub CLI)" "gh" "brew install gh"
echo ""

echo "============================================"
echo -e " 결과: ${GREEN}${PASS} 통과${NC} / ${RED}${FAIL} 실패${NC} / ${YELLOW}${WARN} 선택${NC}"
echo "============================================"

if [ "$FAIL" -gt 0 ]; then
  echo ""
  echo -e "${RED}필수 도구가 누락되었습니다. 위 안내에 따라 설치해주세요.${NC}"
  exit 1
else
  echo ""
  echo -e "${GREEN}sandoc 실행 준비 완료!${NC}"
  exit 0
fi
