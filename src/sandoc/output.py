"""
sandoc.output — 출력 파이프라인

생성된 사업계획서 콘텐츠 + 스타일 프로파일 → HWPX 파일 출력.

파이프라인:
  1. GeneratedPlan 로드 (JSON 또는 인메모리)
  2. StyleMirror 로드 (style-profile.json 또는 기본값)
  3. HwpxBuilder 로 HWPX 문서 조립
  4. 검증 및 저장
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sandoc.generator import GeneratedPlan, GeneratedSection, PlanGenerator
from sandoc.hwpx_engine import HwpxBuilder, StyleMirror, validate_hwpx
from sandoc.schema import CompanyInfo

logger = logging.getLogger(__name__)


# ── 결과 데이터 클래스 ──────────────────────────────────────────────

@dataclass
class BuildResult:
    """빌드 결과."""
    success: bool = False
    hwpx_path: str = ""
    plan_json_path: str = ""
    sections_dir: str = ""
    prompts_dir: str = ""
    validation: dict[str, Any] = field(default_factory=dict)
    section_count: int = 0
    total_chars: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "success": self.success,
            "hwpx_path": self.hwpx_path,
            "plan_json_path": self.plan_json_path,
            "sections_dir": self.sections_dir,
            "prompts_dir": self.prompts_dir,
            "validation": self.validation,
            "section_count": self.section_count,
            "total_chars": self.total_chars,
            "errors": self.errors,
        }


# ── 출력 파이프라인 ──────────────────────────────────────────────

class OutputPipeline:
    """
    사업계획서 출력 파이프라인.

    사용법:
        pipeline = OutputPipeline(
            company_info=company,
            style_profile_path="style-profile.json",
            output_dir="output/",
        )
        result = pipeline.run()
    """

    def __init__(
        self,
        company_info: CompanyInfo,
        output_dir: str | Path = "output",
        style_profile_path: str | Path | None = None,
        style_profile_data: dict[str, Any] | None = None,
        template_analysis: dict[str, Any] | None = None,
        announcement_analysis: dict[str, Any] | None = None,
        plan: GeneratedPlan | None = None,
        plan_json_path: str | Path | None = None,
    ):
        """
        Args:
            company_info: 회사 정보
            output_dir: 출력 디렉토리
            style_profile_path: 스타일 프로파일 JSON 경로
            style_profile_data: 스타일 프로파일 딕셔너리 (직접 전달)
            template_analysis: 양식 분석 결과
            announcement_analysis: 공고문 분석 결과
            plan: 이미 생성된 GeneratedPlan (없으면 자동 생성)
            plan_json_path: plan.json 파일 경로 (plan이 없을 때 로드)
        """
        self.company = company_info
        self.output_dir = Path(output_dir)
        self.template_analysis = template_analysis or {}
        self.announcement_analysis = announcement_analysis or {}

        # 스타일 미러 초기화
        if style_profile_path:
            self.style = StyleMirror.from_file(style_profile_path)
        elif style_profile_data:
            self.style = StyleMirror(style_profile_data)
        else:
            self.style = StyleMirror.default()

        # 생성된 계획 로드
        self._plan = plan
        self._plan_json_path = plan_json_path

        # 스타일 프로파일 데이터 (생성기에 전달용)
        if style_profile_path:
            self._style_data = json.loads(
                Path(style_profile_path).read_text(encoding="utf-8")
            )
        elif style_profile_data:
            self._style_data = style_profile_data
        else:
            self._style_data = {}

    def run(self, prompts_only: bool = False) -> BuildResult:
        """
        전체 출력 파이프라인을 실행합니다.

        Args:
            prompts_only: True이면 프롬프트만 생성 (HWPX 미생성)

        Returns:
            BuildResult: 빌드 결과
        """
        result = BuildResult()

        try:
            # 1. 출력 디렉토리 준비
            self.output_dir.mkdir(parents=True, exist_ok=True)

            # 2. 계획 로드 또는 생성
            plan = self._get_or_generate_plan()

            # 3. 프롬프트 저장
            prompts_dir = self.output_dir / "prompts"
            gen = self._create_generator()
            saved_prompts = gen.save_prompts(prompts_dir)
            result.prompts_dir = str(prompts_dir)
            logger.info("프롬프트 %d개 저장: %s", len(saved_prompts), prompts_dir)

            if prompts_only:
                result.success = True
                return result

            # 4. plan.json 저장
            plan_path = self.output_dir / "plan.json"
            plan_path.write_text(plan.to_json(), encoding="utf-8")
            result.plan_json_path = str(plan_path)

            # 5. 섹션 파일 저장
            sections_dir = self.output_dir / "sections"
            sections_dir.mkdir(parents=True, exist_ok=True)
            for sec in plan.sections:
                sec_path = sections_dir / f"{sec.section_index + 1:02d}_{sec.section_key}.md"
                sec_path.write_text(
                    f"# {sec.title}\n\n{sec.content}\n", encoding="utf-8"
                )
            result.sections_dir = str(sections_dir)

            # 6. 회사 정보 저장
            self.company.save(self.output_dir / "company_info.json")

            # 7. HWPX 빌드
            hwpx_path = self.output_dir / f"{self.company.company_name}_사업계획서.hwpx"
            self._build_hwpx(plan, hwpx_path)
            result.hwpx_path = str(hwpx_path)

            # 8. 검증
            validation = validate_hwpx(hwpx_path)
            result.validation = validation

            # 9. 통계
            result.section_count = len(plan.sections)
            result.total_chars = plan.total_word_count
            result.success = validation.get("valid", False)

            if not result.success:
                result.errors.extend(validation.get("errors", []))

            logger.info(
                "출력 파이프라인 완료: %s (%d 섹션, %d자)",
                hwpx_path, result.section_count, result.total_chars,
            )

        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            logger.error("출력 파이프라인 오류: %s", e)

        return result

    # ── 내부 메서드 ──────────────────────────────────────────

    def _create_generator(self) -> PlanGenerator:
        """PlanGenerator 인스턴스 생성."""
        return PlanGenerator(
            company_info=self.company,
            template_analysis=self.template_analysis,
            announcement_analysis=self.announcement_analysis,
            style_profile=self._style_data,
        )

    def _get_or_generate_plan(self) -> GeneratedPlan:
        """GeneratedPlan 로드 또는 신규 생성."""
        if self._plan is not None:
            return self._plan

        if self._plan_json_path:
            return self._load_plan_from_json(self._plan_json_path)

        # 신규 생성
        gen = self._create_generator()
        return gen.generate_full_plan()

    @staticmethod
    def _load_plan_from_json(path: str | Path) -> GeneratedPlan:
        """plan.json 파일에서 GeneratedPlan 복원."""
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))

        plan = GeneratedPlan(
            title=data.get("title", ""),
            company_name=data.get("company_name", ""),
            total_word_count=data.get("total_word_count", 0),
            metadata=data.get("metadata", {}),
        )

        for sec_data in data.get("sections", []):
            section = GeneratedSection(
                title=sec_data.get("title", ""),
                content=sec_data.get("content", ""),
                section_key=sec_data.get("section_key", ""),
                section_index=sec_data.get("section_index", 0),
                word_count=sec_data.get("word_count", 0),
                prompt=sec_data.get("prompt", ""),
                evaluation_category=sec_data.get("evaluation_category", ""),
            )
            plan.sections.append(section)

        return plan

    def _build_hwpx(self, plan: GeneratedPlan, output_path: Path) -> Path:
        """GeneratedPlan → HWPX 파일 빌드."""
        builder = HwpxBuilder(style=self.style)

        for section in plan.sections:
            builder.add_section(
                title=section.title,
                content=section.content,
                style_name="bodyText",
                section_key=section.section_key,
            )

        return builder.build(output_path)


# ── 편의 함수 ──────────────────────────────────────────────────

def build_hwpx_from_plan(
    plan: GeneratedPlan,
    output_path: str | Path,
    style_profile_path: str | Path | None = None,
) -> Path:
    """
    GeneratedPlan 에서 직접 HWPX 파일을 생성합니다.

    Args:
        plan: 생성된 사업계획서
        output_path: 출력 HWPX 파일 경로
        style_profile_path: 스타일 프로파일 경로 (선택)

    Returns:
        생성된 HWPX 파일 경로
    """
    if style_profile_path:
        style = StyleMirror.from_file(style_profile_path)
    else:
        style = StyleMirror.default()

    builder = HwpxBuilder(style=style)

    for section in plan.sections:
        builder.add_section(
            title=section.title,
            content=section.content,
            style_name="bodyText",
            section_key=section.section_key,
        )

    return builder.build(output_path)


def build_hwpx_from_json(
    plan_json_path: str | Path,
    output_path: str | Path,
    style_profile_path: str | Path | None = None,
) -> Path:
    """
    plan.json 파일에서 HWPX 파일을 생성합니다.

    Args:
        plan_json_path: plan.json 파일 경로
        output_path: 출력 HWPX 파일 경로
        style_profile_path: 스타일 프로파일 경로 (선택)

    Returns:
        생성된 HWPX 파일 경로
    """
    plan = OutputPipeline._load_plan_from_json(plan_json_path)
    return build_hwpx_from_plan(plan, output_path, style_profile_path)
