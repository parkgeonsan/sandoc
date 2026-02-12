#!/usr/bin/env bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# sandoc E2E Demo Script
#
# 사업계획서 자동 생성 전체 파이프라인 데모
# Company Info JSON → Generate → Build → HWPX
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
set -euo pipefail

# ── 색상 정의 ──────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'  # No Color

# ── 경로 설정 ──────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DEMO_OUTPUT="$SCRIPT_DIR/output"
SAMPLE_JSON="$SCRIPT_DIR/sample_company.json"

echo -e "${BOLD}${CYAN}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  sandoc — AI 사업계획서 생성기 E2E 데모"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${NC}"

# ── Step 0: 환경 확인 ─────────────────────────────────────────
echo -e "${BOLD}[0/5] 환경 확인${NC}"
cd "$PROJECT_DIR"

if [ -d ".venv" ]; then
    source .venv/bin/activate 2>/dev/null || true
    echo -e "  ${GREEN}✓${NC} 가상환경 활성화"
fi

if ! python3 -c "import sandoc" 2>/dev/null; then
    echo -e "  ${YELLOW}⚠${NC} sandoc 패키지 설치 중..."
    pip install -e . -q
fi
echo -e "  ${GREEN}✓${NC} sandoc 패키지 확인 완료"
echo ""

# ── Step 1: 출력 디렉토리 준비 ────────────────────────────────
echo -e "${BOLD}[1/5] 출력 디렉토리 준비${NC}"
rm -rf "$DEMO_OUTPUT"
mkdir -p "$DEMO_OUTPUT"
echo -e "  ${GREEN}✓${NC} $DEMO_OUTPUT 생성"
echo ""

# ── Step 2: 샘플 회사 정보 확인 ───────────────────────────────
echo -e "${BOLD}[2/5] 샘플 회사 정보 확인${NC}"
if [ -f "$SAMPLE_JSON" ]; then
    COMPANY_NAME=$(python3 -c "import json; d=json.load(open('$SAMPLE_JSON','r')); print(d['company_name'])")
    ITEM_NAME=$(python3 -c "import json; d=json.load(open('$SAMPLE_JSON','r')); print(d['item_name'])")
    echo -e "  ${GREEN}✓${NC} 회사 정보 파일: $SAMPLE_JSON"
    echo -e "  📋 기업명: ${BOLD}$COMPANY_NAME${NC}"
    echo -e "  📋 아이템: $ITEM_NAME"
else
    echo -e "  ${YELLOW}⚠${NC} sample_company.json 없음 — 내장 샘플 사용"
fi
echo ""

# ── Step 3: 사업계획서 생성 (generate) ─────────────────────────
echo -e "${BOLD}[3/5] 사업계획서 콘텐츠 생성${NC}"
echo -e "  ${BLUE}→${NC} sandoc generate 실행 중..."

if [ -f "$SAMPLE_JSON" ]; then
    python3 -m sandoc generate \
        --company-info "$SAMPLE_JSON" \
        --output "$DEMO_OUTPUT" 2>&1 | sed 's/^/  /'
else
    python3 -m sandoc generate \
        --sample \
        --output "$DEMO_OUTPUT" 2>&1 | sed 's/^/  /'
fi
echo -e "  ${GREEN}✓${NC} 콘텐츠 생성 완료"
echo ""

# ── Step 4: HWPX 빌드 (build) ─────────────────────────────────
echo -e "${BOLD}[4/5] HWPX 문서 빌드${NC}"
echo -e "  ${BLUE}→${NC} sandoc build 실행 중..."

if [ -f "$SAMPLE_JSON" ]; then
    python3 -m sandoc build \
        --company-info "$SAMPLE_JSON" \
        --output "$DEMO_OUTPUT" 2>&1 | sed 's/^/  /'
else
    python3 -m sandoc build \
        --sample \
        --output "$DEMO_OUTPUT" 2>&1 | sed 's/^/  /'
fi
echo -e "  ${GREEN}✓${NC} HWPX 빌드 완료"
echo ""

# ── Step 5: 결과 확인 ─────────────────────────────────────────
echo -e "${BOLD}[5/5] 결과 확인${NC}"
echo ""

# 파일 목록
echo -e "  ${BOLD}📁 생성된 파일:${NC}"
find "$DEMO_OUTPUT" -type f | sort | while read -r f; do
    size=$(du -h "$f" | cut -f1 | xargs)
    relpath="${f#$DEMO_OUTPUT/}"
    echo -e "    $relpath  ${CYAN}($size)${NC}"
done
echo ""

# HWPX 파일 검증
HWPX_FILE=$(find "$DEMO_OUTPUT" -name "*.hwpx" -type f | head -1)
if [ -n "$HWPX_FILE" ]; then
    echo -e "  ${BOLD}🔍 HWPX 검증:${NC}"
    python3 -c "
from sandoc.hwpx_engine import validate_hwpx
v = validate_hwpx('$HWPX_FILE')
print(f\"    유효성: {'✅ 유효' if v['valid'] else '❌ 무효'}\")
print(f\"    파일 수: {v['file_count']}\")
print(f\"    섹션 수: {v['section_count']}\")
if v['errors']:
    for e in v['errors']:
        print(f'    ⚠ {e}')
"
    echo ""
fi

# 섹션별 글자수
if [ -d "$DEMO_OUTPUT/sections" ]; then
    echo -e "  ${BOLD}📊 섹션별 글자수:${NC}"
    for f in "$DEMO_OUTPUT"/sections/*.md; do
        name=$(basename "$f" .md)
        chars=$(wc -m < "$f" | xargs)
        echo -e "    $name: ${chars}자"
    done
    echo ""

    # 총 글자수
    total=$(cat "$DEMO_OUTPUT"/sections/*.md | wc -m | xargs)
    echo -e "  ${BOLD}📊 총 글자수: ${total}자${NC}"
    echo ""
fi

# ── 완료 ──────────────────────────────────────────────────────
echo -e "${BOLD}${GREEN}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ 데모 완료!"
echo ""
echo "  출력 디렉토리: $DEMO_OUTPUT"
if [ -n "${HWPX_FILE:-}" ]; then
echo "  HWPX 파일:     $HWPX_FILE"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${NC}"
