"""
test_e2e.py — 사업계획서 생성 파이프라인 End-to-End 테스트

테스트 흐름:
  1. 샘플 CompanyInfo 생성
  2. (옵션) HWP 양식 파싱 → 분석
  3. (옵션) PDF 공고문 파싱 → 분석
  4. PlanGenerator로 프롬프트 빌드
  5. 콘텐츠 생성 (fill 모드)
  6. 결과 저장 및 검증
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sandoc.schema import (
    CompanyInfo,
    TeamMember,
    InfraItem,
    IPItem,
    RevenueRecord,
    ProjectedRevenue,
    MilestoneItem,
    BudgetItem,
    create_sample_company,
)
from sandoc.generator import (
    PlanGenerator,
    GeneratedSection,
    GeneratedPlan,
    SECTION_DEFS,
    PROMPTS_DIR,
)

# ── 테스트 데이터 경로 ─────────────────────────────────────────────

DATA_DIR = Path(__file__).parent / "v1-data"
OUTPUT_DIR = DATA_DIR / "output"

HWP_FILE = DATA_DIR / "[별첨 1] 2025년도 창업도약패키지(일반형) 사업계획서 양식.hwp"
PDF_FILE = DATA_DIR / "[공고문] 2025년도 창업도약패키지(일반형) 창업기업 모집 수정공고.pdf"
STYLE_FILE = DATA_DIR / "analysis" / "style-profile.json"


# ── CompanyInfo 스키마 테스트 ──────────────────────────────────────

class TestCompanyInfo:
    """CompanyInfo 스키마 테스트."""

    def test_create_sample(self):
        """샘플 회사 정보 생성."""
        company = create_sample_company()
        assert company.company_name == "(주)스마트팜테크"
        assert company.ceo_name == "김창업"
        assert company.employee_count == 12

    def test_total_budget(self):
        """총사업비 계산."""
        company = create_sample_company()
        expected = company.funding_amount + company.self_funding_cash + company.self_funding_inkind
        assert company.total_budget == expected
        assert company.total_budget == 285_000_000

    def test_investment_bonus_false(self):
        """투자유치 가점 — 미해당."""
        company = create_sample_company()
        assert company.investment_amount == 0
        assert company.has_investment_bonus is False

    def test_investment_bonus_true(self):
        """투자유치 가점 — 해당 (5억 이상)."""
        company = create_sample_company()
        company.investment_amount = 600_000_000
        assert company.has_investment_bonus is True

    def test_to_dict(self):
        """딕셔너리 변환."""
        company = create_sample_company()
        d = company.to_dict()
        assert isinstance(d, dict)
        assert d["company_name"] == "(주)스마트팜테크"
        assert isinstance(d["team_members"], list)
        assert len(d["team_members"]) == 4

    def test_to_json_roundtrip(self):
        """JSON 직렬화/역직렬화 왕복."""
        company = create_sample_company()
        json_str = company.to_json()
        restored = CompanyInfo.from_json(json_str)
        assert restored.company_name == company.company_name
        assert restored.funding_amount == company.funding_amount
        assert len(restored.team_members) == len(company.team_members)
        assert restored.team_members[0].name == company.team_members[0].name

    def test_save_and_load(self, tmp_path):
        """파일 저장/로드."""
        company = create_sample_company()
        filepath = tmp_path / "company.json"
        company.save(filepath)
        assert filepath.exists()

        loaded = CompanyInfo.from_file(filepath)
        assert loaded.company_name == company.company_name
        assert loaded.total_budget == company.total_budget

    def test_section_context(self):
        """섹션별 컨텍스트 추출."""
        company = create_sample_company()

        ctx = company.get_section_context("문제인식")
        assert "item_name" in ctx
        assert "problem_background" in ctx

        ctx = company.get_section_context("팀구성")
        assert "ceo_background" in ctx
        assert "team_members" in ctx

        ctx = company.get_section_context("재무계획")
        assert "funding_amount" in ctx
        assert "total_budget" in ctx

    def test_empty_company(self):
        """빈 CompanyInfo 생성."""
        company = CompanyInfo()
        assert company.company_name == ""
        assert company.total_budget == 0
        assert company.has_investment_bonus is False


# ── 프롬프트 템플릿 테스트 ─────────────────────────────────────────

class TestPromptTemplates:
    """프롬프트 템플릿 파일 테스트."""

    def test_prompts_dir_exists(self):
        """프롬프트 디렉토리 존재."""
        assert PROMPTS_DIR.exists()
        assert PROMPTS_DIR.is_dir()

    def test_all_template_files_exist(self):
        """모든 섹션의 템플릿 파일 존재."""
        for section_def in SECTION_DEFS:
            template_path = PROMPTS_DIR / section_def["template_file"]
            assert template_path.exists(), f"템플릿 없음: {template_path}"

    def test_template_files_not_empty(self):
        """템플릿 파일이 비어있지 않음."""
        for section_def in SECTION_DEFS:
            template_path = PROMPTS_DIR / section_def["template_file"]
            content = template_path.read_text(encoding="utf-8")
            assert len(content) > 100, f"템플릿이 너무 짧음: {template_path}"

    def test_template_files_have_variables(self):
        """템플릿 파일에 치환 변수가 포함."""
        for section_def in SECTION_DEFS:
            template_path = PROMPTS_DIR / section_def["template_file"]
            content = template_path.read_text(encoding="utf-8")
            assert "{" in content, f"변수 없음: {template_path}"

    def test_nine_prompt_templates(self):
        """9개의 프롬프트 템플릿."""
        templates = list(PROMPTS_DIR.glob("*.txt"))
        assert len(templates) == 9


# ── PlanGenerator 테스트 ──────────────────────────────────────────

class TestPlanGenerator:
    """PlanGenerator 테스트."""

    @pytest.fixture
    def generator(self):
        """기본 생성기 fixture."""
        company = create_sample_company()
        return PlanGenerator(company_info=company)

    def test_init(self, generator):
        """생성기 초기화."""
        assert generator.company.company_name == "(주)스마트팜테크"

    def test_build_prompt(self, generator):
        """프롬프트 빌드."""
        prompt = generator.build_prompt("problem_recognition")
        assert "문제인식" in prompt
        assert "(주)스마트팜테크" in prompt
        assert "김창업" in prompt
        assert "AI 기반 스마트팜" in prompt

    def test_build_prompt_all_sections(self, generator):
        """모든 섹션 프롬프트 빌드."""
        for section_def in SECTION_DEFS:
            prompt = generator.build_prompt(section_def["key"])
            assert len(prompt) > 100
            # 변수가 치환되었는지 확인 (회사명이 포함)
            assert "(주)스마트팜테크" in prompt

    def test_build_prompt_invalid_section(self, generator):
        """존재하지 않는 섹션 프롬프트 빌드 시 에러."""
        with pytest.raises(ValueError, match="알 수 없는 섹션"):
            generator.build_prompt("nonexistent")

    def test_generate_section(self, generator):
        """섹션 콘텐츠 생성."""
        section = generator.generate_section("company_overview")
        assert isinstance(section, GeneratedSection)
        assert section.title == "기업 개요 및 일반현황"
        assert "(주)스마트팜테크" in section.content
        assert section.word_count > 0
        assert len(section.prompt) > 0

    def test_generate_problem_section(self, generator):
        """문제인식 섹션 생성 — 평가 기준 포함."""
        section = generator.generate_section("problem_recognition")
        assert "문제인식" in section.evaluation_category or "문제인식" in section.title
        assert "시설원예" in section.content  # 샘플 데이터의 문제 배경
        assert section.metadata.get("mode") == "fill"

    def test_generate_full_plan(self, generator):
        """전체 사업계획서 생성."""
        plan = generator.generate_full_plan()
        assert isinstance(plan, GeneratedPlan)
        assert len(plan.sections) == len(SECTION_DEFS)
        assert plan.company_name == "(주)스마트팜테크"
        assert plan.total_word_count > 0

        # 모든 섹션에 콘텐츠가 있는지 확인
        for section in plan.sections:
            assert section.word_count > 0
            assert len(section.content) > 0

    def test_plan_to_json(self, generator):
        """사업계획서 JSON 변환."""
        plan = generator.generate_full_plan()
        json_str = plan.to_json()
        data = json.loads(json_str)
        assert data["company_name"] == "(주)스마트팜테크"
        assert len(data["sections"]) == len(SECTION_DEFS)

    def test_save_prompts(self, generator, tmp_path):
        """프롬프트 파일 저장."""
        saved = generator.save_prompts(tmp_path / "prompts")
        assert len(saved) == len(SECTION_DEFS)
        for filepath in saved:
            assert filepath.exists()
            content = filepath.read_text(encoding="utf-8")
            assert len(content) > 100

    def test_save_plan(self, generator, tmp_path):
        """사업계획서 파일 저장."""
        plan_path = generator.save_plan(tmp_path / "plan.json")
        assert plan_path.exists()
        data = json.loads(plan_path.read_text(encoding="utf-8"))
        assert data["company_name"] == "(주)스마트팜테크"

    def test_evaluation_criteria_in_metadata(self, generator):
        """평가 기준이 메타데이터에 포함."""
        plan = generator.generate_full_plan()
        assert "evaluation_criteria" in plan.metadata
        criteria = plan.metadata["evaluation_criteria"]
        assert "문제인식" in criteria
        assert "실현가능성" in criteria
        assert "성장전략" in criteria
        assert "팀구성" in criteria

    def test_budget_ratio_validation(self, generator):
        """사업비 비율 검증이 콘텐츠에 포함."""
        section = generator.generate_section("growth_strategy")
        assert "비율 준수 확인" in section.content

    def test_fill_content_tables(self, generator):
        """표 데이터가 콘텐츠에 포함."""
        # 매출 실적 표
        section = generator.generate_section("business_model")
        assert "목표시장(고객)" in section.content
        assert "스마트팜 시스템" in section.content

        # 팀 구성 표
        section = generator.generate_section("team")
        assert "이개발" in section.content or "CTO" in section.content

        # 사업비 표
        section = generator.generate_section("growth_strategy")
        assert "재료비" in section.content or "정부지원" in section.content


# ── E2E 파이프라인 테스트 ──────────────────────────────────────────

class TestE2EPipeline:
    """End-to-End 파이프라인 테스트."""

    def test_full_pipeline_with_sample(self, tmp_path):
        """샘플 데이터로 전체 파이프라인 실행."""
        # 1. CompanyInfo 생성
        company = create_sample_company()
        assert company.company_name

        # 2. PlanGenerator 생성
        gen = PlanGenerator(company_info=company)

        # 3. 프롬프트 저장
        prompts_dir = tmp_path / "prompts"
        saved_prompts = gen.save_prompts(prompts_dir)
        assert len(saved_prompts) == 9

        # 4. 전체 생성
        plan = gen.generate_full_plan()
        assert len(plan.sections) == 9
        assert plan.total_word_count > 0

        # 5. JSON 저장
        plan_path = tmp_path / "plan.json"
        plan_path.write_text(plan.to_json(), encoding="utf-8")
        assert plan_path.exists()

        # 6. 섹션 파일 저장
        sections_dir = tmp_path / "sections"
        sections_dir.mkdir()
        for sec in plan.sections:
            sec_path = sections_dir / f"{sec.section_index+1:02d}_{sec.section_key}.md"
            sec_path.write_text(f"# {sec.title}\n\n{sec.content}\n", encoding="utf-8")

        section_files = list(sections_dir.glob("*.md"))
        assert len(section_files) == 9

    @pytest.mark.skipif(not HWP_FILE.exists(), reason="HWP 테스트 파일 없음")
    def test_pipeline_with_hwp_analysis(self, tmp_path):
        """HWP 양식 분석 포함 파이프라인."""
        from sandoc.analyzer import analyze_template

        # 양식 분석
        ta = analyze_template(HWP_FILE)
        template_data = {
            "sections": [{"title": s.title} for s in ta.sections],
            "tables_count": ta.tables_count,
        }

        # 생성
        company = create_sample_company()
        gen = PlanGenerator(
            company_info=company,
            template_analysis=template_data,
        )
        plan = gen.generate_full_plan()
        assert len(plan.sections) == 9

    @pytest.mark.skipif(not PDF_FILE.exists(), reason="PDF 테스트 파일 없음")
    def test_pipeline_with_pdf_analysis(self, tmp_path):
        """PDF 공고문 분석 포함 파이프라인."""
        from sandoc.analyzer import analyze_announcement

        # 공고문 분석
        aa = analyze_announcement(PDF_FILE)
        announcement_data = {
            "title": aa.title,
            "scoring_criteria": [{"item": c.item, "score": c.score} for c in aa.scoring_criteria],
        }

        # 생성
        company = create_sample_company()
        gen = PlanGenerator(
            company_info=company,
            announcement_analysis=announcement_data,
        )
        plan = gen.generate_full_plan()
        assert len(plan.sections) == 9

    @pytest.mark.skipif(
        not (HWP_FILE.exists() and PDF_FILE.exists()),
        reason="테스트 파일 없음"
    )
    def test_full_pipeline_with_all_inputs(self):
        """모든 입력(HWP+PDF+스타일)으로 전체 파이프라인 → output/ 저장."""
        from sandoc.analyzer import analyze_template, analyze_announcement

        # 분석
        ta = analyze_template(HWP_FILE)
        aa = analyze_announcement(PDF_FILE)

        style_data = {}
        if STYLE_FILE.exists():
            style_data = json.loads(STYLE_FILE.read_text(encoding="utf-8"))

        # 생성
        company = create_sample_company()
        gen = PlanGenerator(
            company_info=company,
            template_analysis={
                "sections": [{"title": s.title} for s in ta.sections],
                "tables_count": ta.tables_count,
            },
            announcement_analysis={
                "title": aa.title,
                "scoring_criteria": [{"item": c.item, "score": c.score} for c in aa.scoring_criteria],
            },
            style_profile=style_data,
        )

        # output 디렉토리에 저장
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # 프롬프트 저장
        prompts_dir = OUTPUT_DIR / "prompts"
        saved = gen.save_prompts(prompts_dir)
        assert len(saved) == 9

        # 전체 생성 및 저장
        plan = gen.generate_full_plan()
        plan_path = OUTPUT_DIR / "plan.json"
        plan_path.write_text(plan.to_json(), encoding="utf-8")

        # 회사 정보 저장
        company.save(OUTPUT_DIR / "company_info.json")

        # 섹션별 파일 저장
        sections_dir = OUTPUT_DIR / "sections"
        sections_dir.mkdir(parents=True, exist_ok=True)
        for sec in plan.sections:
            sec_path = sections_dir / f"{sec.section_index+1:02d}_{sec.section_key}.md"
            sec_path.write_text(f"# {sec.title}\n\n{sec.content}\n", encoding="utf-8")

        # 검증
        assert plan_path.exists()
        assert (OUTPUT_DIR / "company_info.json").exists()
        assert len(list(sections_dir.glob("*.md"))) == 9
        assert len(list(prompts_dir.glob("*.md"))) == 9

    def test_company_info_from_json_file(self, tmp_path):
        """JSON 파일에서 회사 정보 로드 후 생성."""
        company = create_sample_company()
        json_path = tmp_path / "company.json"
        company.save(json_path)

        # 파일에서 로드
        loaded = CompanyInfo.from_file(json_path)
        gen = PlanGenerator(company_info=loaded)
        plan = gen.generate_full_plan()

        assert plan.company_name == "(주)스마트팜테크"
        assert len(plan.sections) == 9


# ── 하위 호환 테스트 ──────────────────────────────────────────────

class TestLegacyCompat:
    """기존 함수 하위 호환 테스트."""

    def test_generate_section_legacy(self):
        """레거시 generate_section 함수."""
        from sandoc.generator import generate_section
        section = generate_section("테스트 섹션")
        assert isinstance(section, GeneratedSection)
        assert section.title == "테스트 섹션"

    def test_generate_plan_legacy(self):
        """레거시 generate_plan 함수."""
        from sandoc.generator import generate_plan
        plan = generate_plan()
        assert isinstance(plan, GeneratedPlan)
        assert len(plan.sections) == 6  # 레거시 기본 섹션 수
