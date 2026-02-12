"""
test_e2e.py — 사업계획서 생성 파이프라인 End-to-End 테스트

테스트 흐름:
  1. 샘플 CompanyInfo 생성
  2. (옵션) HWP 양식 파싱 → 분석
  3. (옵션) PDF 공고문 파싱 → 분석
  4. PlanGenerator로 프롬프트 빌드
  5. 콘텐츠 생성 (fill 모드)
  6. HWPX 빌드 및 검증
  7. 결과 저장 및 검증
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

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
from sandoc.hwpx_engine import (
    StyleMirror,
    HwpxBuilder,
    validate_hwpx,
)
from sandoc.output import (
    OutputPipeline,
    BuildResult,
    build_hwpx_from_plan,
    build_hwpx_from_json,
)

# ── 테스트 데이터 경로 ─────────────────────────────────────────────

DATA_DIR = Path(__file__).parent / "v1-data"
OUTPUT_DIR = DATA_DIR / "output"
DEMO_DIR = Path(__file__).parent.parent / "demo"

HWP_FILE = DATA_DIR / "[별첨 1] 2025년도 창업도약패키지(일반형) 사업계획서 양식.hwp"
PDF_FILE = DATA_DIR / "[공고문] 2025년도 창업도약패키지(일반형) 창업기업 모집 수정공고.pdf"
STYLE_FILE = DATA_DIR / "analysis" / "style-profile.json"
DEMO_COMPANY_JSON = DEMO_DIR / "sample_company.json"


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


# ── E2E 전체 파이프라인 (CompanyInfo → Generate → Build → HWPX) ──

class TestE2EFullPipeline:
    """
    Phase 6 — 전체 E2E 데모 파이프라인 테스트.

    CompanyInfo JSON → PlanGenerator → OutputPipeline → HWPX → 검증
    """

    def test_sample_company_full_pipeline(self, tmp_path):
        """내장 샘플 회사: CompanyInfo → Generate → Build → HWPX 검증."""
        company = create_sample_company()
        output_dir = tmp_path / "e2e_sample"

        # 파이프라인 실행
        pipeline = OutputPipeline(
            company_info=company,
            output_dir=output_dir,
        )
        result = pipeline.run()

        # 빌드 성공
        assert result.success is True
        assert result.section_count == 9
        assert result.total_chars > 1000

        # HWPX 파일 존재 및 유효
        hwpx_path = Path(result.hwpx_path)
        assert hwpx_path.exists()
        assert hwpx_path.suffix == ".hwpx"
        assert zipfile.is_zipfile(hwpx_path)

        # HWPX 구조 검증
        v = validate_hwpx(hwpx_path)
        assert v["valid"] is True
        assert v["has_mimetype"] is True
        assert v["has_content_hpf"] is True
        assert v["has_header"] is True
        assert v["has_sections"] is True
        assert v["section_count"] >= 1
        assert v["file_count"] >= 5
        assert len(v["errors"]) == 0

        # plan.json 존재 및 구조
        plan_path = Path(result.plan_json_path)
        assert plan_path.exists()
        plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
        assert plan_data["company_name"] == "(주)스마트팜테크"
        assert len(plan_data["sections"]) == 9
        assert plan_data["total_word_count"] > 0

        # 섹션 파일 9개 존재
        sections_dir = Path(result.sections_dir)
        assert sections_dir.exists()
        md_files = sorted(sections_dir.glob("*.md"))
        assert len(md_files) == 9

        # 프롬프트 파일 9개 존재
        prompts_dir = Path(result.prompts_dir)
        assert prompts_dir.exists()
        prompt_files = list(prompts_dir.glob("*.md"))
        assert len(prompt_files) == 9

        # company_info.json 존재
        assert (output_dir / "company_info.json").exists()

    @pytest.mark.skipif(
        not DEMO_COMPANY_JSON.exists(),
        reason="demo/sample_company.json 없음"
    )
    def test_custom_company_json_full_pipeline(self, tmp_path):
        """외부 JSON 파일에서 회사 정보 로드 → 전체 파이프라인 → HWPX 검증."""
        # 1. JSON 파일에서 CompanyInfo 로드
        company = CompanyInfo.from_file(DEMO_COMPANY_JSON)
        assert company.company_name == "(주)메디랩AI"
        assert company.item_name == "AI 기반 의료영상 자동 판독 보조 시스템"
        assert company.total_budget > 0

        # 2. 파이프라인 실행
        output_dir = tmp_path / "e2e_custom"
        pipeline = OutputPipeline(
            company_info=company,
            output_dir=output_dir,
        )
        result = pipeline.run()

        # 3. 빌드 성공
        assert result.success is True
        assert result.section_count == 9
        assert result.total_chars > 1000

        # 4. HWPX 검증
        v = validate_hwpx(result.hwpx_path)
        assert v["valid"] is True
        assert v["file_count"] >= 5

        # 5. HWPX 내부 XML에 회사 정보 포함 확인
        with zipfile.ZipFile(result.hwpx_path) as zf:
            section_xml = zf.read("Contents/section0.xml").decode("utf-8")
            assert "(주)메디랩AI" in section_xml
            assert "의료영상" in section_xml

    def test_hwpx_xml_structure_validation(self, tmp_path):
        """HWPX 내부 XML 구조 상세 검증."""
        company = create_sample_company()
        pipeline = OutputPipeline(
            company_info=company,
            output_dir=tmp_path / "xml_check",
        )
        result = pipeline.run()
        assert result.success is True

        with zipfile.ZipFile(result.hwpx_path) as zf:
            # 1. mimetype 확인
            mt = zf.read("mimetype").decode("utf-8").strip()
            assert mt == "application/hwp+zip"

            # 2. manifest.xml 유효한 XML
            manifest_xml = zf.read("META-INF/manifest.xml").decode("utf-8")
            manifest_root = ET.fromstring(manifest_xml)
            assert "manifest" in manifest_root.tag

            # 3. content.hpf 유효한 XML
            hpf_xml = zf.read("Contents/content.hpf").decode("utf-8")
            hpf_root = ET.fromstring(hpf_xml)
            # ha:HWPDocumentPackage 또는 HWPDocumentPackage
            assert "HWPDocumentPackage" in hpf_root.tag

            # 4. header.xml 유효한 XML (폰트, 문자모양, 문단모양)
            header_xml = zf.read("Contents/header.xml").decode("utf-8")
            header_root = ET.fromstring(header_xml)
            assert "Head" in header_root.tag

            # 5. section0.xml 유효한 XML (본문 콘텐츠)
            section_xml = zf.read("Contents/section0.xml").decode("utf-8")
            section_root = ET.fromstring(section_xml)
            assert "Section" in section_root.tag

    def test_section_content_not_empty(self, tmp_path):
        """모든 섹션 콘텐츠가 비어있지 않음을 확인."""
        company = create_sample_company()
        gen = PlanGenerator(company_info=company)
        plan = gen.generate_full_plan()

        for section in plan.sections:
            assert len(section.content.strip()) > 50, (
                f"섹션 '{section.title}' 콘텐츠가 너무 짧음: {len(section.content)}자"
            )
            assert section.word_count > 0
            assert section.section_key != ""
            assert section.title != ""

    def test_section_keys_match_definitions(self, tmp_path):
        """생성된 섹션 키가 SECTION_DEFS와 일치."""
        company = create_sample_company()
        gen = PlanGenerator(company_info=company)
        plan = gen.generate_full_plan()

        expected_keys = [sd["key"] for sd in SECTION_DEFS]
        actual_keys = [s.section_key for s in plan.sections]
        assert actual_keys == expected_keys

    def test_style_profile_applied(self, tmp_path):
        """스타일 프로파일이 HWPX에 적용되는지 확인."""
        company = create_sample_company()

        # 커스텀 스타일 데이터
        custom_style = {
            "paperSize": {"width": "210.0mm", "height": "297.0mm"},
            "margins": {"top": "15.0mm", "bottom": "20.0mm", "left": "25.0mm", "right": "25.0mm"},
            "characterStyles": {
                "bodyText": {"font": "나눔고딕", "size": "11pt"},
                "sectionTitle": {"font": "나눔고딕", "size": "16pt", "bold": True},
            },
            "paragraphStyles": {
                "default": {"alignment": "justify", "lineSpacing": 180},
            },
        }

        pipeline = OutputPipeline(
            company_info=company,
            output_dir=tmp_path / "styled",
            style_profile_data=custom_style,
        )
        result = pipeline.run()
        assert result.success is True

        # header.xml에서 스타일 정보 확인
        with zipfile.ZipFile(result.hwpx_path) as zf:
            header_xml = zf.read("Contents/header.xml").decode("utf-8")
            # 폰트 크기가 반영됨 (11pt = Height 1100)
            assert "1100" in header_xml  # bodyText 11pt
            # 줄간격 반영됨
            assert "180" in header_xml  # lineSpacing 180

    def test_plan_json_roundtrip_build(self, tmp_path):
        """plan.json 저장 → 로드 → HWPX 빌드 왕복 테스트."""
        company = create_sample_company()

        # 1차: 생성 + 저장
        gen = PlanGenerator(company_info=company)
        plan = gen.generate_full_plan()
        plan_json = tmp_path / "plan.json"
        plan_json.write_text(plan.to_json(), encoding="utf-8")

        # 2차: plan.json에서 로드 후 HWPX 빌드
        pipeline = OutputPipeline(
            company_info=company,
            output_dir=tmp_path / "roundtrip",
            plan_json_path=plan_json,
        )
        result = pipeline.run()
        assert result.success is True
        assert result.section_count == 9

        # HWPX 검증
        v = validate_hwpx(result.hwpx_path)
        assert v["valid"] is True

    def test_hwpx_file_is_valid_zip(self, tmp_path):
        """HWPX 파일이 유효한 ZIP이며 올바른 엔트리 포함."""
        company = create_sample_company()
        pipeline = OutputPipeline(
            company_info=company,
            output_dir=tmp_path / "zip_check",
        )
        result = pipeline.run()
        assert result.success is True

        hwpx_path = Path(result.hwpx_path)
        assert zipfile.is_zipfile(hwpx_path)

        with zipfile.ZipFile(hwpx_path) as zf:
            names = zf.namelist()
            # 필수 파일 존재
            required = [
                "mimetype",
                "META-INF/manifest.xml",
                "Contents/content.hpf",
                "Contents/header.xml",
                "Contents/section0.xml",
            ]
            for req in required:
                assert req in names, f"필수 파일 없음: {req}"

            # 모든 파일이 읽을 수 있는지 (손상 없음)
            for name in names:
                data = zf.read(name)
                assert data is not None
                assert len(data) > 0, f"빈 파일: {name}"

    def test_hwpx_contains_all_section_titles(self, tmp_path):
        """HWPX에 모든 섹션 제목이 포함되어 있는지 확인."""
        company = create_sample_company()
        gen = PlanGenerator(company_info=company)
        plan = gen.generate_full_plan()

        pipeline = OutputPipeline(
            company_info=company,
            output_dir=tmp_path / "title_check",
            plan=plan,
        )
        result = pipeline.run()
        assert result.success is True

        with zipfile.ZipFile(result.hwpx_path) as zf:
            section_xml = zf.read("Contents/section0.xml").decode("utf-8")
            for section in plan.sections:
                assert section.title in section_xml, (
                    f"섹션 제목 '{section.title}' 이 HWPX에 없음"
                )

    def test_company_info_data_in_hwpx(self, tmp_path):
        """HWPX에 회사 정보 핵심 데이터가 포함되어 있는지 확인."""
        company = create_sample_company()
        pipeline = OutputPipeline(
            company_info=company,
            output_dir=tmp_path / "data_check",
        )
        result = pipeline.run()
        assert result.success is True

        with zipfile.ZipFile(result.hwpx_path) as zf:
            xml = zf.read("Contents/section0.xml").decode("utf-8")
            # 핵심 회사 정보
            assert company.company_name in xml
            assert company.ceo_name in xml
            assert company.item_name in xml
            # 재무 정보
            assert f"{company.total_budget:,}" in xml

    def test_multiple_companies_independent(self, tmp_path):
        """서로 다른 회사 정보로 독립적 빌드."""
        # 회사 1: 내장 샘플
        company1 = create_sample_company()
        out1 = tmp_path / "company1"
        p1 = OutputPipeline(company_info=company1, output_dir=out1)
        r1 = p1.run()
        assert r1.success is True

        # 회사 2: 수정된 정보
        company2 = create_sample_company()
        company2.company_name = "(주)테스트기업"
        company2.ceo_name = "홍길동"
        company2.item_name = "블록체인 기반 물류 추적 시스템"
        out2 = tmp_path / "company2"
        p2 = OutputPipeline(company_info=company2, output_dir=out2)
        r2 = p2.run()
        assert r2.success is True

        # 독립적 결과 확인
        with zipfile.ZipFile(r1.hwpx_path) as zf:
            xml1 = zf.read("Contents/section0.xml").decode("utf-8")
        with zipfile.ZipFile(r2.hwpx_path) as zf:
            xml2 = zf.read("Contents/section0.xml").decode("utf-8")

        assert "(주)스마트팜테크" in xml1
        assert "(주)테스트기업" in xml2
        assert "(주)테스트기업" not in xml1
        assert "(주)스마트팜테크" not in xml2

    def test_evaluation_categories_present(self, tmp_path):
        """평가 카테고리 4개(문제인식, 실현가능성, 성장전략, 팀구성)가 계획에 포함."""
        company = create_sample_company()
        gen = PlanGenerator(company_info=company)
        plan = gen.generate_full_plan()

        categories = {s.evaluation_category for s in plan.sections if s.evaluation_category}
        assert "문제인식" in categories
        assert "실현가능성" in categories
        assert "성장전략" in categories
        assert "팀구성" in categories

    def test_build_result_statistics(self, tmp_path):
        """BuildResult 통계가 정확한지 확인."""
        company = create_sample_company()
        pipeline = OutputPipeline(
            company_info=company,
            output_dir=tmp_path / "stats",
        )
        result = pipeline.run()

        assert result.success is True
        assert result.section_count == 9
        assert result.total_chars > 0
        assert result.hwpx_path != ""
        assert result.plan_json_path != ""
        assert result.sections_dir != ""
        assert result.prompts_dir != ""
        assert result.validation["valid"] is True
        assert len(result.errors) == 0


# ── CLI 명령 E2E 테스트 ──────────────────────────────────────────

class TestCLICommands:
    """CLI 명령어 E2E 테스트."""

    def test_generate_sample_cli(self, tmp_path):
        """sandoc generate --sample CLI 실행."""
        from click.testing import CliRunner
        from sandoc.cli import main

        runner = CliRunner()
        output_dir = str(tmp_path / "cli_gen")
        result = runner.invoke(main, ["generate", "--sample", "-o", output_dir])

        assert result.exit_code == 0
        assert "생성 완료" in result.output
        assert Path(output_dir).exists()

        # plan.json 존재
        plan_json = Path(output_dir) / "plan.json"
        assert plan_json.exists()

        # 섹션 파일 존재
        sections = list((Path(output_dir) / "sections").glob("*.md"))
        assert len(sections) == 9

    def test_build_sample_cli(self, tmp_path):
        """sandoc build --sample CLI 실행."""
        from click.testing import CliRunner
        from sandoc.cli import main

        runner = CliRunner()
        output_dir = str(tmp_path / "cli_build")
        result = runner.invoke(main, ["build", "--sample", "-o", output_dir])

        assert result.exit_code == 0
        assert "빌드 완료" in result.output

        # HWPX 파일 존재
        hwpx_files = list(Path(output_dir).glob("*.hwpx"))
        assert len(hwpx_files) >= 1

    @pytest.mark.skipif(
        not DEMO_COMPANY_JSON.exists(),
        reason="demo/sample_company.json 없음"
    )
    def test_build_with_custom_json_cli(self, tmp_path):
        """sandoc build --company-info demo/sample_company.json CLI 실행."""
        from click.testing import CliRunner
        from sandoc.cli import main

        runner = CliRunner()
        output_dir = str(tmp_path / "cli_custom")
        result = runner.invoke(main, [
            "build",
            "--company-info", str(DEMO_COMPANY_JSON),
            "-o", output_dir,
        ])

        assert result.exit_code == 0
        assert "빌드 완료" in result.output

        # HWPX 파일 검증
        hwpx_files = list(Path(output_dir).glob("*.hwpx"))
        assert len(hwpx_files) >= 1
        v = validate_hwpx(hwpx_files[0])
        assert v["valid"] is True

    def test_generate_prompts_only_cli(self, tmp_path):
        """sandoc generate --sample --prompts-only CLI 실행."""
        from click.testing import CliRunner
        from sandoc.cli import main

        runner = CliRunner()
        output_dir = str(tmp_path / "prompts_only")
        result = runner.invoke(main, [
            "generate", "--sample", "--prompts-only", "-o", output_dir,
        ])

        assert result.exit_code == 0
        assert "프롬프트 생성 완료" in result.output

        # 프롬프트 파일만 존재
        prompts = list((Path(output_dir) / "prompts").glob("*.md"))
        assert len(prompts) == 9

    def test_generate_no_args_error(self):
        """인자 없이 generate 실행 시 에러."""
        from click.testing import CliRunner
        from sandoc.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["generate"])
        assert result.exit_code != 0

    def test_build_no_args_error(self):
        """인자 없이 build 실행 시 에러."""
        from click.testing import CliRunner
        from sandoc.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["build"])
        assert result.exit_code != 0


# ── Demo 파일 테스트 ────────────────────────────────────────────

class TestDemoFiles:
    """데모 파일 유효성 테스트."""

    @pytest.mark.skipif(
        not DEMO_COMPANY_JSON.exists(),
        reason="demo/sample_company.json 없음"
    )
    def test_demo_company_json_loadable(self):
        """demo/sample_company.json이 로드 가능."""
        company = CompanyInfo.from_file(DEMO_COMPANY_JSON)
        assert company.company_name != ""
        assert company.ceo_name != ""
        assert company.item_name != ""
        assert company.total_budget > 0
        assert len(company.team_members) > 0
        assert len(company.budget_items) > 0

    @pytest.mark.skipif(
        not DEMO_COMPANY_JSON.exists(),
        reason="demo/sample_company.json 없음"
    )
    def test_demo_company_json_valid_structure(self):
        """demo/sample_company.json이 올바른 구조를 가짐."""
        company = CompanyInfo.from_file(DEMO_COMPANY_JSON)

        # 기본 정보
        assert len(company.company_name) > 0
        assert len(company.ceo_name) > 0
        assert len(company.business_registration_no) > 0
        assert len(company.establishment_date) > 0

        # 아이템 정보
        assert len(company.item_name) > 0
        assert len(company.item_summary) > 0
        assert len(company.product_description) > 0

        # 문제인식
        assert len(company.problem_background) > 0
        assert len(company.problem_statement) > 0
        assert len(company.development_motivation) > 0

        # 재무
        assert company.funding_amount > 0
        assert company.total_budget > 0
        assert len(company.budget_items) > 0

        # 팀
        assert len(company.ceo_background) > 0
        assert len(company.team_members) > 0

    @pytest.mark.skipif(
        not DEMO_COMPANY_JSON.exists(),
        reason="demo/sample_company.json 없음"
    )
    def test_demo_company_generates_all_sections(self):
        """demo 회사 정보로 모든 9개 섹션을 성공적으로 생성."""
        company = CompanyInfo.from_file(DEMO_COMPANY_JSON)
        gen = PlanGenerator(company_info=company)
        plan = gen.generate_full_plan()

        assert len(plan.sections) == 9
        assert plan.total_word_count > 0

        for section in plan.sections:
            assert section.word_count > 0, (
                f"섹션 '{section.title}'의 콘텐츠가 비어있음"
            )

    def test_demo_script_exists(self):
        """demo/run_demo.sh 존재."""
        demo_script = DEMO_DIR / "run_demo.sh"
        assert demo_script.exists(), "demo/run_demo.sh 없음"


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
