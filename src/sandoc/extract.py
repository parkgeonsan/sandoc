"""
sandoc.extract — 프로젝트 폴더에서 모든 정보 추출

docs/ 하위 폴더의 모든 문서를 스캔하여:
  - 문서 분류 (공고문/양식/참고/증빙)
  - HWP 양식 분석 (섹션, 표, 입력필드)
  - PDF 공고문 분석 (평가기준, 주요일정)
  - HWP 스타일 프로파일 추출

결과를 context.json 과 missing_info.json 으로 출력합니다.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sandoc.analyzer import (
    analyze_announcement,
    analyze_template,
    classify_documents,
    ClassifiedDocument,
)
from sandoc.style import extract_style_profile

logger = logging.getLogger(__name__)

# 회사 정보로 필요한 필수 항목들 (missing_info 판별용)
REQUIRED_COMPANY_FIELDS = [
    "company_name",
    "ceo_name",
    "business_registration_no",
    "establishment_date",
    "employee_count",
    "address",
    "item_name",
    "item_summary",
    "product_description",
    "problem_background",
    "problem_statement",
    "development_motivation",
    "target_market",
    "target_customer",
    "competitive_advantage",
    "key_features",
    "business_model",
    "growth_strategy",
    "marketing_plan",
    "funding_amount",
    "self_funding_cash",
    "ceo_background",
    "team_members",
    "budget_items",
]


def run_extract(project_dir: Path) -> dict[str, Any]:
    """
    프로젝트 폴더에서 모든 정보를 추출합니다.

    Args:
        project_dir: 프로젝트 루트 디렉토리 (docs/ 하위 폴더 필요)

    Returns:
        {
            "context": { ... context.json 내용 },
            "missing_info": { ... missing_info.json 내용 },
            "style_profile_data": { ... } or None,
        }
    """
    docs_dir = project_dir / "docs"
    if not docs_dir.is_dir():
        # docs/ 폴더가 없으면 프로젝트 루트 자체를 스캔
        docs_dir = project_dir

    context: dict[str, Any] = {
        "project_name": project_dir.name,
        "documents": [],
        "template_analysis": None,
        "announcement_analysis": None,
        "style_profile": None,
        "company_info_found": {"from_docs": {}},
        "missing_info": [],
    }

    style_profile_data: dict[str, Any] | None = None

    # ── 1. 문서 분류 ────────────────────────────────────────────
    logger.info("문서 분류 중: %s", docs_dir)
    try:
        classified = classify_documents(docs_dir)
    except ValueError:
        classified = []

    for doc in classified:
        context["documents"].append({
            "file": doc.filename,
            "category": doc.category,
            "confidence": doc.confidence,
        })

    # 카테고리별 그룹핑
    by_category: dict[str, list[ClassifiedDocument]] = {}
    for doc in classified:
        cat = doc.category
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(doc)

    # ── 2. 양식(HWP) 분석 ──────────────────────────────────────
    template_docs = by_category.get("양식", [])
    hwp_templates = [d for d in template_docs if d.extension == ".hwp"]

    if hwp_templates:
        # 첫 번째(가장 신뢰도 높은) HWP 양식 분석
        best_template = max(hwp_templates, key=lambda d: d.confidence)
        logger.info("양식 분석 중: %s", best_template.filename)

        try:
            ta = analyze_template(best_template.file_path)
            context["template_analysis"] = {
                "file": best_template.filename,
                "sections": [
                    {"title": s.title, "level": s.level}
                    for s in ta.sections
                ],
                "tables_count": ta.tables_count,
                "input_fields": ta.input_fields,
                "total_paragraphs": ta.total_paragraphs,
            }
        except Exception as e:
            logger.warning("양식 분석 실패: %s — %s", best_template.filename, e)

        # ── 3. 스타일 프로파일 추출 ────────────────────────────
        logger.info("스타일 프로파일 추출 중: %s", best_template.filename)
        try:
            profile = extract_style_profile(best_template.file_path)
            context["style_profile"] = "style-profile.json"
            style_profile_data = profile.to_dict()
        except Exception as e:
            logger.warning("스타일 프로파일 추출 실패: %s", e)

    # ── 4. 공고문(PDF) 분석 ────────────────────────────────────
    announcement_docs = by_category.get("공고문", [])
    pdf_announcements = [d for d in announcement_docs if d.extension == ".pdf"]

    if pdf_announcements:
        best_announcement = max(pdf_announcements, key=lambda d: d.confidence)
        logger.info("공고문 분석 중: %s", best_announcement.filename)

        try:
            aa = analyze_announcement(best_announcement.file_path)
            context["announcement_analysis"] = {
                "file": best_announcement.filename,
                "title": aa.title,
                "scoring_criteria": [
                    {"category": c.category, "item": c.item, "score": c.score}
                    for c in aa.scoring_criteria
                ],
                "key_dates": aa.key_dates,
                "eligibility": aa.eligibility,
                "requirements": aa.eligibility,  # alias
                "total_pages": aa.total_pages,
            }
        except Exception as e:
            logger.warning("공고문 분석 실패: %s — %s", best_announcement.filename, e)

    # ── 5. 누락 정보 판별 ──────────────────────────────────────
    found_info = context["company_info_found"]["from_docs"]
    missing = _determine_missing_info(found_info)
    context["missing_info"] = missing

    # ── 결과 반환 ──────────────────────────────────────────────
    missing_info_output = {
        "project_name": context["project_name"],
        "missing_fields": missing,
        "total_missing": len(missing),
        "instructions": (
            "아래 항목들은 문서에서 자동 추출되지 않았습니다. "
            "사용자에게 직접 확인이 필요합니다."
        ),
    }

    return {
        "context": context,
        "missing_info": missing_info_output,
        "style_profile_data": style_profile_data,
    }


def _determine_missing_info(found_info: dict[str, Any]) -> list[str]:
    """문서에서 추출된 정보와 필수 항목을 비교하여 누락 목록을 반환합니다."""
    missing = []
    for field_name in REQUIRED_COMPANY_FIELDS:
        value = found_info.get(field_name)
        if value is None or value == "" or value == [] or value == 0:
            missing.append(field_name)
    return missing
