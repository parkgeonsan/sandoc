"""
sandoc.inject — HWP 템플릿 삽입 매핑 (HWP Template Injection Mapping)

원본 HWP 양식(별첨1)에 초안 내용을 매핑하는 파일을 생성합니다:
  - injection_map.json: 섹션-템플릿 매핑 정보
  - injection_instructions.md: Claude Code가 hwpx-mcp로 실제 삽입할 때 사용할 지시서

직접 HWP 편집이 아닌, hwpx-mcp 사용을 위한 지시서 생성 방식입니다.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── 섹션 → 양식 매핑 테이블 (창업도약패키지 기준) ────────────────────

TEMPLATE_SECTION_MAP: list[dict[str, Any]] = [
    {
        "section_key": "company_overview",
        "template_section": "□ 신청 및 일반현황",
        "injection_type": "text_replace",
        "target_markers": [
            "기업명:", "대표자:", "사업자등록번호:", "개업연월일:",
            "소재지:", "직원수:", "창업아이템명:", "지원분야:",
        ],
        "description": "기업 기본 정보와 일반현황 섹션 (표 형태)",
    },
    {
        "section_key": "problem_recognition",
        "template_section": "1. 문제인식 (Problem)",
        "injection_type": "section_content",
        "target_markers": [
            "1. 창업아이템 개발 동기(필요성) 및 현황",
            "2. 핵심 아이템 관련",
        ],
        "description": "문제인식 평가항목 — 개발 동기, 필요성, 현황 서술",
    },
    {
        "section_key": "solution",
        "template_section": "2-1. 목표시장(고객) 분석",
        "injection_type": "section_content",
        "target_markers": [
            "목표시장(고객)",
            "핵심 기능/성능",
            "경쟁사",
            "차별적 경쟁 우위",
        ],
        "description": "목표시장 분석, 경쟁 우위, TAM/SAM/SOM",
    },
    {
        "section_key": "business_model",
        "template_section": "2-2. 사업화 추진 성과",
        "injection_type": "table_and_content",
        "target_markers": [
            "매출 실적",
            "목표시장(고객)",
            "제품·서비스",
            "발생매출액",
        ],
        "description": "매출 실적 표 + 사업화 성과 서술",
    },
    {
        "section_key": "market_analysis",
        "template_section": "3-1. 사업화 추진 전략",
        "injection_type": "section_content",
        "target_markers": [
            "성장 전략",
            "마케팅/판로 전략",
            "사업 추진 일정",
            "추진내용",
            "추진기간",
        ],
        "description": "성장전략, 마케팅, 마일스톤 일정표",
    },
    {
        "section_key": "growth_strategy",
        "template_section": "3-2. 자금운용 계획",
        "injection_type": "table_and_content",
        "target_markers": [
            "사업비 총괄",
            "정부지원사업비",
            "자기부담",
            "비목",
            "산출근거",
            "금액(원)",
        ],
        "description": "사업비 구성 표 + 자금운용 계획 서술",
    },
    {
        "section_key": "team",
        "template_section": "4. 기업 구성 (Team)",
        "injection_type": "table_and_content",
        "target_markers": [
            "대표자 역량",
            "전문 인력 현황",
            "직위",
            "담당업무",
            "보유역량",
            "산업재산권",
            "보유 인프라",
        ],
        "description": "팀 구성, 조직도, 인프라, IP 포트폴리오",
    },
    {
        "section_key": "financial_plan",
        "template_section": "재무 계획 종합",
        "injection_type": "section_content",
        "target_markers": [
            "사업비 구성 검증",
            "투자유치 가점",
        ],
        "description": "재무 분석 종합, 투자유치 가점 정보",
    },
    {
        "section_key": "funding_plan",
        "template_section": "사업비 집행 계획 (상세)",
        "injection_type": "table_and_content",
        "target_markers": [
            "비목별 집행",
            "재료비",
            "인건비",
            "외주용역비",
        ],
        "description": "비목별 상세 집행 계획 표",
    },
]


def run_inject(
    project_dir: Path,
) -> dict[str, Any]:
    """
    HWP 템플릿 삽입 매핑 파일을 생성합니다.

    Args:
        project_dir: 프로젝트 루트 디렉토리

    Returns:
        {
            "success": bool,
            "map_path": str,
            "instructions_path": str,
            "mappings_count": int,
            "errors": list[str],
        }
    """
    result: dict[str, Any] = {
        "success": False,
        "map_path": None,
        "instructions_path": None,
        "mappings_count": 0,
        "errors": [],
    }

    # 초안 디렉토리 확인
    drafts_dir = project_dir / "output" / "drafts" / "current"
    if not drafts_dir.is_dir():
        result["errors"].append(
            f"초안 디렉토리를 찾을 수 없습니다: {drafts_dir}\n"
            "먼저 섹션 초안을 작성하세요."
        )
        return result

    md_files = sorted(drafts_dir.glob("*.md"))
    if not md_files:
        result["errors"].append("초안 마크다운 파일이 없습니다.")
        return result

    # 사용 가능한 초안 파일 매핑
    available_sections: dict[str, Path] = {}
    for md_path in md_files:
        section_key = re.sub(r"^\d+_", "", md_path.stem)
        available_sections[section_key] = md_path

    # context.json 에서 양식 정보 읽기
    context_path = project_dir / "context.json"
    template_info: dict[str, Any] = {}
    if context_path.exists():
        try:
            ctx = json.loads(context_path.read_text(encoding="utf-8"))
            template_info = ctx.get("template_analysis", {}) or {}
        except (json.JSONDecodeError, OSError):
            pass

    # 출력 디렉토리
    output_dir = project_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── injection_map.json 생성 ──────────────────────────────────
    mappings = _build_injection_map(available_sections, template_info)
    map_data = {
        "project": project_dir.name,
        "template_file": template_info.get("file", "양식.hwp"),
        "total_mappings": len(mappings),
        "mappings": mappings,
    }

    map_path = output_dir / "injection_map.json"
    map_path.write_text(
        json.dumps(map_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    result["map_path"] = str(map_path)

    # ── injection_instructions.md 생성 ───────────────────────────
    instructions = _build_injection_instructions(
        mappings, project_dir.name,
        template_info.get("file", "양식.hwp"),
    )
    instr_path = output_dir / "injection_instructions.md"
    instr_path.write_text(instructions, encoding="utf-8")
    result["instructions_path"] = str(instr_path)

    result["success"] = True
    result["mappings_count"] = len(mappings)
    return result


def _build_injection_map(
    available_sections: dict[str, Path],
    template_info: dict[str, Any],
) -> list[dict[str, Any]]:
    """초안 ↔ 양식 매핑 목록을 생성합니다."""
    mappings: list[dict[str, Any]] = []

    # 양식 섹션 제목 목록 (있으면 활용)
    template_sections: list[str] = []
    if template_info.get("sections"):
        template_sections = [s.get("title", "") for s in template_info["sections"]]

    for tmpl in TEMPLATE_SECTION_MAP:
        section_key = tmpl["section_key"]
        if section_key not in available_sections:
            continue

        draft_path = available_sections[section_key]
        mapping: dict[str, Any] = {
            "template_section": tmpl["template_section"],
            "draft_file": draft_path.name,
            "section_key": section_key,
            "injection_type": tmpl["injection_type"],
            "target_markers": tmpl["target_markers"],
            "description": tmpl["description"],
        }

        # 양식에서 매칭되는 섹션 찾기
        matched_template_section = None
        for ts in template_sections:
            if _section_title_match(tmpl["template_section"], ts):
                matched_template_section = ts
                break

        if matched_template_section:
            mapping["matched_in_template"] = matched_template_section

        mappings.append(mapping)

    return mappings


def _section_title_match(expected: str, actual: str) -> bool:
    """양식 섹션 제목이 매칭되는지 확인합니다."""
    # 공백, 특수문자 제거 후 비교
    norm_expected = re.sub(r"[\s□■◆●○]", "", expected)
    norm_actual = re.sub(r"[\s□■◆●○]", "", actual)

    # 부분 매칭
    if norm_expected in norm_actual or norm_actual in norm_expected:
        return True

    # 키워드 매칭
    keywords = re.findall(r"[가-힣]+", expected)
    if keywords:
        matches = sum(1 for kw in keywords if kw in actual)
        return matches >= len(keywords) // 2

    return False


def _build_injection_instructions(
    mappings: list[dict[str, Any]],
    project_name: str,
    template_file: str,
) -> str:
    """Claude Code 용 삽입 지시서를 생성합니다."""
    lines = [
        "# 📝 HWP 템플릿 삽입 지시서",
        "",
        f"**프로젝트:** {project_name}",
        f"**대상 양식:** {template_file}",
        f"**총 매핑 수:** {len(mappings)}개",
        "",
        "---",
        "",
        "## 사전 요구사항",
        "",
        "1. `hwpx-mcp` MCP 서버가 실행 중이어야 합니다",
        "2. 원본 HWP 양식 파일이 프로젝트 `docs/` 폴더에 있어야 합니다",
        "3. 아래 매핑을 순서대로 처리하세요",
        "",
        "---",
        "",
        "## 삽입 절차",
        "",
    ]

    for i, mapping in enumerate(mappings, 1):
        lines.append(f"### {i}. {mapping['template_section']}")
        lines.append("")
        lines.append(f"- **초안 파일:** `output/drafts/current/{mapping['draft_file']}`")
        lines.append(f"- **삽입 유형:** `{mapping['injection_type']}`")
        lines.append(f"- **설명:** {mapping['description']}")
        lines.append("")

        # 삽입 유형별 상세 지시
        injection_type = mapping["injection_type"]
        markers = mapping["target_markers"]

        if injection_type == "text_replace":
            lines.append("**작업 절차:**")
            lines.append("```")
            lines.append(f"1. hwpx-mcp로 양식에서 '{mapping['template_section']}' 섹션을 찾습니다")
            lines.append("2. 다음 마커 위치의 텍스트를 초안 파일의 해당 값으로 교체합니다:")
            for marker in markers:
                lines.append(f"   - {marker} → (초안에서 추출)")
            lines.append("```")
        elif injection_type == "section_content":
            lines.append("**작업 절차:**")
            lines.append("```")
            lines.append(f"1. hwpx-mcp로 양식에서 '{mapping['template_section']}' 섹션을 찾습니다")
            lines.append("2. 해당 섹션의 빈 영역에 초안 파일의 내용을 삽입합니다")
            lines.append("3. 양식의 서식(폰트, 크기, 줄간격)을 유지합니다")
            lines.append("4. 다음 하위 항목을 순서대로 배치합니다:")
            for marker in markers:
                lines.append(f"   - {marker}")
            lines.append("```")
        elif injection_type == "table_and_content":
            lines.append("**작업 절차:**")
            lines.append("```")
            lines.append(f"1. hwpx-mcp로 양식에서 '{mapping['template_section']}' 섹션을 찾습니다")
            lines.append("2. 표 데이터를 먼저 삽입합니다 (마크다운 표 → HWP 표)")
            lines.append("3. 표 아래/위의 서술 내용을 삽입합니다")
            lines.append("4. 다음 필드를 포함해야 합니다:")
            for marker in markers:
                lines.append(f"   - {marker}")
            lines.append("```")

        lines.append("")
        lines.append("---")
        lines.append("")

    # 마무리 확인사항
    lines.extend([
        "## 마무리 확인사항",
        "",
        "- [ ] 모든 섹션이 올바른 위치에 삽입되었는지 확인",
        "- [ ] 양식의 서식(폰트, 크기, 줄간격)이 유지되는지 확인",
        "- [ ] 표의 행/열이 올바르게 채워졌는지 확인",
        "- [ ] 빈 필드가 없는지 확인",
        "- [ ] 페이지 넘침이 없는지 확인",
        "- [ ] 최종 HWPX 파일을 한글(HWP)에서 열어 육안 검토",
        "",
        f"> 이 지시서는 `sandoc inject {project_name}` 으로 자동 생성되었습니다.",
    ])

    return "\n".join(lines)
