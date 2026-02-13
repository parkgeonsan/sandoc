"""
sandoc.learn — 지식 축적 (Knowledge Accumulation)

완성된 초안 섹션에서:
  - 효과적인 표현/패턴 추출
  - knowledge/expressions/ 에 저장
  - knowledge/patterns/ 에 저장
  - knowledge/lessons.md 에 기록
  - 처리된 공고 유형 추적
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── 섹션 키 → 평가 카테고리 매핑 ────────────────────────────────────

SECTION_CATEGORY_MAP = {
    "company_overview": "기업개요",
    "problem_recognition": "문제인식",
    "solution": "실현가능성",
    "business_model": "실현가능성",
    "market_analysis": "성장전략",
    "growth_strategy": "성장전략",
    "team": "팀구성",
    "financial_plan": "재무계획",
    "funding_plan": "재무계획",
}

# 효과적 표현 추출 패턴
EXPRESSION_PATTERNS = [
    # 수치가 포함된 구체적 성과 표현
    (r"[가-힣\w]+\s*\d[\d,.]*\s*[%억만원건명개호대]+\s*(?:이상|달성|증가|감소|절감|확보|유치|돌파)", "성과_수치"),
    # 비교 우위 표현
    (r"기존\s*대비\s*\d[\d,.]*\s*[%배]+\s*[가-힣]+", "비교우위"),
    # 연도별 목표 표현
    (r"\d{4}년?\s*[:：]?\s*[가-힣\w,\s]+(?:달성|목표|시작|론칭|확대)", "연도별목표"),
    # 핵심 차별점 표현 (①②③ 형태)
    (r"[①②③④⑤]\s*[가-힣\w\s]+(?:\([^)]+\))?", "차별점열거"),
]

# 구조적 패턴 유형
STRUCTURE_PATTERNS = [
    ("table", r"\|[^|]+\|[^|]+\|", "표 형식 데이터 제시"),
    ("bullet_hierarchy", r"◦\s*.+\n\s+-\s+", "불릿 계층 구조"),
    ("numbered_list", r"\d+\.\s+.+(?:\n\s+.+)*", "번호 목록 구조"),
    ("section_header", r"□\s+.+|[0-9]+-[0-9]+[-.]?\s+", "섹션 헤더 구조"),
]


def run_learn(
    project_dir: Path,
    knowledge_dir: Path | None = None,
) -> dict[str, Any]:
    """
    완성된 초안에서 지식을 축적합니다.

    Args:
        project_dir: 프로젝트 루트 디렉토리
        knowledge_dir: 지식 저장 디렉토리 (기본: project_dir 기준 상위 knowledge/)

    Returns:
        {
            "success": bool,
            "expressions_count": int,
            "patterns_count": int,
            "lessons_path": str,
            "processed_sections": list[str],
            "errors": list[str],
        }
    """
    result: dict[str, Any] = {
        "success": False,
        "expressions_count": 0,
        "patterns_count": 0,
        "lessons_path": None,
        "processed_sections": [],
        "errors": [],
    }

    # 초안 디렉토리 탐색
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

    # 지식 디렉토리 결정
    if knowledge_dir is None:
        # 프로젝트 상위에 knowledge/ 사용 (전역 지식 저장소)
        knowledge_dir = project_dir.parent.parent / "knowledge"
        if not knowledge_dir.exists():
            knowledge_dir = project_dir / "knowledge"

    expressions_dir = knowledge_dir / "expressions"
    patterns_dir = knowledge_dir / "patterns"
    expressions_dir.mkdir(parents=True, exist_ok=True)
    patterns_dir.mkdir(parents=True, exist_ok=True)

    # 프로젝트 이름 추출
    project_name = project_dir.name
    context_path = project_dir / "context.json"
    announcement_type = "unknown"
    if context_path.exists():
        try:
            ctx = json.loads(context_path.read_text(encoding="utf-8"))
            project_name = ctx.get("project_name", project_name)
            aa = ctx.get("announcement_analysis", {})
            if aa:
                announcement_type = aa.get("title", "unknown")[:50]
        except (json.JSONDecodeError, OSError):
            pass

    # 각 섹션 처리
    all_expressions: list[dict[str, str]] = []
    all_patterns: list[dict[str, str]] = []
    sections_processed: list[str] = []
    lessons: list[str] = []

    for md_path in md_files:
        content = md_path.read_text(encoding="utf-8")
        if not content.strip():
            continue

        section_stem = md_path.stem
        # 섹션 키 추출 (01_company_overview → company_overview)
        section_key = re.sub(r"^\d+_", "", section_stem)
        category = SECTION_CATEGORY_MAP.get(section_key, "기타")

        # 1. 표현 추출
        expressions = _extract_expressions(content, section_key, category)
        all_expressions.extend(expressions)

        # 2. 구조 패턴 추출
        patterns = _extract_patterns(content, section_key, category)
        all_patterns.extend(patterns)

        # 3. 교훈 추출
        lesson = _extract_lesson(content, section_key, category)
        if lesson:
            lessons.append(lesson)

        sections_processed.append(section_key)

    # ── 저장 ─────────────────────────────────────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1. 표현 저장
    if all_expressions:
        expr_path = expressions_dir / f"{project_name}_{timestamp}.json"
        expr_path.write_text(
            json.dumps(all_expressions, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        result["expressions_count"] = len(all_expressions)

    # 2. 패턴 저장
    if all_patterns:
        pat_path = patterns_dir / f"{project_name}_{timestamp}.json"
        pat_path.write_text(
            json.dumps(all_patterns, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        result["patterns_count"] = len(all_patterns)

    # 3. 교훈 기록
    lessons_path = knowledge_dir / "lessons.md"
    _append_lessons(lessons_path, project_name, announcement_type, lessons, timestamp)
    result["lessons_path"] = str(lessons_path)

    # 4. 처리 이력 기록
    _record_processed(knowledge_dir, project_name, announcement_type, timestamp)

    result["success"] = True
    result["processed_sections"] = sections_processed
    return result


def _extract_expressions(
    content: str, section_key: str, category: str
) -> list[dict[str, str]]:
    """텍스트에서 효과적인 표현을 추출합니다."""
    expressions: list[dict[str, str]] = []

    for pattern, expr_type in EXPRESSION_PATTERNS:
        for match in re.finditer(pattern, content):
            text = match.group().strip()
            if len(text) > 10:  # 너무 짧은 건 스킵
                expressions.append({
                    "text": text,
                    "type": expr_type,
                    "section": section_key,
                    "category": category,
                })

    return expressions


def _extract_patterns(
    content: str, section_key: str, category: str
) -> list[dict[str, str]]:
    """텍스트에서 구조적 패턴을 추출합니다."""
    patterns: list[dict[str, str]] = []

    for pat_type, regex, description in STRUCTURE_PATTERNS:
        matches = re.findall(regex, content)
        if matches:
            patterns.append({
                "type": pat_type,
                "description": description,
                "section": section_key,
                "category": category,
                "count": str(len(matches)),
                "sample": matches[0][:100] if matches else "",
            })

    return patterns


def _extract_lesson(content: str, section_key: str, category: str) -> str | None:
    """섹션 내용에서 교훈/특징을 추출합니다."""
    char_count = len(content)
    table_count = content.count("|---|")
    bullet_count = content.count("◦")
    numbered_count = len(re.findall(r"^\d+\.", content, re.MULTILINE))

    # 의미 있는 내용이 있는 경우만
    if char_count < 100:
        return None

    parts = []
    parts.append(f"- **{section_key}** ({category}): {char_count}자")
    if table_count:
        parts.append(f"  표 {table_count}개 사용")
    if bullet_count > 3:
        parts.append(f"  불릿 {bullet_count}개로 구조화")
    if numbered_count > 2:
        parts.append(f"  번호 목록 {numbered_count}개 사용")

    return ", ".join(parts)


def _append_lessons(
    lessons_path: Path,
    project_name: str,
    announcement_type: str,
    lessons: list[str],
    timestamp: str,
) -> None:
    """lessons.md 에 교훈을 추가합니다."""
    header = (
        f"\n## {project_name} ({timestamp})\n"
        f"공고 유형: {announcement_type}\n\n"
    )

    content = header
    if lessons:
        for lesson in lessons:
            content += f"{lesson}\n"
    else:
        content += "- 특별한 교훈 없음\n"
    content += "\n"

    # 기존 파일에 추가
    if lessons_path.exists():
        existing = lessons_path.read_text(encoding="utf-8")
    else:
        existing = "# 📚 sandoc 학습 기록 (Lessons Learned)\n\n"

    lessons_path.write_text(existing + content, encoding="utf-8")


def _record_processed(
    knowledge_dir: Path,
    project_name: str,
    announcement_type: str,
    timestamp: str,
) -> None:
    """처리 이력을 기록합니다."""
    history_path = knowledge_dir / "processing_history.json"
    history: list[dict[str, str]] = []

    if history_path.exists():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            history = []

    history.append({
        "project": project_name,
        "announcement_type": announcement_type,
        "processed_at": timestamp,
    })

    history_path.write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )
