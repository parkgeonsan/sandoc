#!/usr/bin/env bash
# scan-docs.sh — docs/ 디렉토리 내 문서 파일 목록과 정보를 출력한다.
# 용도: 프로젝트 문서 현황 파악
# 사용법: ./scripts/scan-docs.sh [docs_dir]

set -euo pipefail

# ── 색상 정의 ──────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'  # No Color

# ── 인자 처리 ──────────────────────────────────────────────
DOCS_DIR="${1:-docs}"

if [ ! -d "$DOCS_DIR" ]; then
    echo -e "${RED}오류: '$DOCS_DIR' 디렉토리가 존재하지 않습니다.${NC}"
    echo ""
    echo "사용법: $0 [docs_directory]"
    echo "  기본값: docs/"
    exit 1
fi

# ── 유틸리티 함수 ──────────────────────────────────────────
human_size() {
    local bytes=$1
    if [ "$bytes" -ge 1073741824 ]; then
        echo "$(echo "scale=1; $bytes / 1073741824" | bc)GB"
    elif [ "$bytes" -ge 1048576 ]; then
        echo "$(echo "scale=1; $bytes / 1048576" | bc)MB"
    elif [ "$bytes" -ge 1024 ]; then
        echo "$(echo "scale=1; $bytes / 1024" | bc)KB"
    else
        echo "${bytes}B"
    fi
}

get_file_type() {
    local ext="${1##*.}"
    ext=$(echo "$ext" | tr '[:upper:]' '[:lower:]')
    case "$ext" in
        hwp)   echo "HWP (한글)" ;;
        hwpx)  echo "HWPX (한글 XML)" ;;
        doc)   echo "DOC (Word 97-03)" ;;
        docx)  echo "DOCX (Word)" ;;
        pdf)   echo "PDF" ;;
        ppt)   echo "PPT (PowerPoint 97-03)" ;;
        pptx)  echo "PPTX (PowerPoint)" ;;
        xls)   echo "XLS (Excel 97-03)" ;;
        xlsx)  echo "XLSX (Excel)" ;;
        txt)   echo "TXT (텍스트)" ;;
        csv)   echo "CSV (콤마 구분)" ;;
        png)   echo "PNG (이미지)" ;;
        jpg|jpeg) echo "JPG (이미지)" ;;
        gif)   echo "GIF (이미지)" ;;
        bmp)   echo "BMP (이미지)" ;;
        zip)   echo "ZIP (압축)" ;;
        *)     echo "$ext (기타)" ;;
    esac
}

# ── 스캔 시작 ──────────────────────────────────────────────
echo ""
echo -e "${BOLD}📂 문서 스캔 결과: ${CYAN}${DOCS_DIR}/${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 파일 수집
total_count=0
total_size=0

declare -A ext_count
declare -A ext_size

# 파일 목록 출력
echo -e "${BOLD}📄 파일 목록${NC}"
echo "──────────────────────────────────────────────────"
printf "%-50s %10s  %s\n" "파일명" "크기" "유형"
echo "──────────────────────────────────────────────────"

while IFS= read -r -d '' file; do
    filename=$(basename "$file")
    relpath="${file#$DOCS_DIR/}"
    filesize=$(stat -f%z "$file" 2>/dev/null || stat --format=%s "$file" 2>/dev/null || echo 0)
    filetype=$(get_file_type "$filename")
    human=$(human_size "$filesize")

    # 확장자 통계
    ext="${filename##*.}"
    ext=$(echo "$ext" | tr '[:upper:]' '[:lower:]')
    ext_count[$ext]=$(( ${ext_count[$ext]:-0} + 1 ))
    ext_size[$ext]=$(( ${ext_size[$ext]:-0} + filesize ))

    total_count=$((total_count + 1))
    total_size=$((total_size + filesize))

    # 파일명이 길면 잘라내기
    if [ ${#relpath} -gt 48 ]; then
        display_name="...${relpath: -45}"
    else
        display_name="$relpath"
    fi

    printf "%-50s %10s  %s\n" "$display_name" "$human" "$filetype"

done < <(find "$DOCS_DIR" -type f -not -name '.*' -not -path '*/\.*' -print0 | sort -z)

if [ "$total_count" -eq 0 ]; then
    echo -e "  ${YELLOW}(파일 없음)${NC}"
fi

# ── 요약 통계 ──────────────────────────────────────────────
echo ""
echo -e "${BOLD}📊 유형별 통계${NC}"
echo "──────────────────────────────────────────────────"
printf "%-20s %8s %12s\n" "확장자" "파일 수" "총 크기"
echo "──────────────────────────────────────────────────"

for ext in $(echo "${!ext_count[@]}" | tr ' ' '\n' | sort); do
    count=${ext_count[$ext]}
    size=${ext_size[$ext]}
    human=$(human_size "$size")
    printf "%-20s %8d %12s\n" ".$ext" "$count" "$human"
done

echo "──────────────────────────────────────────────────"
printf "${BOLD}%-20s %8d %12s${NC}\n" "합계" "$total_count" "$(human_size $total_size)"

# ── 디렉토리 구조 ─────────────────────────────────────────
echo ""
echo -e "${BOLD}📁 디렉토리 구조${NC}"
echo "──────────────────────────────────────────────────"

dir_count=0
while IFS= read -r -d '' dir; do
    reldir="${dir#$DOCS_DIR}"
    if [ -z "$reldir" ]; then
        reldir="/"
    fi
    file_count=$(find "$dir" -maxdepth 1 -type f -not -name '.*' 2>/dev/null | wc -l | tr -d ' ')
    echo -e "  ${BLUE}${reldir}/${NC} — ${file_count}개 파일"
    dir_count=$((dir_count + 1))
done < <(find "$DOCS_DIR" -type d -not -name '.*' -print0 | sort -z)

# ── 최종 요약 ──────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BOLD}요약:${NC} ${GREEN}${total_count}${NC}개 파일, ${GREEN}${dir_count}${NC}개 디렉토리, 총 ${GREEN}$(human_size $total_size)${NC}"
echo ""
