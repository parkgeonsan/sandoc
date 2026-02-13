"""
sandoc.interview — 인터랙티브 정보 수집 (Interactive Info Collection)

missing_info.json 을 읽어서:
  - 누락 필드를 논리 카테고리별로 그룹핑
  - 구조화된 설문지 마크다운 생성 (questionnaire.md)
  - 작성 가능한 JSON 템플릿 생성 (company_info_template.json)
  - --fill 옵션으로 answers.json 을 context.json 에 병합
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── 필드 메타데이터: 카테고리, 한국어 이름, 설명, 예시 ─────────────

FIELD_METADATA: dict[str, dict[str, str]] = {
    # 기업정보
    "company_name": {
        "category": "기업정보",
        "label": "기업명",
        "description": "법인명 또는 상호명 (정식 명칭)",
        "example": "(주)스마트팜테크",
    },
    "ceo_name": {
        "category": "기업정보",
        "label": "대표자명",
        "description": "대표이사 성명",
        "example": "김창업",
    },
    "business_registration_no": {
        "category": "기업정보",
        "label": "사업자등록번호",
        "description": "사업자등록증 상의 번호",
        "example": "123-45-67890",
    },
    "business_type": {
        "category": "기업정보",
        "label": "사업자구분",
        "description": "개인사업자 또는 법인사업자",
        "example": "법인사업자",
    },
    "ceo_type": {
        "category": "기업정보",
        "label": "대표자유형",
        "description": "창업자 또는 공동창업자",
        "example": "창업자",
    },
    "establishment_date": {
        "category": "기업정보",
        "label": "설립일(개업연월일)",
        "description": "사업자등록증 상의 개업연월일",
        "example": "2021-06-15",
    },
    "employee_count": {
        "category": "기업정보",
        "label": "직원 수",
        "description": "현재 재직 인원 수",
        "example": "12",
    },
    "address": {
        "category": "기업정보",
        "label": "소재지",
        "description": "기업 주소 (본사 소재지)",
        "example": "서울특별시 강남구 테헤란로 123, 4층",
    },
    # 아이템정보
    "item_name": {
        "category": "아이템정보",
        "label": "창업아이템명",
        "description": "지원 대상 창업아이템 이름",
        "example": "AI 기반 스마트팜 환경 자동제어 시스템",
    },
    "item_category": {
        "category": "아이템정보",
        "label": "아이템 범주/분야",
        "description": "아이템이 속하는 산업 분야",
        "example": "농업 IoT / AI",
    },
    "support_field": {
        "category": "아이템정보",
        "label": "지원분야",
        "description": "공고에 명시된 지원 분야",
        "example": "정보통신",
    },
    "tech_field": {
        "category": "아이템정보",
        "label": "전문기술분야",
        "description": "핵심 기술 분야",
        "example": "인공지능(AI)",
    },
    "item_summary": {
        "category": "아이템정보",
        "label": "아이템 개요",
        "description": "창업아이템 한 줄 요약 (50자 내외)",
        "example": "딥러닝 기반 작물 생육환경 분석 및 자동 제어 시스템",
    },
    "product_description": {
        "category": "아이템정보",
        "label": "제품/서비스 상세 설명",
        "description": "제품 또는 서비스에 대한 상세 설명 (100~300자)",
        "example": "IoT 센서 네트워크와 AI 예측 모델을 결합한 스마트팜 솔루션...",
    },
    # 문제인식 / 사업계획
    "problem_background": {
        "category": "사업계획",
        "label": "문제 배경 (외부/내부)",
        "description": "창업아이템과 관련된 시장/사회 문제 배경",
        "example": "국내 시설원예 농가의 80%가 수동 환경제어에 의존...",
    },
    "problem_statement": {
        "category": "사업계획",
        "label": "핵심 문제점",
        "description": "기존 솔루션의 한계와 문제점",
        "example": "기존 스마트팜 솔루션은 고가이며 설치가 복잡하여...",
    },
    "development_motivation": {
        "category": "사업계획",
        "label": "개발 동기",
        "description": "아이템 개발의 동기와 필요성",
        "example": "현장에서 농가의 환경제어 어려움을 직접 목격하고...",
    },
    "progress_to_date": {
        "category": "사업계획",
        "label": "추진 경과",
        "description": "지금까지의 개발/사업화 진행 상황",
        "example": "2021년 프로토타입 → 2022년 실증 → 2023년 양산",
    },
    "target_market": {
        "category": "사업계획",
        "label": "목표 시장",
        "description": "진출 대상 시장과 규모",
        "example": "국내 시설원예 농가 약 52,000호 및 동남아 수출시장",
    },
    "target_customer": {
        "category": "사업계획",
        "label": "목표 고객",
        "description": "주요 타겟 고객층",
        "example": "중소규모 시설원예 농가, 농업법인, 지자체",
    },
    "competitive_advantage": {
        "category": "사업계획",
        "label": "경쟁우위/차별성",
        "description": "경쟁사 대비 핵심 차별점",
        "example": "기존 대비 60% 저렴, 설치 1일, AI 자동 최적화",
    },
    "key_features": {
        "category": "사업계획",
        "label": "핵심 기능/성능",
        "description": "제품의 주요 기능 나열",
        "example": "딥러닝 예측, IoT 통합제어, 모바일 대시보드",
    },
    "competitor_analysis": {
        "category": "사업계획",
        "label": "경쟁사 분석",
        "description": "주요 경쟁사와 비교 분석",
        "example": "A사: 고가/대형전용, B사: 센서만, C사: 한국 데이터 부족",
    },
    "business_model": {
        "category": "사업계획",
        "label": "사업 모델",
        "description": "수익 창출 모델",
        "example": "하드웨어 판매 + SaaS 구독 + 유지보수",
    },
    "growth_strategy": {
        "category": "사업계획",
        "label": "성장 전략",
        "description": "중장기 성장 계획",
        "example": "2025 국내 확대 → 2026 해외 수출 → 2027 플랫폼 연계",
    },
    "marketing_plan": {
        "category": "사업계획",
        "label": "마케팅/판로 전략",
        "description": "마케팅 및 판매 채널 전략",
        "example": "지자체 사업 수주, 전시회, 레퍼런스 마케팅, 제휴",
    },
    "mid_term_roadmap": {
        "category": "사업계획",
        "label": "중장기 로드맵",
        "description": "3~5년 사업 로드맵",
        "example": "2025: 점유율 5% → 2028: 매출 100억",
    },
    "short_term_roadmap": {
        "category": "사업계획",
        "label": "협약기간 로드맵",
        "description": "지원사업 협약기간 내 실행 계획",
        "example": "AI v3 개발 → 양산 최적화 → 해외 실증 → 100농가 확보",
    },
    "deliverables": {
        "category": "사업계획",
        "label": "산출물 목표",
        "description": "사업 완료 시 산출물",
        "example": "AI 모듈 v3.0, 수출형 제품 1종, 실증 보고서",
    },
    # 재무정보
    "funding_amount": {
        "category": "재무정보",
        "label": "신청 금액 (정부지원금)",
        "description": "정부지원금 신청 금액 (원)",
        "example": "200000000",
    },
    "self_funding_cash": {
        "category": "재무정보",
        "label": "자기부담 (현금)",
        "description": "자기부담금 중 현금 (원)",
        "example": "30000000",
    },
    "self_funding_inkind": {
        "category": "재무정보",
        "label": "자기부담 (현물)",
        "description": "자기부담금 중 현물 (원)",
        "example": "55000000",
    },
    "future_funding_plan": {
        "category": "재무정보",
        "label": "향후 자금 조달 계획",
        "description": "투자유치, 대출 등 향후 자금 계획",
        "example": "시리즈 A 30억원, 기술보증기금 융자",
    },
    "budget_items": {
        "category": "재무정보",
        "label": "사업비 항목",
        "description": "비목별 사업비 세부 내역 (JSON 배열)",
        "example": '[{"category":"재료비","description":"부품 구입","amount":50000000,"source":"정부지원"}]',
    },
    "revenue_records": {
        "category": "재무정보",
        "label": "매출 실적",
        "description": "기존 매출 실적 (JSON 배열)",
        "example": '[{"target_market":"시설원예","product_service":"시스템","entry_date":"2023-03","volume":"15대","price":"3000만원","revenue":"4.5억원"}]',
    },
    "projected_revenues": {
        "category": "재무정보",
        "label": "추정 매출",
        "description": "향후 추정 매출 계획 (JSON 배열)",
        "example": '[{"target_market":"시설원예","product_service":"시스템","launch_date":"2025-06","volume":"30대","price":"3000만원","projected_sales":"9억원"}]',
    },
    "milestones": {
        "category": "사업계획",
        "label": "사업 추진 일정",
        "description": "주요 마일스톤 (JSON 배열)",
        "example": '[{"task":"AI 모델 개발","period":"2025.06~08","details":"고도화"}]',
    },
    # 팀 구성
    "ceo_background": {
        "category": "기업정보",
        "label": "대표자 역량/이력",
        "description": "대표자의 주요 경력과 역량",
        "example": "서울대 공학 석사, 삼성SDS 5년, 특허 3건",
    },
    "team_members": {
        "category": "기업정보",
        "label": "팀 구성원",
        "description": "주요 팀원 정보 (JSON 배열)",
        "example": '[{"name":"이개발","position":"CTO","role":"AI 개발","experience":"박사, 8년","employment_type":"기고용"}]',
    },
    "infrastructure": {
        "category": "기업정보",
        "label": "보유 인프라",
        "description": "기업 보유 시설/장비 (JSON 배열)",
        "example": '[{"infra_type":"사무실","description":"본사","location":"서울 강남"}]',
    },
    "ip_portfolio": {
        "category": "기업정보",
        "label": "지식재산권",
        "description": "보유 특허/상표/디자인 (JSON 배열)",
        "example": '[{"ip_type":"특허","name":"AI 제어 방법","registration_no":"10-2345678","registration_date":"2023-05-10"}]',
    },
    "investment_amount": {
        "category": "재무정보",
        "label": "투자유치 금액",
        "description": "투자유치 금액 (가점 대상, 0이면 미해당)",
        "example": "0",
    },
    "investment_date": {
        "category": "재무정보",
        "label": "투자계약일",
        "description": "투자 계약 체결일",
        "example": "",
    },
    "investor_name": {
        "category": "재무정보",
        "label": "투자자명",
        "description": "투자사/투자자 이름",
        "example": "",
    },
}

# 카테고리 표시 순서
CATEGORY_ORDER = ["기업정보", "아이템정보", "재무정보", "사업계획"]


def run_interview(
    project_dir: Path,
    fill_path: Path | None = None,
) -> dict[str, Any]:
    """
    인터랙티브 정보 수집을 실행합니다.

    Args:
        project_dir: 프로젝트 루트 디렉토리
        fill_path: answers.json 경로 (병합 모드)

    Returns:
        {
            "success": bool,
            "mode": "generate" | "fill",
            "questionnaire_path": str | None,
            "template_path": str | None,
            "merged_fields": int,       # fill 모드에서 병합된 필드 수
            "errors": list[str],
        }
    """
    result: dict[str, Any] = {
        "success": False,
        "mode": "fill" if fill_path else "generate",
        "questionnaire_path": None,
        "template_path": None,
        "merged_fields": 0,
        "errors": [],
    }

    # ── fill 모드: answers.json → context.json 병합 ──────────────
    if fill_path:
        return _fill_answers(project_dir, fill_path, result)

    # ── generate 모드: 설문지 + 템플릿 생성 ──────────────────────
    return _generate_questionnaire(project_dir, result)


def _generate_questionnaire(
    project_dir: Path,
    result: dict[str, Any],
) -> dict[str, Any]:
    """missing_info.json 을 읽어 설문지와 JSON 템플릿을 생성합니다."""

    missing_info_path = project_dir / "missing_info.json"
    if not missing_info_path.exists():
        result["errors"].append(
            f"missing_info.json 을 찾을 수 없습니다: {missing_info_path}\n"
            "먼저 'sandoc extract' 를 실행하세요."
        )
        return result

    try:
        missing_data = json.loads(missing_info_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        result["errors"].append(f"missing_info.json 읽기 실패: {e}")
        return result

    missing_fields: list[str] = missing_data.get("missing_fields", [])
    if not missing_fields:
        # 누락 필드가 없음
        result["success"] = True
        return result

    # 카테고리별 그룹핑
    grouped = _group_by_category(missing_fields)

    # 출력 디렉토리
    output_dir = project_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. 설문지 마크다운 생성
    questionnaire = _build_questionnaire_md(
        grouped, missing_data.get("project_name", project_dir.name)
    )
    q_path = output_dir / "questionnaire.md"
    q_path.write_text(questionnaire, encoding="utf-8")
    result["questionnaire_path"] = str(q_path)
    logger.info("설문지 생성: %s", q_path)

    # 2. JSON 템플릿 생성
    template = _build_json_template(grouped)
    t_path = output_dir / "company_info_template.json"
    t_path.write_text(
        json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    result["template_path"] = str(t_path)
    logger.info("JSON 템플릿 생성: %s", t_path)

    result["success"] = True
    return result


def _fill_answers(
    project_dir: Path,
    fill_path: Path,
    result: dict[str, Any],
) -> dict[str, Any]:
    """answers.json 을 context.json 에 병합합니다."""

    context_path = project_dir / "context.json"
    if not context_path.exists():
        result["errors"].append(
            f"context.json 을 찾을 수 없습니다: {context_path}\n"
            "먼저 'sandoc extract' 를 실행하세요."
        )
        return result

    if not fill_path.exists():
        result["errors"].append(f"answers 파일을 찾을 수 없습니다: {fill_path}")
        return result

    try:
        context = json.loads(context_path.read_text(encoding="utf-8"))
        answers = json.loads(fill_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        result["errors"].append(f"JSON 읽기 실패: {e}")
        return result

    # company_info_found 에 answers 병합
    if "company_info_found" not in context:
        context["company_info_found"] = {"from_docs": {}}
    if "from_docs" not in context["company_info_found"]:
        context["company_info_found"]["from_docs"] = {}

    merged_count = 0
    for key, value in answers.items():
        if value is not None and value != "" and value != []:
            context["company_info_found"]["from_docs"][key] = value
            merged_count += 1

    # missing_info 업데이트
    from sandoc.extract import _determine_missing_info

    found_info = context["company_info_found"]["from_docs"]
    context["missing_info"] = _determine_missing_info(found_info)

    # context.json 저장
    context_path.write_text(
        json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # missing_info.json 업데이트
    missing_info_path = project_dir / "missing_info.json"
    missing_info_output = {
        "project_name": context.get("project_name", project_dir.name),
        "missing_fields": context["missing_info"],
        "total_missing": len(context["missing_info"]),
        "instructions": "아래 항목들은 아직 미입력된 필드입니다.",
    }
    missing_info_path.write_text(
        json.dumps(missing_info_output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    result["success"] = True
    result["merged_fields"] = merged_count
    return result


def _group_by_category(fields: list[str]) -> dict[str, list[str]]:
    """필드 목록을 카테고리별로 그룹핑합니다."""
    grouped: dict[str, list[str]] = {}
    for f in fields:
        meta = FIELD_METADATA.get(f, {})
        cat = meta.get("category", "기타")
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(f)

    # 카테고리 순서 정렬
    ordered: dict[str, list[str]] = {}
    for cat in CATEGORY_ORDER:
        if cat in grouped:
            ordered[cat] = grouped.pop(cat)
    # 나머지 (기타 등)
    for cat, fields_list in grouped.items():
        ordered[cat] = fields_list

    return ordered


def _build_questionnaire_md(
    grouped: dict[str, list[str]], project_name: str
) -> str:
    """카테고리별 설문지 마크다운을 생성합니다."""
    lines = [
        f"# 📋 사업계획서 정보 수집 설문지",
        f"",
        f"**프로젝트:** {project_name}",
        f"",
        f"아래 항목들은 문서에서 자동 추출되지 않아 직접 입력이 필요합니다.",
        f"작성 후 `output/company_info_template.json` 파일을 채워서 제출하세요.",
        f"",
        f"---",
        f"",
    ]

    for cat, fields in grouped.items():
        lines.append(f"## {cat}")
        lines.append("")

        for f in fields:
            meta = FIELD_METADATA.get(f, {})
            label = meta.get("label", f)
            desc = meta.get("description", "")
            example = meta.get("example", "")

            lines.append(f"### {label}")
            if desc:
                lines.append(f"  {desc}")
            if example:
                lines.append(f"  - 예시: `{example}`")
            lines.append(f"  - **입력:** ____________________")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def _build_json_template(grouped: dict[str, list[str]]) -> dict[str, Any]:
    """작성 가능한 JSON 템플릿을 생성합니다."""
    template: dict[str, Any] = {}

    for _cat, fields in grouped.items():
        for f in fields:
            meta = FIELD_METADATA.get(f, {})
            # 배열 형태 필드는 빈 배열로
            if meta.get("example", "").startswith("["):
                template[f] = []
            # 숫자 필드
            elif f in (
                "funding_amount",
                "self_funding_cash",
                "self_funding_inkind",
                "employee_count",
                "investment_amount",
            ):
                template[f] = 0
            else:
                template[f] = ""

    # _comments 섹션 추가 (각 필드 설명)
    comments: dict[str, str] = {}
    for _cat, fields in grouped.items():
        for f in fields:
            meta = FIELD_METADATA.get(f, {})
            label = meta.get("label", f)
            desc = meta.get("description", "")
            example = meta.get("example", "")
            comments[f] = f"{label}: {desc} (예: {example})"
    template["_comments"] = comments

    return template
