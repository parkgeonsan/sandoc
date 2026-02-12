"""
sandoc.generator — 사업계획서 섹션 생성 모듈 (스텁)

향후 LLM 연동을 통해 공고문 분석 결과와 양식 구조를 기반으로
사업계획서 각 섹션의 초안을 자동 생성합니다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class GeneratedSection:
    """생성된 섹션."""
    title: str
    content: str
    section_index: int = 0
    word_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GeneratedPlan:
    """생성된 사업계획서 전체."""
    title: str = ""
    sections: list[GeneratedSection] = field(default_factory=list)
    total_word_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


def generate_section(
    section_title: str,
    context: dict[str, Any] | None = None,
    max_words: int = 500,
) -> GeneratedSection:
    """
    사업계획서 섹션 초안을 생성합니다. (스텁)

    향후 LLM API 연동 시 실제 콘텐츠를 생성합니다.

    Args:
        section_title: 섹션 제목
        context: 생성에 필요한 컨텍스트 (공고문 분석 결과, 회사 정보 등)
        max_words: 최대 단어 수

    Returns:
        GeneratedSection: 생성된 섹션
    """
    logger.info("섹션 생성 (스텁): %s", section_title)

    placeholder = (
        f"[{section_title}]\n\n"
        f"이 섹션은 향후 LLM 연동을 통해 자동 생성될 예정입니다.\n"
        f"컨텍스트: {context or '없음'}\n"
        f"최대 단어 수: {max_words}\n\n"
        f"--- 스텁 콘텐츠 ---\n"
        f"사업의 목적과 필요성을 기술하세요.\n"
        f"시장 분석 및 경쟁력을 설명하세요.\n"
        f"실행 계획과 기대 효과를 제시하세요.\n"
    )

    return GeneratedSection(
        title=section_title,
        content=placeholder,
        word_count=len(placeholder.split()),
    )


def generate_plan(
    template_sections: list[str] | None = None,
    context: dict[str, Any] | None = None,
    max_words_per_section: int = 500,
) -> GeneratedPlan:
    """
    사업계획서 전체 초안을 생성합니다. (스텁)

    향후 LLM API 연동 시 실제 콘텐츠를 생성합니다.

    Args:
        template_sections: 생성할 섹션 제목 목록
        context: 생성에 필요한 컨텍스트
        max_words_per_section: 섹션당 최대 단어 수

    Returns:
        GeneratedPlan: 생성된 사업계획서
    """
    if template_sections is None:
        template_sections = [
            "1. 창업아이템 개요",
            "2. 시장 분석",
            "3. 사업화 전략",
            "4. 기술 개발 계획",
            "5. 자금 운용 계획",
            "6. 기대 효과",
        ]

    logger.info("사업계획서 생성 (스텁): %d개 섹션", len(template_sections))

    plan = GeneratedPlan(
        title="사업계획서 초안 (스텁)",
        metadata={"context": context or {}, "max_words": max_words_per_section},
    )

    for i, section_title in enumerate(template_sections):
        section = generate_section(
            section_title=section_title,
            context=context,
            max_words=max_words_per_section,
        )
        section.section_index = i
        plan.sections.append(section)
        plan.total_word_count += section.word_count

    return plan
