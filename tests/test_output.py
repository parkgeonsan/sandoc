"""
test_output.py — HWPX 출력 엔진 및 출력 파이프라인 테스트

테스트 대상:
  - hwpx_engine.StyleMirror
  - hwpx_engine.HwpxBuilder
  - hwpx_engine.edit_hwpx_text
  - hwpx_engine.validate_hwpx
  - output.OutputPipeline
  - output.build_hwpx_from_plan / build_hwpx_from_json
  - cli.build 명령
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from sandoc.schema import CompanyInfo, create_sample_company
from sandoc.generator import PlanGenerator, GeneratedPlan, GeneratedSection, SECTION_DEFS
from sandoc.hwpx_engine import (
    StyleMirror,
    HwpxBuilder,
    edit_hwpx_text,
    validate_hwpx,
    _parse_rgb_to_hex,
)
from sandoc.output import (
    OutputPipeline,
    BuildResult,
    build_hwpx_from_plan,
    build_hwpx_from_json,
)


# ── 테스트 데이터 경로 ──────────────────────────────────────────────

DATA_DIR = Path(__file__).parent / "v1-data"
STYLE_FILE = DATA_DIR / "analysis" / "style-profile.json"


# ── StyleMirror 테스트 ──────────────────────────────────────────────

class TestStyleMirror:
    """StyleMirror 클래스 테스트."""

    def test_default_style(self):
        """기본 스타일 생성."""
        style = StyleMirror.default()
        assert style.get_paper_width_mm() == 210.0
        assert style.get_paper_height_mm() == 297.0

    def test_default_margins(self):
        """기본 여백."""
        style = StyleMirror.default()
        assert style.get_margin_mm("top") == 10.0
        assert style.get_margin_mm("bottom") == 15.0
        assert style.get_margin_mm("left") == 20.0
        assert style.get_margin_mm("right") == 20.0

    def test_default_font(self):
        """기본 폰트."""
        style = StyleMirror.default()
        assert style.get_font_name("bodyText") == "맑은 고딕"
        assert style.get_font_size_pt("bodyText") == 10.0

    def test_section_title_style(self):
        """섹션 제목 스타일."""
        style = StyleMirror.default()
        assert style.get_font_size_pt("sectionTitle") == 18.0
        assert style.get_alignment("sectionTitle") == "distribute"

    def test_line_spacing(self):
        """줄간격."""
        style = StyleMirror.default()
        assert style.get_line_spacing("default") == 160

    def test_font_list_default(self):
        """기본 폰트 리스트."""
        style = StyleMirror.default()
        font_list = style.get_font_list()
        assert len(font_list) >= 3
        assert "맑은 고딕" in font_list

    def test_char_style_fallback(self):
        """없는 스타일 → bodyText 폴백."""
        style = StyleMirror.default()
        cs = style.get_char_style("nonexistent")
        # bodyText 폴백
        assert cs.get("font") == "맑은 고딕"

    def test_from_dict(self):
        """딕셔너리에서 StyleMirror 생성."""
        data = {
            "paperSize": {"width": "200.0mm", "height": "280.0mm"},
            "margins": {"top": "15.0mm"},
            "characterStyles": {
                "bodyText": {"font": "나눔고딕", "size": "11pt"},
            },
        }
        style = StyleMirror(data)
        assert style.get_paper_width_mm() == 200.0
        assert style.get_font_name("bodyText") == "나눔고딕"
        assert style.get_font_size_pt("bodyText") == 11.0

    def test_slash_font_name(self):
        """'폰트A / 폰트B' 형태에서 첫 번째 사용."""
        data = {
            "characterStyles": {
                "bodyText": {"font": "HY헤드라인M / HY울릉도M", "size": "14pt"},
            },
        }
        style = StyleMirror(data)
        assert style.get_font_name("bodyText") == "HY헤드라인M"

    def test_range_font_size(self):
        """'14-16pt' 형태에서 첫 번째 사용."""
        data = {
            "characterStyles": {
                "bodyText": {"font": "맑은 고딕", "size": "14-16pt"},
            },
        }
        style = StyleMirror(data)
        assert style.get_font_size_pt("bodyText") == 14.0

    @pytest.mark.skipif(not STYLE_FILE.exists(), reason="스타일 프로파일 없음")
    def test_from_file(self):
        """실제 style-profile.json 로드."""
        style = StyleMirror.from_file(STYLE_FILE)
        assert style.get_paper_width_mm() == 210.0
        font_list = style.get_font_list()
        assert len(font_list) > 0
        assert "맑은 고딕" in font_list

    def test_from_file_not_found(self):
        """존재하지 않는 파일."""
        with pytest.raises(FileNotFoundError):
            StyleMirror.from_file("/nonexistent/style.json")


# ── HwpxBuilder 테스트 ──────────────────────────────────────────────

class TestHwpxBuilder:
    """HwpxBuilder 클래스 테스트."""

    def test_build_empty(self, tmp_path):
        """빈 문서 빌드."""
        builder = HwpxBuilder()
        output = tmp_path / "empty.hwpx"
        result = builder.build(output)
        assert result.exists()
        assert result.suffix == ".hwpx"

    def test_build_creates_zip(self, tmp_path):
        """빌드 결과가 유효한 ZIP."""
        builder = HwpxBuilder()
        builder.add_section("테스트", "테스트 콘텐츠입니다.")
        output = tmp_path / "test.hwpx"
        builder.build(output)
        assert zipfile.is_zipfile(output)

    def test_build_has_mimetype(self, tmp_path):
        """mimetype 파일 존재 및 내용 확인."""
        builder = HwpxBuilder()
        builder.add_section("제목", "내용")
        output = tmp_path / "test.hwpx"
        builder.build(output)

        with zipfile.ZipFile(output) as zf:
            assert "mimetype" in zf.namelist()
            mt = zf.read("mimetype").decode("utf-8")
            assert mt == "application/hwp+zip"

    def test_build_has_required_files(self, tmp_path):
        """필수 파일 존재 확인."""
        builder = HwpxBuilder()
        builder.add_section("제목", "내용")
        output = tmp_path / "test.hwpx"
        builder.build(output)

        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
            assert "mimetype" in names
            assert "META-INF/manifest.xml" in names
            assert "Contents/content.hpf" in names
            assert "Contents/header.xml" in names
            assert "Contents/section0.xml" in names

    def test_build_section_xml_contains_text(self, tmp_path):
        """섹션 XML에 삽입한 텍스트가 포함."""
        builder = HwpxBuilder()
        builder.add_section("테스트 제목", "안녕하세요 테스트입니다.")
        output = tmp_path / "test.hwpx"
        builder.build(output)

        with zipfile.ZipFile(output) as zf:
            section_xml = zf.read("Contents/section0.xml").decode("utf-8")
            assert "테스트 제목" in section_xml
            assert "안녕하세요 테스트입니다" in section_xml

    def test_build_multiple_sections(self, tmp_path):
        """여러 섹션 추가."""
        builder = HwpxBuilder()
        builder.add_section("섹션 1", "내용 1")
        builder.add_section("섹션 2", "내용 2")
        builder.add_section("섹션 3", "내용 3")
        output = tmp_path / "multi.hwpx"
        builder.build(output)

        with zipfile.ZipFile(output) as zf:
            section_xml = zf.read("Contents/section0.xml").decode("utf-8")
            assert "섹션 1" in section_xml
            assert "섹션 2" in section_xml
            assert "섹션 3" in section_xml

    def test_build_with_style_profile(self, tmp_path):
        """스타일 프로파일 적용 빌드."""
        style = StyleMirror.default()
        builder = HwpxBuilder(style=style)
        builder.add_section("제목", "본문")
        output = tmp_path / "styled.hwpx"
        builder.build(output)

        with zipfile.ZipFile(output) as zf:
            header_xml = zf.read("Contents/header.xml").decode("utf-8")
            # 폰트 정의 포함 확인 (레거시: FontFace/FontRef, hwpx-mcp-server: head XML)
            assert ("FontFace" in header_xml or "FontRef" in header_xml
                    or "head" in header_xml.lower())

    def test_build_with_multiline_content(self, tmp_path):
        """여러 줄 콘텐츠."""
        content = "\n".join([
            "◦ 첫 번째 항목",
            "  - 세부 내용 A",
            "  - 세부 내용 B",
            "",
            "◦ 두 번째 항목",
            "  - 세부 내용 C",
        ])
        builder = HwpxBuilder()
        builder.add_section("개요", content)
        output = tmp_path / "multiline.hwpx"
        builder.build(output)
        assert output.exists()

    def test_build_with_table_rows(self, tmp_path):
        """표 행(| 형식) 콘텐츠."""
        content = "\n".join([
            "◦ 매출 실적",
            "| 순번 | 항목 | 금액 |",
            "|------|------|------|",
            "| 1 | A제품 | 1억원 |",
            "| 2 | B제품 | 2억원 |",
        ])
        builder = HwpxBuilder()
        builder.add_section("실적", content)
        output = tmp_path / "table.hwpx"
        builder.build(output)

        with zipfile.ZipFile(output) as zf:
            xml = zf.read("Contents/section0.xml").decode("utf-8")
            assert "A제품" in xml
            assert "B제품" in xml

    @pytest.mark.skipif(not STYLE_FILE.exists(), reason="스타일 프로파일 없음")
    def test_build_with_real_style_profile(self, tmp_path):
        """실제 스타일 프로파일로 빌드."""
        style = StyleMirror.from_file(STYLE_FILE)
        builder = HwpxBuilder(style=style)
        builder.add_section("1. 문제인식(Problem)", "테스트 내용입니다.")
        output = tmp_path / "real_style.hwpx"
        builder.build(output)
        assert output.exists()


# ── validate_hwpx 테스트 ──────────────────────────────────────────

class TestValidateHwpx:
    """validate_hwpx 함수 테스트."""

    def test_validate_valid_hwpx(self, tmp_path):
        """유효한 HWPX 검증."""
        builder = HwpxBuilder()
        builder.add_section("테스트", "내용")
        output = tmp_path / "valid.hwpx"
        builder.build(output)

        result = validate_hwpx(output)
        assert result["valid"] is True
        assert result["has_mimetype"] is True
        assert result["has_content_hpf"] is True
        assert result["has_sections"] is True
        assert result["section_count"] == 1
        assert len(result["errors"]) == 0

    def test_validate_nonexistent(self):
        """존재하지 않는 파일."""
        result = validate_hwpx("/nonexistent/file.hwpx")
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_validate_invalid_zip(self, tmp_path):
        """유효하지 않은 ZIP 파일."""
        bad = tmp_path / "bad.hwpx"
        bad.write_text("not a zip file")
        result = validate_hwpx(bad)
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_validate_wrong_mimetype(self, tmp_path):
        """잘못된 mimetype."""
        output = tmp_path / "wrong_mt.hwpx"
        with zipfile.ZipFile(output, "w") as zf:
            zf.writestr("mimetype", "application/wrong")
            zf.writestr("Contents/content.hpf", "<xml/>")
            zf.writestr("Contents/section0.xml", "<xml/>")

        result = validate_hwpx(output)
        assert result["valid"] is False
        assert any("mimetype" in e for e in result["errors"])


# ── edit_hwpx_text 테스트 ─────────────────────────────────────────

class TestEditHwpxText:
    """edit_hwpx_text 함수 테스트."""

    def test_edit_text_replacement(self, tmp_path):
        """텍스트 교체."""
        # HWPX 파일 생성
        builder = HwpxBuilder()
        builder.add_section("OO기업", "OO기업은 최고입니다.")
        source = tmp_path / "source.hwpx"
        builder.build(source)

        # 텍스트 교체
        edited = tmp_path / "edited.hwpx"
        edit_hwpx_text(source, {"OO기업": "스마트팜테크"}, edited)

        # 교체 확인
        with zipfile.ZipFile(edited) as zf:
            xml = zf.read("Contents/section0.xml").decode("utf-8")
            assert "스마트팜테크" in xml
            assert "OO기업" not in xml

    def test_edit_text_inplace(self, tmp_path):
        """인플레이스 교체."""
        builder = HwpxBuilder()
        builder.add_section("교체전", "내용")
        target = tmp_path / "target.hwpx"
        builder.build(target)

        edit_hwpx_text(target, {"교체전": "교체후"})

        with zipfile.ZipFile(target) as zf:
            xml = zf.read("Contents/section0.xml").decode("utf-8")
            assert "교체후" in xml

    def test_edit_text_not_found(self):
        """존재하지 않는 HWPX 파일."""
        with pytest.raises(FileNotFoundError):
            edit_hwpx_text("/nonexistent.hwpx", {"a": "b"})

    def test_edit_text_bad_zip(self, tmp_path):
        """유효하지 않은 ZIP 파일."""
        bad = tmp_path / "bad.hwpx"
        bad.write_text("not a zip")
        with pytest.raises(ValueError):
            edit_hwpx_text(bad, {"a": "b"})


# ── _parse_rgb_to_hex 테스트 ──────────────────────────────────────

class TestParseRgbToHex:
    """색상 변환 테스트."""

    def test_basic(self):
        assert _parse_rgb_to_hex("rgb(0,0,0)") == "#000000"

    def test_blue(self):
        assert _parse_rgb_to_hex("rgb(0,0,255)") == "#0000FF"

    def test_white(self):
        assert _parse_rgb_to_hex("rgb(255,255,255)") == "#FFFFFF"

    def test_with_spaces(self):
        assert _parse_rgb_to_hex("rgb( 128 , 64 , 32 )") == "#804020"

    def test_invalid(self):
        assert _parse_rgb_to_hex("not-a-color") == "#000000"


# ── OutputPipeline 테스트 ─────────────────────────────────────────

class TestOutputPipeline:
    """OutputPipeline 클래스 테스트."""

    def test_run_sample(self, tmp_path):
        """샘플 데이터로 전체 파이프라인 실행."""
        company = create_sample_company()
        pipeline = OutputPipeline(
            company_info=company,
            output_dir=tmp_path / "output",
        )
        result = pipeline.run()

        assert result.success is True
        assert result.section_count == 9
        assert result.total_chars > 0
        assert Path(result.hwpx_path).exists()
        assert Path(result.plan_json_path).exists()

    def test_run_creates_hwpx(self, tmp_path):
        """HWPX 파일 생성 확인."""
        company = create_sample_company()
        pipeline = OutputPipeline(
            company_info=company,
            output_dir=tmp_path / "output",
        )
        result = pipeline.run()

        hwpx = Path(result.hwpx_path)
        assert hwpx.exists()
        assert zipfile.is_zipfile(hwpx)

    def test_run_creates_plan_json(self, tmp_path):
        """plan.json 생성 확인."""
        company = create_sample_company()
        pipeline = OutputPipeline(
            company_info=company,
            output_dir=tmp_path / "output",
        )
        result = pipeline.run()

        plan_path = Path(result.plan_json_path)
        assert plan_path.exists()
        data = json.loads(plan_path.read_text(encoding="utf-8"))
        assert data["company_name"] == "(주)스마트팜테크"
        assert len(data["sections"]) == 9

    def test_run_creates_sections(self, tmp_path):
        """섹션 파일 생성 확인."""
        company = create_sample_company()
        pipeline = OutputPipeline(
            company_info=company,
            output_dir=tmp_path / "output",
        )
        result = pipeline.run()

        sections_dir = Path(result.sections_dir)
        assert sections_dir.exists()
        md_files = list(sections_dir.glob("*.md"))
        assert len(md_files) == 9

    def test_run_creates_prompts(self, tmp_path):
        """프롬프트 파일 생성 확인."""
        company = create_sample_company()
        pipeline = OutputPipeline(
            company_info=company,
            output_dir=tmp_path / "output",
        )
        result = pipeline.run()

        prompts_dir = Path(result.prompts_dir)
        assert prompts_dir.exists()
        prompt_files = list(prompts_dir.glob("*.md"))
        assert len(prompt_files) == 9

    def test_run_with_existing_plan(self, tmp_path):
        """기존 GeneratedPlan 전달."""
        company = create_sample_company()
        gen = PlanGenerator(company_info=company)
        plan = gen.generate_full_plan()

        pipeline = OutputPipeline(
            company_info=company,
            output_dir=tmp_path / "output",
            plan=plan,
        )
        result = pipeline.run()
        assert result.success is True

    def test_run_with_plan_json(self, tmp_path):
        """plan.json 파일에서 로드."""
        company = create_sample_company()
        gen = PlanGenerator(company_info=company)
        plan = gen.generate_full_plan()

        plan_json = tmp_path / "plan.json"
        plan_json.write_text(plan.to_json(), encoding="utf-8")

        pipeline = OutputPipeline(
            company_info=company,
            output_dir=tmp_path / "output",
            plan_json_path=plan_json,
        )
        result = pipeline.run()
        assert result.success is True

    def test_run_prompts_only(self, tmp_path):
        """프롬프트만 생성 모드."""
        company = create_sample_company()
        pipeline = OutputPipeline(
            company_info=company,
            output_dir=tmp_path / "output",
        )
        result = pipeline.run(prompts_only=True)

        assert result.success is True
        assert result.hwpx_path == ""  # HWPX 미생성
        assert result.prompts_dir != ""

    @pytest.mark.skipif(not STYLE_FILE.exists(), reason="스타일 프로파일 없음")
    def test_run_with_style_profile(self, tmp_path):
        """스타일 프로파일 적용."""
        company = create_sample_company()
        pipeline = OutputPipeline(
            company_info=company,
            output_dir=tmp_path / "output",
            style_profile_path=STYLE_FILE,
        )
        result = pipeline.run()
        assert result.success is True

    def test_run_with_style_data(self, tmp_path):
        """스타일 프로파일 딕셔너리 직접 전달."""
        company = create_sample_company()
        style_data = {
            "paperSize": {"width": "210.0mm", "height": "297.0mm"},
            "margins": {"top": "10.0mm", "bottom": "15.0mm", "left": "20.0mm", "right": "20.0mm"},
            "characterStyles": {
                "bodyText": {"font": "나눔고딕", "size": "10pt"},
            },
        }
        pipeline = OutputPipeline(
            company_info=company,
            output_dir=tmp_path / "output",
            style_profile_data=style_data,
        )
        result = pipeline.run()
        assert result.success is True

    def test_validation_result(self, tmp_path):
        """검증 결과 확인."""
        company = create_sample_company()
        pipeline = OutputPipeline(
            company_info=company,
            output_dir=tmp_path / "output",
        )
        result = pipeline.run()

        assert "valid" in result.validation
        assert result.validation["valid"] is True
        assert result.validation["has_mimetype"] is True
        assert result.validation["section_count"] >= 1


# ── build_hwpx_from_plan / build_hwpx_from_json 테스트 ─────────

class TestConvenienceFunctions:
    """편의 함수 테스트."""

    def test_build_from_plan(self, tmp_path):
        """GeneratedPlan → HWPX."""
        company = create_sample_company()
        gen = PlanGenerator(company_info=company)
        plan = gen.generate_full_plan()

        output = tmp_path / "from_plan.hwpx"
        result = build_hwpx_from_plan(plan, output)

        assert result.exists()
        assert zipfile.is_zipfile(result)
        v = validate_hwpx(result)
        assert v["valid"] is True

    def test_build_from_json(self, tmp_path):
        """plan.json → HWPX."""
        company = create_sample_company()
        gen = PlanGenerator(company_info=company)
        plan = gen.generate_full_plan()

        json_path = tmp_path / "plan.json"
        json_path.write_text(plan.to_json(), encoding="utf-8")

        output = tmp_path / "from_json.hwpx"
        result = build_hwpx_from_json(json_path, output)

        assert result.exists()
        v = validate_hwpx(result)
        assert v["valid"] is True

    @pytest.mark.skipif(not STYLE_FILE.exists(), reason="스타일 프로파일 없음")
    def test_build_from_plan_with_style(self, tmp_path):
        """스타일 프로파일 적용 빌드."""
        company = create_sample_company()
        gen = PlanGenerator(company_info=company)
        plan = gen.generate_full_plan()

        output = tmp_path / "styled.hwpx"
        result = build_hwpx_from_plan(plan, output, style_profile_path=STYLE_FILE)
        assert result.exists()


# ── BuildResult 테스트 ────────────────────────────────────────────

class TestBuildResult:
    """BuildResult 데이터 클래스 테스트."""

    def test_defaults(self):
        """기본값."""
        result = BuildResult()
        assert result.success is False
        assert result.hwpx_path == ""
        assert result.errors == []

    def test_to_dict(self):
        """딕셔너리 변환."""
        result = BuildResult(success=True, section_count=9, total_chars=5000)
        d = result.to_dict()
        assert d["success"] is True
        assert d["section_count"] == 9
        assert d["total_chars"] == 5000


# ── E2E 빌드 파이프라인 테스트 ────────────────────────────────────

class TestE2EBuild:
    """End-to-End 빌드 파이프라인 테스트."""

    def test_full_build_pipeline(self, tmp_path):
        """전체 빌드 파이프라인: CompanyInfo → PlanGenerator → OutputPipeline → HWPX."""
        # 1. 회사 정보
        company = create_sample_company()

        # 2. 콘텐츠 생성
        gen = PlanGenerator(company_info=company)
        plan = gen.generate_full_plan()
        assert len(plan.sections) == 9

        # 3. HWPX 빌드
        output_dir = tmp_path / "full_build"
        pipeline = OutputPipeline(
            company_info=company,
            output_dir=output_dir,
            plan=plan,
        )
        result = pipeline.run()

        # 4. 검증
        assert result.success is True
        assert result.section_count == 9
        assert result.total_chars > 0

        # HWPX 파일 존재 및 유효
        hwpx = Path(result.hwpx_path)
        assert hwpx.exists()
        v = validate_hwpx(hwpx)
        assert v["valid"] is True
        assert v["file_count"] >= 5  # mimetype, manifest, content.hpf, header, section0

        # plan.json 존재 및 내용 확인
        plan_data = json.loads(Path(result.plan_json_path).read_text(encoding="utf-8"))
        assert plan_data["company_name"] == "(주)스마트팜테크"

        # 섹션 .md 파일 존재
        sections = list(Path(result.sections_dir).glob("*.md"))
        assert len(sections) == 9

        # 프롬프트 파일 존재
        prompts = list(Path(result.prompts_dir).glob("*.md"))
        assert len(prompts) == 9

        # 회사 정보 JSON 존재
        assert (output_dir / "company_info.json").exists()

    def test_build_roundtrip_plan_json(self, tmp_path):
        """plan.json 왕복: 생성 → 저장 → 로드 → HWPX 빌드."""
        company = create_sample_company()
        gen = PlanGenerator(company_info=company)
        plan = gen.generate_full_plan()

        # 저장
        plan_json = tmp_path / "plan.json"
        plan_json.write_text(plan.to_json(), encoding="utf-8")

        # 새 pipeline으로 로드 후 빌드
        pipeline = OutputPipeline(
            company_info=company,
            output_dir=tmp_path / "roundtrip",
            plan_json_path=plan_json,
        )
        result = pipeline.run()
        assert result.success is True
        assert result.section_count == 9

    def test_hwpx_content_integrity(self, tmp_path):
        """HWPX 내부 XML에 회사 정보 포함 확인."""
        company = create_sample_company()
        pipeline = OutputPipeline(
            company_info=company,
            output_dir=tmp_path / "integrity",
        )
        result = pipeline.run()

        with zipfile.ZipFile(result.hwpx_path) as zf:
            section_xml = zf.read("Contents/section0.xml").decode("utf-8")
            # 회사명이 포함되어야 함
            assert "(주)스마트팜테크" in section_xml
            # 아이템명이 포함되어야 함
            assert "스마트팜" in section_xml
