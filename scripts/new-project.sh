#!/usr/bin/env bash
# sandoc 새 프로젝트 생성 스크립트
# 사용법: bash scripts/new-project.sh "사업명"
#
# 결과: projects/YYYY-사업명/ 아래 표준 폴더 구조 생성

set -euo pipefail

# --- 인자 확인 ---
if [ $# -lt 1 ]; then
  echo "사용법: $0 \"사업명\""
  echo "예시:   $0 \"스마트공장-구축\""
  exit 1
fi

RAW_NAME="$1"
YEAR=$(date +%Y)

# --- 사업명 정규화: 공백→하이픈, 특수문자 제거 ---
SAFE_NAME=$(echo "$RAW_NAME" | \
  sed 's/[[:space:]]/-/g' | \
  sed 's/[^가-힣a-zA-Z0-9_-]//g')

if [ -z "$SAFE_NAME" ]; then
  echo "오류: 유효한 사업명을 입력해주세요."
  exit 1
fi

PROJECT_DIR="projects/${YEAR}-${SAFE_NAME}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
FULL_PATH="${ROOT_DIR}/${PROJECT_DIR}"

# --- 중복 확인 ---
if [ -d "$FULL_PATH" ]; then
  echo "오류: 이미 존재하는 프로젝트입니다 → ${PROJECT_DIR}"
  exit 1
fi

# --- 폴더 생성 ---
echo "프로젝트 생성 중: ${PROJECT_DIR}"

mkdir -p "${FULL_PATH}/docs"
mkdir -p "${FULL_PATH}/output/drafts/current"
mkdir -p "${FULL_PATH}/output/visuals/tables"
mkdir -p "${FULL_PATH}/output/visuals/charts"
mkdir -p "${FULL_PATH}/output/visuals/diagrams"
mkdir -p "${FULL_PATH}/output/visuals/sources"
mkdir -p "${FULL_PATH}/output/visuals/infographics"

# --- context.md 초기화 ---
cat > "${FULL_PATH}/context.md" << EOF
# ${RAW_NAME}

## 상태
- status: created
- phase: 0
- created: $(date +%Y-%m-%d)
- deadline:
- profile:

## 파일 분류
(Phase 1에서 자동 생성)

## 공고 분석
(Phase 2에서 자동 생성)

## 작성 전략
(Phase 3에서 자동 생성)

## 변경 이력
| 일시 | Phase | 변경 내용 |
|------|-------|----------|
| $(date +%Y-%m-%d) | 0 | 프로젝트 생성 |
EOF

echo ""
echo "생성 완료!"
echo ""
echo "  ${PROJECT_DIR}/"
echo "  ├── docs/                 ← 여기에 서류를 넣어주세요"
echo "  ├── output/"
echo "  │   ├── drafts/current/"
echo "  │   └── visuals/"
echo "  │       ├── tables/"
echo "  │       ├── charts/"
echo "  │       ├── diagrams/"
echo "  │       ├── sources/"
echo "  │       └── infographics/"
echo "  └── context.md"
echo ""
echo "다음 단계: docs/ 폴더에 공고문, 양식, 증빙서류를 넣은 후"
echo "           Claude에게 \"서류 넣었어\" 또는 \"분석해줘\"라고 말하세요."
