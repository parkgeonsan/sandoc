"""
sandoc.assemble — 작성된 섹션 마크다운을 HWPX로 조립

output/drafts/current/ 의 *.md 파일을 읽어:
  - plan.json 형식으로 변환
  - 스타일 프로파일 적용
  - HWPX 문서 빌드
  - 결과 검증
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from sandoc.generator import GeneratedPlan, GeneratedSection, SECTION_DEFS
from sandoc.hwpx_engine import HwpxBuilder, StyleMirror, validate_hwpx

logger = logging.getLogger(__name__)

# 섹션 키 이름 → 인덱스 매핑
SECTION_KEY_INDEX = {sd["key"]: i for i, sd in enumerate(SECTION_DEFS)}


def run_assemble(
    project_dir: Path,
    drafts_dir: Path | None = None,
    style_profile_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """
    작성된 섹션 마크다운 파일을 HWPX 문서로 조립합니다.

    Args:
        project_dir: 프로젝트 루트 디렉토리
        drafts_dir: 섹션 마크다운 파일 디렉토리 (기본: project_dir/output/drafts/current/)
        style_profile_path: 스타일 프로파일 JSON 경로
        output_path: HWPX 출력 경로

    Returns:
        조립 결과 딕셔너리
    """
    result: dict[str, Any] = {
        "success": False,
        "hwpx_path": "",
        "plan_json_path": "",
        "section_count": 0,
        "total_chars": 0,
        "validation": {},
        "errors": [],
    }

    try:
        # ── 1. 초안 디렉토리 결정 ──────────────────────────────
        if drafts_dir is None:
            drafts_dir = project_dir / "output" / "drafts" / "current"

        if not drafts_dir.is_dir():
            result["errors"].append(f"초안 디렉토리가 없습니다: {drafts_dir}")
            return result

        # ── 2. 마크다운 파일 읽기 ──────────────────────────────
        md_files = sorted(drafts_dir.glob("*.md"))
        if not md_files:
            result["errors"].append(f"마크다운 파일이 없습니다: {drafts_dir}")
            return result

        logger.info("마크다운 파일 %d개 발견: %s", len(md_files), drafts_dir)

        # ── 3. GeneratedPlan 구성 ──────────────────────────────
        plan = _build_plan_from_markdowns(md_files)
        result["section_count"] = len(plan.sections)
        result["total_chars"] = plan.total_word_count

        # ── 4. plan.json 저장 ──────────────────────────────────
        output_dir = project_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        plan_json_path = output_dir / "plan.json"
        plan_json_path.write_text(plan.to_json(), encoding="utf-8")
        result["plan_json_path"] = str(plan_json_path)

        # ── 5. 스타일 미러 초기화 ──────────────────────────────
        if style_profile_path is None:
            # 프로젝트 내 style-profile.json 탐색
            candidates = [
                project_dir / "style-profile.json",
                project_dir / "output" / "style-profile.json",
            ]
            for candidate in candidates:
                if candidate.exists():
                    style_profile_path = candidate
                    break

        if style_profile_path and style_profile_path.exists():
            style = StyleMirror.from_file(style_profile_path)
            logger.info("스타일 프로파일 로드: %s", style_profile_path)
        else:
            style = StyleMirror.default()
            logger.info("기본 스타일 사용")

        # ── 6. HWPX 빌드 ──────────────────────────────────────
        if output_path is None:
            output_path = output_dir / f"{plan.company_name or 'sandoc'}_사업계획서.hwpx"

        builder = HwpxBuilder(style=style)
        for section in plan.sections:
            builder.add_section(
                title=section.title,
                content=section.content,
                style_name="bodyText",
                section_key=section.section_key,
            )
        builder.build(output_path)
        result["hwpx_path"] = str(output_path)

        # ── 7. 검증 ──────────────────────────────────────────
        validation = validate_hwpx(output_path)
        result["validation"] = validation
        result["success"] = validation.get("valid", False)

        if not result["success"]:
            result["errors"].extend(validation.get("errors", []))

        logger.info(
            "HWPX 조립 완료: %s (%d 섹션, %d자)",
            output_path, result["section_count"], result["total_chars"],
        )

    except Exception as e:
        result["success"] = False
        result["errors"].append(str(e))
        logger.error("HWPX 조립 오류: %s", e)

    return result


def _build_plan_from_markdowns(md_files: list[Path]) -> GeneratedPlan:
    """마크다운 파일 목록에서 GeneratedPlan을 구성합니다."""
    plan = GeneratedPlan(
        title="사업계획서",
        company_name="",
    )

    for i, md_path in enumerate(md_files):
        text = md_path.read_text(encoding="utf-8")
        title, content = _parse_markdown_section(text)
        section_key = _infer_section_key(md_path.stem, i)

        section = GeneratedSection(
            title=title,
            content=content,
            section_key=section_key,
            section_index=i,
            word_count=len(content),
        )
        plan.sections.append(section)
        plan.total_word_count += section.word_count

    return plan


def _parse_markdown_section(text: str) -> tuple[str, str]:
    """마크다운 텍스트에서 제목(# heading)과 본문을 분리합니다."""
    lines = text.strip().split("\n")
    title = ""
    content_start = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#"):
            title = re.sub(r"^#+\s*", "", stripped)
            content_start = i + 1
            break

    if not title and lines:
        # # 없으면 첫 줄을 제목으로
        title = lines[0].strip()
        content_start = 1

    content = "\n".join(lines[content_start:]).strip()
    return title, content


def _infer_section_key(stem: str, index: int) -> str:
    """파일명에서 섹션 키를 추론합니다.

    파일명 패턴: 01_company_overview, 02_problem_recognition, etc.
    """
    # 숫자 접두사 제거: "01_company_overview" → "company_overview"
    key = re.sub(r"^\d+[-_]", "", stem)

    # SECTION_DEFS에 정의된 키인지 확인
    if key in SECTION_KEY_INDEX:
        return key

    # 알려진 키가 아니면 stem 그대로 사용
    return key
