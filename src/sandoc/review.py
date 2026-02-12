"""
sandoc.review -- 사업계획서 자가 검토 및 점수 평가

초안 섹션을 분석하여:
  - 필수 섹션 존재 여부 확인
  - 섹션별 최소 분량 검증 (500자)
  - 재무 데이터 일관성 검증
  - 필수 요소 포함 여부 (문제→솔루션→시장→팀)
  - 사업비 합계 일치 여부
  - 섹션별 예상 점수 및 종합 준비도 평가
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── 평가 기준 ─────────────────────────────────────────────────

REQUIRED_SECTIONS = [
    "company_overview",
    "problem_recognition",
    "solution",
    "business_model",
    "market_analysis",
    "growth_strategy",
    "team",
    "financial_plan",
    "funding_plan",
]

# 평가항목 매핑
EVAL_CATEGORIES = {
    "문제인식": {
        "sections": ["problem_recognition"],
        "max_score": 25,
        "required_keywords": [
            "문제", "필요성", "동기", "배경", "현황", "현재", "기존",
            "한계", "어려움", "불편", "개발 동기",
        ],
        "description": "창업아이템 개발 동기(필요성) 및 현황",
    },
    "실현가능성": {
        "sections": ["solution", "business_model"],
        "max_score": 25,
        "required_keywords": [
            "목표시장", "고객", "경쟁", "차별", "우위", "기능", "성능",
            "매출", "실적", "특허", "인증",
        ],
        "description": "창업아이템 목표시장(고객) 분석, 시장진입 현황",
    },
    "성장전략": {
        "sections": ["market_analysis", "growth_strategy", "financial_plan", "funding_plan"],
        "max_score": 25,
        "required_keywords": [
            "전략", "마케팅", "판로", "매출", "계획", "추정", "추진",
            "사업비", "자금", "로드맵", "일정",
        ],
        "description": "사업화 추진 전략 및 자금 운용 계획",
    },
    "팀구성": {
        "sections": ["team"],
        "max_score": 25,
        "required_keywords": [
            "대표", "인력", "경력", "역량", "팀", "인프라", "장비",
            "특허", "기술", "채용",
        ],
        "description": "기업 구성 및 보유 역량, 보유 인프라 활용 계획",
    },
}

MIN_CHARS_PER_SECTION = 500  # 최소 500자


# ── 검증 함수 ─────────────────────────────────────────────────

def _check_sections_present(sections: dict[str, str]) -> tuple[list[str], list[str]]:
    """필수 섹션 존재 여부 확인. (present, missing) 반환."""
    present = [s for s in REQUIRED_SECTIONS if s in sections]
    missing = [s for s in REQUIRED_SECTIONS if s not in sections]
    return present, missing


def _check_word_count(sections: dict[str, str]) -> dict[str, dict[str, Any]]:
    """섹션별 글자 수 확인."""
    results: dict[str, dict[str, Any]] = {}
    for key, text in sections.items():
        char_count = len(text.strip())
        results[key] = {
            "chars": char_count,
            "sufficient": char_count >= MIN_CHARS_PER_SECTION,
            "min_required": MIN_CHARS_PER_SECTION,
        }
    return results


def _check_keywords(sections: dict[str, str]) -> dict[str, dict[str, Any]]:
    """평가 카테고리별 필수 키워드 포함 여부 확인."""
    results: dict[str, dict[str, Any]] = {}

    for category, criteria in EVAL_CATEGORIES.items():
        combined_text = ""
        for section_key in criteria["sections"]:
            combined_text += sections.get(section_key, "")

        found_keywords = []
        missing_keywords = []
        for kw in criteria["required_keywords"]:
            if kw in combined_text:
                found_keywords.append(kw)
            else:
                missing_keywords.append(kw)

        coverage = len(found_keywords) / len(criteria["required_keywords"]) if criteria["required_keywords"] else 0

        results[category] = {
            "found": found_keywords,
            "missing": missing_keywords,
            "coverage": coverage,
            "description": criteria["description"],
        }

    return results


def _extract_financial_numbers(text: str) -> dict[str, int]:
    """텍스트에서 사업비 관련 금액 추출."""
    numbers: dict[str, int] = {}

    # 총사업비
    m = re.search(r"총사업비[^0-9]*?(\d{1,3}(?:,\d{3})+)", text)
    if m:
        numbers["총사업비"] = int(m.group(1).replace(",", ""))

    # 정부지원금
    m = re.search(r"정부지원(?:금|사업비)[^0-9]*?(\d{1,3}(?:,\d{3})+)", text)
    if m:
        numbers["정부지원금"] = int(m.group(1).replace(",", ""))

    # 자기부담(현금)
    m = re.search(r"자기부담\(현금\)[^0-9]*?(\d{1,3}(?:,\d{3})+)", text)
    if m:
        numbers["자기부담현금"] = int(m.group(1).replace(",", ""))

    # 자기부담(현물)
    m = re.search(r"자기부담\(현물\)[^0-9]*?(\d{1,3}(?:,\d{3})+)", text)
    if m:
        numbers["자기부담현물"] = int(m.group(1).replace(",", ""))

    return numbers


def _check_financial_consistency(sections: dict[str, str]) -> dict[str, Any]:
    """재무 데이터 일관성 검증."""
    result: dict[str, Any] = {
        "consistent": True,
        "issues": [],
        "data_found": {},
    }

    # 여러 섹션에서 사업비 데이터 수집
    all_financial: list[dict[str, int]] = []
    for key in ["company_overview", "growth_strategy", "financial_plan", "funding_plan"]:
        text = sections.get(key, "")
        if text:
            data = _extract_financial_numbers(text)
            if data:
                all_financial.append(data)
                result["data_found"][key] = data

    if not all_financial:
        result["issues"].append("사업비 관련 수치가 발견되지 않았습니다.")
        result["consistent"] = False
        return result

    # 총사업비 = 정부지원 + 현금 + 현물 확인
    for key, data in result["data_found"].items():
        total = data.get("총사업비", 0)
        gov = data.get("정부지원금", 0)
        cash = data.get("자기부담현금", 0)
        inkind = data.get("자기부담현물", 0)

        if total > 0 and (gov + cash + inkind) > 0:
            calculated = gov + cash + inkind
            if abs(total - calculated) > 1000:  # 1,000원 이상 차이
                result["consistent"] = False
                result["issues"].append(
                    f"[{key}] 총사업비({total:,}) != 정부지원({gov:,}) + "
                    f"현금({cash:,}) + 현물({inkind:,}) = {calculated:,}"
                )

    # 비율 검증
    for key, data in result["data_found"].items():
        total = data.get("총사업비", 0)
        gov = data.get("정부지원금", 0)
        cash = data.get("자기부담현금", 0)
        inkind = data.get("자기부담현물", 0)

        if total > 0:
            gov_ratio = gov / total * 100 if total else 0
            cash_ratio = cash / total * 100 if total else 0
            inkind_ratio = inkind / total * 100 if total else 0

            if gov_ratio > 70:
                result["issues"].append(
                    f"[{key}] 정부지원 비율 {gov_ratio:.1f}% > 70% (초과)"
                )
            if cash_ratio < 10 and cash > 0:
                result["issues"].append(
                    f"[{key}] 현금 부담 비율 {cash_ratio:.1f}% < 10% (부족)"
                )
            if inkind_ratio > 20:
                result["issues"].append(
                    f"[{key}] 현물 부담 비율 {inkind_ratio:.1f}% > 20% (초과)"
                )

    # 섹션 간 수치 불일치 확인
    totals = set()
    for data in all_financial:
        t = data.get("총사업비", 0)
        if t > 0:
            totals.add(t)
    if len(totals) > 1:
        result["consistent"] = False
        result["issues"].append(
            f"섹션 간 총사업비 불일치: {', '.join(f'{t:,}' for t in totals)}"
        )

    return result


def _estimate_section_score(
    section_key: str,
    text: str,
    keyword_results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """섹션별 예상 점수 계산."""
    char_count = len(text.strip())
    sufficient = char_count >= MIN_CHARS_PER_SECTION

    # 어떤 평가 카테고리에 속하는지 찾기
    eval_category = None
    for category, criteria in EVAL_CATEGORIES.items():
        if section_key in criteria["sections"]:
            eval_category = category
            break

    base_score = 0
    max_score = 25 if eval_category else 0

    if eval_category:
        kw_data = keyword_results.get(eval_category, {})
        coverage = kw_data.get("coverage", 0)

        # 분량 점수 (30%)
        length_score = min(char_count / 2000, 1.0) * 0.3 * max_score

        # 키워드 커버리지 점수 (40%)
        keyword_score = coverage * 0.4 * max_score

        # 구조 점수 (30%) - 서브헤딩, 표, 목록 포함 여부
        structure_score = 0
        if "◦" in text or "○" in text:
            structure_score += 0.1 * max_score
        if "|" in text and "---" in text:  # 표
            structure_score += 0.1 * max_score
        if any(ch in text for ch in ["①", "②", "1.", "2."]):
            structure_score += 0.1 * max_score

        base_score = length_score + keyword_score + structure_score

    return {
        "chars": char_count,
        "sufficient": sufficient,
        "eval_category": eval_category or "N/A",
        "estimated_score": round(min(base_score, max_score), 1),
        "max_score": max_score,
    }


# ── 리포트 생성 ──────────────────────────────────────────────

def _generate_review_markdown(
    present_sections: list[str],
    missing_sections: list[str],
    word_counts: dict[str, dict[str, Any]],
    keyword_results: dict[str, dict[str, Any]],
    financial: dict[str, Any],
    section_scores: dict[str, dict[str, Any]],
    overall_score: float,
) -> str:
    """리뷰 결과를 마크다운으로 생성."""
    lines: list[str] = []

    lines.append("# 사업계획서 자가 검토 보고서")
    lines.append("")
    lines.append(f"**종합 준비도: {overall_score:.0f}/100점**")
    lines.append("")

    # 준비도 등급
    if overall_score >= 80:
        grade = "A (우수)"
        comment = "제출 준비가 잘 되어 있습니다. 세부 보완 후 제출하세요."
    elif overall_score >= 60:
        grade = "B (보통)"
        comment = "핵심 항목은 갖추었으나 보완이 필요한 영역이 있습니다."
    elif overall_score >= 40:
        grade = "C (미흡)"
        comment = "여러 항목에서 보완이 필요합니다. 아래 개선 사항을 참고하세요."
    else:
        grade = "D (부족)"
        comment = "상당한 보완이 필요합니다. 섹션별 가이드를 참고하여 재작성하세요."

    lines.append(f"**등급: {grade}**")
    lines.append(f"> {comment}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 1. 섹션 현황
    lines.append("## 1. 섹션 현황")
    lines.append("")
    lines.append(f"- 작성된 섹션: {len(present_sections)}/{len(REQUIRED_SECTIONS)}")
    if missing_sections:
        lines.append(f"- **누락 섹션:** {', '.join(missing_sections)}")
    else:
        lines.append("- 모든 필수 섹션이 작성되었습니다.")
    lines.append("")

    # 2. 분량 검사
    lines.append("## 2. 분량 검사 (최소 500자)")
    lines.append("")
    lines.append("| 섹션 | 글자 수 | 판정 |")
    lines.append("|------|---------|------|")
    for key in REQUIRED_SECTIONS:
        if key in word_counts:
            wc = word_counts[key]
            status = "충분" if wc["sufficient"] else "**부족**"
            lines.append(f"| {key} | {wc['chars']:,}자 | {status} |")
        else:
            lines.append(f"| {key} | - | **미작성** |")
    lines.append("")

    # 3. 평가항목별 분석
    lines.append("## 3. 평가항목별 분석")
    lines.append("")

    for category, data in keyword_results.items():
        coverage_pct = data["coverage"] * 100
        status = "양호" if coverage_pct >= 70 else ("보통" if coverage_pct >= 50 else "**미흡**")
        lines.append(f"### {category} ({status}, 커버리지 {coverage_pct:.0f}%)")
        lines.append(f"> {data['description']}")
        lines.append("")

        if data["missing"]:
            lines.append(f"- 누락 키워드: {', '.join(data['missing'][:8])}")

        # 해당 카테고리의 섹션별 점수
        cat_def = EVAL_CATEGORIES[category]
        for sk in cat_def["sections"]:
            if sk in section_scores:
                sc = section_scores[sk]
                lines.append(f"- [{sk}] 예상점수: {sc['estimated_score']}/{sc['max_score']}점 ({sc['chars']:,}자)")

        lines.append("")

    # 4. 재무 데이터 검증
    lines.append("## 4. 재무 데이터 검증")
    lines.append("")

    if financial["consistent"]:
        lines.append("재무 데이터가 일관성 있게 작성되었습니다.")
    else:
        lines.append("**재무 데이터에 불일치가 발견되었습니다:**")

    if financial["issues"]:
        for issue in financial["issues"]:
            lines.append(f"- {issue}")
    else:
        lines.append("- 특이사항 없음")
    lines.append("")

    # 5. 예상 점수 종합
    lines.append("## 5. 예상 점수 종합")
    lines.append("")
    lines.append("| 평가항목 | 예상 점수 | 만점 |")
    lines.append("|---------|----------|------|")

    category_scores: dict[str, float] = {}
    for category, criteria in EVAL_CATEGORIES.items():
        total_est = 0
        for sk in criteria["sections"]:
            if sk in section_scores:
                total_est += section_scores[sk]["estimated_score"]
        # 같은 카테고리에 여러 섹션이 있는 경우 평균이 아닌 합산 (최대 max_score)
        total_est = min(total_est, criteria["max_score"])
        category_scores[category] = total_est
        lines.append(f"| {category} | {total_est:.1f} | {criteria['max_score']} |")

    total_est = sum(category_scores.values())
    lines.append(f"| **합계** | **{total_est:.1f}** | **100** |")
    lines.append("")

    # 6. 개선 제안
    lines.append("## 6. 개선 제안")
    lines.append("")

    suggestions = []

    if missing_sections:
        suggestions.append(f"누락된 섹션({', '.join(missing_sections)})을 작성하세요.")

    for key, wc in word_counts.items():
        if not wc["sufficient"]:
            needed = MIN_CHARS_PER_SECTION - wc["chars"]
            suggestions.append(f"[{key}] 분량이 부족합니다. 최소 {needed:,}자 추가 작성이 필요합니다.")

    for category, data in keyword_results.items():
        if data["coverage"] < 0.5:
            suggestions.append(
                f"[{category}] 핵심 요소가 부족합니다. "
                f"다음 키워드를 포함하세요: {', '.join(data['missing'][:5])}"
            )

    if not financial["consistent"]:
        suggestions.append("재무 데이터의 일관성을 점검하세요. 총사업비 = 정부지원 + 현금 + 현물")

    for issue in financial.get("issues", []):
        if "비율" in issue:
            suggestions.append(f"사업비 비율 조정: {issue}")

    if not suggestions:
        suggestions.append("전반적으로 잘 작성되었습니다. 세부 표현과 데이터를 한번 더 점검하세요.")

    for i, s in enumerate(suggestions, 1):
        lines.append(f"{i}. {s}")

    lines.append("")
    lines.append("---")
    lines.append("*이 보고서는 sandoc review 자동 분석 결과입니다.*")

    return "\n".join(lines)


# ── 메인 실행 함수 ──────────────────────────────────────────

def _read_sections(drafts_dir: Path) -> dict[str, str]:
    """초안 디렉토리에서 섹션 내용을 읽어 dict로 반환."""
    sections: dict[str, str] = {}
    for md_path in sorted(drafts_dir.glob("*.md")):
        stem = md_path.stem
        key = re.sub(r"^\d+[-_]", "", stem)
        sections[key] = md_path.read_text(encoding="utf-8")
    return sections


def run_review(
    project_dir: Path,
    drafts_dir: Path | None = None,
    output_path: Path | None = None,
    context_path: Path | None = None,
) -> dict[str, Any]:
    """
    사업계획서 자가 검토를 실행합니다.

    Args:
        project_dir: 프로젝트 루트 디렉토리
        drafts_dir: 초안 디렉토리 (기본: project_dir/output/drafts/current/)
        output_path: 리뷰 결과 저장 경로 (기본: project_dir/output/review.md)
        context_path: context.json 경로 (선택)

    Returns:
        검토 결과 딕셔너리
    """
    result: dict[str, Any] = {
        "success": False,
        "overall_score": 0,
        "section_scores": {},
        "issues": [],
        "output_path": "",
        "errors": [],
    }

    try:
        # 초안 디렉토리
        if drafts_dir is None:
            drafts_dir = project_dir / "output" / "drafts" / "current"

        if not drafts_dir.is_dir():
            result["errors"].append(f"초안 디렉토리가 없습니다: {drafts_dir}")
            return result

        # 섹션 읽기
        sections = _read_sections(drafts_dir)
        if not sections:
            result["errors"].append("마크다운 파일이 없습니다.")
            return result

        logger.info("섹션 %d개 읽기 완료", len(sections))

        # context.json에서 추가 평가 기준 로드 (선택적)
        context_data: dict[str, Any] = {}
        if context_path is None:
            context_path = project_dir / "context.json"
        if context_path.exists():
            context_data = json.loads(context_path.read_text(encoding="utf-8"))
            logger.info("context.json 로드 완료")

        # 1. 섹션 존재 확인
        present, missing = _check_sections_present(sections)

        # 2. 분량 검사
        word_counts = _check_word_count(sections)

        # 3. 키워드 검사
        keyword_results = _check_keywords(sections)

        # 4. 재무 일관성 검사
        financial = _check_financial_consistency(sections)

        # 5. 섹션별 점수 추정
        section_scores: dict[str, dict[str, Any]] = {}
        for key, text in sections.items():
            section_scores[key] = _estimate_section_score(key, text, keyword_results)

        # 6. 종합 점수 계산
        # 섹션 존재 (20점)
        section_score = (len(present) / len(REQUIRED_SECTIONS)) * 20

        # 분량 (20점)
        sufficient_count = sum(1 for v in word_counts.values() if v["sufficient"])
        length_score = (sufficient_count / max(len(sections), 1)) * 20

        # 키워드 커버리지 (30점)
        avg_coverage = sum(v["coverage"] for v in keyword_results.values()) / max(len(keyword_results), 1)
        keyword_score = avg_coverage * 30

        # 재무 일관성 (15점)
        fin_score = 15 if financial["consistent"] else max(0, 15 - len(financial["issues"]) * 3)

        # 구조/완성도 (15점)
        structure_score = 0
        for key, text in sections.items():
            if "◦" in text or "○" in text:
                structure_score += 1
            if "|" in text and "---" in text:
                structure_score += 1
        structure_score = min(structure_score / max(len(sections), 1) * 15, 15)

        overall_score = section_score + length_score + keyword_score + fin_score + structure_score
        overall_score = min(round(overall_score, 1), 100)

        # 이슈 수집
        issues: list[str] = []
        if missing:
            issues.append(f"누락 섹션: {', '.join(missing)}")
        for key, wc in word_counts.items():
            if not wc["sufficient"]:
                issues.append(f"[{key}] 분량 부족 ({wc['chars']}자 < {MIN_CHARS_PER_SECTION}자)")
        if not financial["consistent"]:
            issues.extend(financial["issues"])

        # 리뷰 마크다운 생성
        review_md = _generate_review_markdown(
            present, missing, word_counts, keyword_results,
            financial, section_scores, overall_score,
        )

        # 저장
        if output_path is None:
            output_dir = project_dir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "review.md"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(review_md, encoding="utf-8")

        result["success"] = True
        result["overall_score"] = overall_score
        result["section_scores"] = section_scores
        result["issues"] = issues
        result["output_path"] = str(output_path)
        result["present_sections"] = present
        result["missing_sections"] = missing
        result["keyword_results"] = {
            k: {"coverage": v["coverage"], "missing": v["missing"]}
            for k, v in keyword_results.items()
        }
        result["financial"] = financial

        logger.info("검토 완료: 종합 %s점, %d개 이슈", overall_score, len(issues))

    except Exception as e:
        result["success"] = False
        result["errors"].append(str(e))
        logger.error("검토 오류: %s", e)

    return result
