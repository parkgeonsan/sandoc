"""
sandoc.analyzer — 문서 분석 모듈

HWP 양식 분석, PDF 공고문 분석, 폴더 내 문서 분류 기능을 제공합니다.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sandoc.parser import parse_hwp, parse_pdf, parse_any, HwpParseResult, PdfParseResult

logger = logging.getLogger(__name__)

# ── 문서 분류 패턴 ─────────────────────────────────────────────────

CLASSIFICATION_PATTERNS: dict[str, list[str]] = {
    "공고문": ["공고", "공고문", "모집", "수정공고"],
    "양식": ["양식", "사업계획서", "별첨", "신청서", "서식"],
    "참고": ["참고", "매뉴얼", "안내", "가이드", "질의응답", "FAQ"],
    "증빙": ["증빙", "제출목록", "첨부", "확인서", "증명"],
}


# ── 데이터 클래스 ─────────────────────────────────────────────────

@dataclass
class TemplateSection:
    """양식 내 섹션 정보."""
    title: str
    level: int = 0
    start_index: int = 0
    fields: list[str] = field(default_factory=list)


@dataclass
class TemplateAnalysis:
    """양식 분석 결과."""
    file_path: str
    sections: list[TemplateSection] = field(default_factory=list)
    tables_count: int = 0
    input_fields: list[str] = field(default_factory=list)
    total_paragraphs: int = 0
    summary: str = ""


@dataclass
class ScoringCriterion:
    """평가 기준 항목."""
    category: str
    item: str
    score: float = 0.0
    description: str = ""


@dataclass
class AnnouncementAnalysis:
    """공고문 분석 결과."""
    file_path: str
    title: str = ""
    scoring_criteria: list[ScoringCriterion] = field(default_factory=list)
    key_dates: list[str] = field(default_factory=list)
    eligibility: list[str] = field(default_factory=list)
    total_pages: int = 0
    summary: str = ""


@dataclass
class ClassifiedDocument:
    """분류된 문서."""
    file_path: str
    filename: str
    category: str
    extension: str
    confidence: float = 0.0


# ── 양식 분석 ─────────────────────────────────────────────────────

# 섹션 제목 패턴 (로마/아라비아/가나다 숫자 + 제목)
SECTION_PATTERNS = [
    re.compile(r"^[IVX]+\.\s+(.+)"),                    # I. 제목
    re.compile(r"^[0-9]+\.\s+(.+)"),                     # 1. 제목
    re.compile(r"^[가-힣]\.\s+(.+)"),                    # 가. 제목
    re.compile(r"^[①-⑳]\s*(.+)"),                       # ① 제목
    re.compile(r"^\d+[-)]\s+(.+)"),                      # 1) 제목 또는 1- 제목
    re.compile(r"^[■□●○▶▷◆◇★☆]\s*(.+)"),                # 불릿 제목
]

# 입력 필드 패턴 (빈칸, 밑줄, 괄호 내 공란)
INPUT_FIELD_PATTERNS = [
    re.compile(r"[_]{3,}"),                              # ___ 빈칸
    re.compile(r"[　]{3,}"),                              # 전각 공백
    re.compile(r"\(\s{2,}\)"),                           # (   ) 괄호 공란
    re.compile(r"【\s{2,}】"),                            # 【   】
    re.compile(r"□"),                                    # 체크박스
]


def analyze_template(path: str | Path) -> TemplateAnalysis:
    """
    HWP 양식 파일을 분석하여 섹션, 표, 입력 필드를 식별합니다.

    Args:
        path: HWP 양식 파일 경로

    Returns:
        TemplateAnalysis: 양식 분석 결과
    """
    path = Path(path)
    result = TemplateAnalysis(file_path=str(path))

    # HWP 파싱
    parsed = parse_hwp(path)
    result.total_paragraphs = len(parsed.paragraphs)
    result.tables_count = len(parsed.tables)

    # 섹션 식별
    for i, para in enumerate(parsed.paragraphs):
        text = para.text.strip()
        if not text:
            continue

        for pattern in SECTION_PATTERNS:
            match = pattern.match(text)
            if match:
                section = TemplateSection(
                    title=text,
                    level=para.level,
                    start_index=i,
                )
                result.sections.append(section)
                break

    # 입력 필드 식별
    for para in parsed.paragraphs:
        text = para.text
        for pattern in INPUT_FIELD_PATTERNS:
            if pattern.search(text):
                # 필드가 포함된 줄 기록
                field_text = text.strip()
                if field_text and field_text not in result.input_fields:
                    result.input_fields.append(field_text)
                break

    result.summary = (
        f"양식 분석 완료: {result.total_paragraphs}개 문단, "
        f"{len(result.sections)}개 섹션, "
        f"{result.tables_count}개 표, "
        f"{len(result.input_fields)}개 입력 필드"
    )

    logger.info(result.summary)
    return result


# ── 공고문 분석 ───────────────────────────────────────────────────

# 평가 점수 패턴
SCORE_PATTERNS = [
    # "항목 (30점)" 형태
    re.compile(r"(.+?)\s*[(\(]\s*(\d+)\s*점\s*[)\)]"),
    # "항목 30점" 형태
    re.compile(r"(.+?)\s+(\d+)\s*점"),
    # "항목 | 배점 30" 형태 (표에서)
    re.compile(r"(\d+)\s*$"),
]

# 날짜 패턴
DATE_PATTERNS = [
    re.compile(r"\d{4}\.\s*\d{1,2}\.\s*\d{1,2}"),                 # 2025. 1. 15
    re.compile(r"\d{4}년\s*\d{1,2}월\s*\d{1,2}일"),                # 2025년 1월 15일
    re.compile(r"\d{4}-\d{2}-\d{2}"),                              # 2025-01-15
    re.compile(r"\d{1,2}/\d{1,2}"),                                # 1/15
]


def analyze_announcement(path: str | Path) -> AnnouncementAnalysis:
    """
    PDF 공고문을 분석하여 평가 기준, 주요 일정, 자격 요건을 추출합니다.

    Args:
        path: PDF 공고문 파일 경로

    Returns:
        AnnouncementAnalysis: 공고문 분석 결과
    """
    path = Path(path)
    result = AnnouncementAnalysis(file_path=str(path))

    # PDF 파싱
    parsed = parse_pdf(path)
    result.total_pages = parsed.page_count
    full_text = parsed.full_text

    # 제목 추출 (첫 페이지에서)
    if parsed.pages:
        first_page = parsed.pages[0]
        lines = [l.strip() for l in first_page.split("\n") if l.strip()]
        if lines:
            # 가장 긴 줄이나 첫 의미있는 줄을 제목으로
            for line in lines[:5]:
                if len(line) > 10:
                    result.title = line
                    break

    # 평가 기준 추출
    _extract_scoring_criteria(full_text, parsed.tables, result)

    # 주요 일정 추출
    for pattern in DATE_PATTERNS:
        for match in pattern.finditer(full_text):
            # 날짜 주변 컨텍스트 포함
            start = max(0, match.start() - 30)
            end = min(len(full_text), match.end() + 10)
            context = full_text[start:end].strip()
            context = re.sub(r"\s+", " ", context)
            if context not in result.key_dates:
                result.key_dates.append(context)

    # 자격 요건 추출
    _extract_eligibility(full_text, result)

    result.summary = (
        f"공고문 분석 완료: {result.total_pages}페이지, "
        f"{len(result.scoring_criteria)}개 평가항목, "
        f"{len(result.key_dates)}개 일정"
    )

    logger.info(result.summary)
    return result


def _extract_scoring_criteria(
    text: str,
    tables: list[list[list[str]]],
    result: AnnouncementAnalysis,
) -> None:
    """평가 기준 추출."""
    # 텍스트에서 "점" 패턴으로 추출
    for pattern in SCORE_PATTERNS[:2]:
        for match in pattern.finditer(text):
            item_text = match.group(1).strip()
            score = float(match.group(2))
            if score > 0 and len(item_text) > 1:
                criterion = ScoringCriterion(
                    category="평가항목",
                    item=item_text,
                    score=score,
                )
                result.scoring_criteria.append(criterion)

    # 표에서 배점 관련 데이터 추출
    for table in tables:
        for row in table:
            row_text = " ".join(str(cell) for cell in row if cell)
            if "점" in row_text or "배점" in row_text:
                for cell in row:
                    if cell and re.search(r"\d+\s*점", str(cell)):
                        criterion = ScoringCriterion(
                            category="표_평가항목",
                            item=row_text.strip(),
                            score=0,
                        )
                        result.scoring_criteria.append(criterion)
                        break


def _extract_eligibility(text: str, result: AnnouncementAnalysis) -> None:
    """자격 요건 추출."""
    eligibility_keywords = [
        "신청자격", "지원자격", "참여자격", "대상",
        "자격요건", "신청대상", "지원대상",
    ]

    lines = text.split("\n")
    capturing = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if capturing:
                capturing = False
            continue

        # 자격 관련 키워드가 있으면 캡처 시작
        if any(kw in stripped for kw in eligibility_keywords):
            capturing = True
            result.eligibility.append(stripped)
            continue

        if capturing and len(stripped) > 5:
            # 새로운 섹션 시작 시 캡처 종료
            if re.match(r"^[IVX0-9]+[.\s]", stripped):
                capturing = False
                continue
            result.eligibility.append(stripped)


# ── 문서 분류 ─────────────────────────────────────────────────────

def classify_documents(folder: str | Path) -> list[ClassifiedDocument]:
    """
    폴더 내 문서를 파일명 패턴으로 분류합니다.

    분류 카테고리: 공고문, 양식, 참고, 증빙, 기타

    Args:
        folder: 문서 폴더 경로

    Returns:
        분류된 문서 목록
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError(f"유효한 폴더가 아닙니다: {folder}")

    results: list[ClassifiedDocument] = []
    extensions = {".hwp", ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt"}

    for file_path in sorted(folder.iterdir()):
        if not file_path.is_file():
            continue
        ext = file_path.suffix.lower()
        if ext not in extensions:
            continue

        filename = file_path.name
        category, confidence = _classify_filename(filename)

        doc = ClassifiedDocument(
            file_path=str(file_path),
            filename=filename,
            category=category,
            extension=ext,
            confidence=confidence,
        )
        results.append(doc)

    logger.info("문서 분류 완료: %d개 파일", len(results))
    return results


def _classify_filename(filename: str) -> tuple[str, float]:
    """파일명 패턴 매칭으로 카테고리 결정."""
    best_category = "기타"
    best_confidence = 0.0

    for category, patterns in CLASSIFICATION_PATTERNS.items():
        for pattern in patterns:
            if pattern in filename:
                # 대괄호 내 패턴은 높은 신뢰도
                bracket_match = re.search(r"\[(.+?)\]", filename)
                if bracket_match and pattern in bracket_match.group(1):
                    confidence = 0.95
                else:
                    confidence = 0.7

                if confidence > best_confidence:
                    best_category = category
                    best_confidence = confidence

    return best_category, best_confidence
