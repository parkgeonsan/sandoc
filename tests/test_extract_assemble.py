"""
tests/test_extract_assemble.py — extract 및 assemble 명령어 테스트

sandoc extract: 프로젝트 폴더에서 모든 정보 추출
sandoc assemble: 작성된 섹션 마크다운을 HWPX로 조립
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

# ── 프로젝트 경로 ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
V1_DATA = PROJECT_ROOT / "tests" / "v1-data"
SAMPLE_PROJECT = PROJECT_ROOT / "projects" / "sample-창업도약"

# 테스트 HWP/PDF 파일 존재 여부
HAS_HWP = any(V1_DATA.glob("*.hwp"))
HAS_PDF = any(V1_DATA.glob("*.pdf"))


# ═══════════════════════════════════════════════════════════════
#  EXTRACT 모듈 테스트
# ═══════════════════════════════════════════════════════════════

class TestExtractModule:
    """sandoc.extract 모듈 단위 테스트."""

    def test_import(self):
        """extract 모듈 임포트 가능."""
        from sandoc.extract import run_extract, REQUIRED_COMPANY_FIELDS
        assert callable(run_extract)
        assert len(REQUIRED_COMPANY_FIELDS) > 10

    def test_determine_missing_info_all_empty(self):
        """빈 found_info → 모든 필수 필드가 missing."""
        from sandoc.extract import _determine_missing_info, REQUIRED_COMPANY_FIELDS
        missing = _determine_missing_info({})
        assert len(missing) == len(REQUIRED_COMPANY_FIELDS)
        assert "company_name" in missing
        assert "ceo_name" in missing

    def test_determine_missing_info_partial(self):
        """일부 필드가 제공되면 해당 필드는 missing 에서 제외."""
        from sandoc.extract import _determine_missing_info
        found = {
            "company_name": "(주)테스트회사",
            "ceo_name": "홍길동",
        }
        missing = _determine_missing_info(found)
        assert "company_name" not in missing
        assert "ceo_name" not in missing
        assert "item_name" in missing  # 여전히 누락

    def test_determine_missing_info_empty_values(self):
        """빈 문자열, 빈 리스트, 0 값은 missing으로 간주."""
        from sandoc.extract import _determine_missing_info
        found = {
            "company_name": "",
            "funding_amount": 0,
            "team_members": [],
        }
        missing = _determine_missing_info(found)
        assert "company_name" in missing
        assert "funding_amount" in missing
        assert "team_members" in missing

    def test_run_extract_empty_project(self, tmp_path):
        """빈 프로젝트 폴더 → 오류 없이 빈 context 반환."""
        from sandoc.extract import run_extract

        project_dir = tmp_path / "empty-project"
        project_dir.mkdir()
        (project_dir / "docs").mkdir()

        result = run_extract(project_dir)

        assert "context" in result
        assert "missing_info" in result
        ctx = result["context"]
        assert ctx["project_name"] == "empty-project"
        assert ctx["documents"] == []
        assert len(ctx["missing_info"]) > 0

    def test_run_extract_no_docs_folder(self, tmp_path):
        """docs/ 폴더가 없어도 프로젝트 루트를 스캔."""
        from sandoc.extract import run_extract

        project_dir = tmp_path / "no-docs"
        project_dir.mkdir()

        result = run_extract(project_dir)
        assert result["context"]["project_name"] == "no-docs"

    @pytest.mark.skipif(not HAS_HWP or not HAS_PDF, reason="테스트 데이터 필요")
    def test_run_extract_with_real_docs(self, tmp_path):
        """실제 HWP/PDF 파일로 extract 실행."""
        from sandoc.extract import run_extract

        # v1-data를 임시 프로젝트 docs/에 심볼릭 링크 또는 복사
        project_dir = tmp_path / "real-project"
        project_dir.mkdir()
        docs_dir = project_dir / "docs"
        docs_dir.mkdir()

        # v1-data 파일들을 docs/에 심볼릭 링크
        for f in V1_DATA.iterdir():
            if f.is_file() and f.suffix.lower() in (".hwp", ".pdf"):
                (docs_dir / f.name).symlink_to(f)

        result = run_extract(project_dir)

        ctx = result["context"]
        assert len(ctx["documents"]) > 0
        assert ctx["template_analysis"] is not None
        assert ctx["announcement_analysis"] is not None
        assert result["style_profile_data"] is not None

    @pytest.mark.skipif(not HAS_HWP or not HAS_PDF, reason="테스트 데이터 필요")
    def test_run_extract_context_json_structure(self, tmp_path):
        """추출된 context.json이 올바른 스키마를 가지는지 확인."""
        from sandoc.extract import run_extract

        project_dir = tmp_path / "schema-test"
        project_dir.mkdir()
        docs_dir = project_dir / "docs"
        docs_dir.mkdir()

        for f in V1_DATA.iterdir():
            if f.is_file() and f.suffix.lower() in (".hwp", ".pdf"):
                (docs_dir / f.name).symlink_to(f)

        result = run_extract(project_dir)
        ctx = result["context"]

        # 필수 키 확인
        assert "project_name" in ctx
        assert "documents" in ctx
        assert isinstance(ctx["documents"], list)
        assert "template_analysis" in ctx
        assert "announcement_analysis" in ctx
        assert "style_profile" in ctx
        assert "company_info_found" in ctx
        assert "missing_info" in ctx

        # documents 구조 확인
        for doc in ctx["documents"]:
            assert "file" in doc
            assert "category" in doc
            assert "confidence" in doc

        # template_analysis 구조 확인
        if ctx["template_analysis"]:
            ta = ctx["template_analysis"]
            assert "sections" in ta
            assert "tables_count" in ta
            assert "input_fields" in ta

        # announcement_analysis 구조 확인
        if ctx["announcement_analysis"]:
            aa = ctx["announcement_analysis"]
            assert "title" in aa
            assert "scoring_criteria" in aa
            assert "key_dates" in aa


# ═══════════════════════════════════════════════════════════════
#  ASSEMBLE 모듈 테스트
# ═══════════════════════════════════════════════════════════════

class TestAssembleModule:
    """sandoc.assemble 모듈 단위 테스트."""

    def test_import(self):
        """assemble 모듈 임포트 가능."""
        from sandoc.assemble import run_assemble, _parse_markdown_section, _infer_section_key
        assert callable(run_assemble)
        assert callable(_parse_markdown_section)
        assert callable(_infer_section_key)

    def test_parse_markdown_section_with_heading(self):
        """# 제목이 있는 마크다운에서 제목/본문 분리."""
        from sandoc.assemble import _parse_markdown_section
        text = "# 기업 개요\n\n본문 내용입니다.\n두 번째 줄."
        title, content = _parse_markdown_section(text)
        assert title == "기업 개요"
        assert "본문 내용입니다." in content
        assert "두 번째 줄." in content

    def test_parse_markdown_section_multiple_hash(self):
        """## 또는 ### 제목도 파싱."""
        from sandoc.assemble import _parse_markdown_section
        text = "## 2-1. 목표시장 분석\n\n분석 내용"
        title, content = _parse_markdown_section(text)
        assert title == "2-1. 목표시장 분석"
        assert "분석 내용" in content

    def test_parse_markdown_section_no_heading(self):
        """# 없는 마크다운은 첫 줄을 제목으로."""
        from sandoc.assemble import _parse_markdown_section
        text = "제목이 될 줄\n\n본문 내용"
        title, content = _parse_markdown_section(text)
        assert title == "제목이 될 줄"
        assert "본문 내용" in content

    def test_infer_section_key_standard(self):
        """표준 파일명에서 섹션 키 추론."""
        from sandoc.assemble import _infer_section_key
        assert _infer_section_key("01_company_overview", 0) == "company_overview"
        assert _infer_section_key("02_problem_recognition", 1) == "problem_recognition"
        assert _infer_section_key("07_team", 6) == "team"

    def test_infer_section_key_unknown(self):
        """알 수 없는 키는 stem 그대로 반환."""
        from sandoc.assemble import _infer_section_key
        assert _infer_section_key("99_custom_section", 0) == "custom_section"

    def test_build_plan_from_markdowns(self, tmp_path):
        """마크다운 파일 목록에서 GeneratedPlan 구성."""
        from sandoc.assemble import _build_plan_from_markdowns

        drafts = tmp_path / "drafts"
        drafts.mkdir()

        (drafts / "01_test.md").write_text("# 테스트 제목\n\n테스트 본문", encoding="utf-8")
        (drafts / "02_another.md").write_text("# 두번째\n\n두번째 본문 내용", encoding="utf-8")

        md_files = sorted(drafts.glob("*.md"))
        plan = _build_plan_from_markdowns(md_files)

        assert len(plan.sections) == 2
        assert plan.sections[0].title == "테스트 제목"
        assert plan.sections[0].section_key == "test"
        assert plan.sections[1].title == "두번째"
        assert plan.total_word_count > 0

    def test_run_assemble_no_drafts(self, tmp_path):
        """초안 디렉토리 없음 → 오류 반환."""
        from sandoc.assemble import run_assemble

        project_dir = tmp_path / "no-drafts"
        project_dir.mkdir()

        result = run_assemble(project_dir)
        assert result["success"] is False
        assert len(result["errors"]) > 0

    def test_run_assemble_empty_drafts(self, tmp_path):
        """빈 초안 디렉토리 → 오류 반환."""
        from sandoc.assemble import run_assemble

        project_dir = tmp_path / "empty-drafts"
        project_dir.mkdir()
        (project_dir / "output" / "drafts" / "current").mkdir(parents=True)

        result = run_assemble(project_dir)
        assert result["success"] is False
        assert len(result["errors"]) > 0

    def test_run_assemble_with_drafts(self, tmp_path):
        """마크다운 초안으로 HWPX 조립 성공."""
        from sandoc.assemble import run_assemble

        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        drafts_dir = project_dir / "output" / "drafts" / "current"
        drafts_dir.mkdir(parents=True)

        # 샘플 마크다운 생성
        (drafts_dir / "01_company_overview.md").write_text(
            "# 기업 개요\n\n◦ 기업명: (주)테스트\n◦ 대표: 홍길동\n",
            encoding="utf-8",
        )
        (drafts_dir / "02_problem_recognition.md").write_text(
            "# 문제인식\n\n기존 시스템의 문제점을 분석합니다.\n",
            encoding="utf-8",
        )

        result = run_assemble(project_dir)

        assert result["success"] is True
        assert result["section_count"] == 2
        assert result["total_chars"] > 0
        assert result["hwpx_path"]
        assert result["plan_json_path"]

        # HWPX 파일 검증
        hwpx_path = Path(result["hwpx_path"])
        assert hwpx_path.exists()
        assert hwpx_path.stat().st_size > 0

        # plan.json 검증
        plan_json_path = Path(result["plan_json_path"])
        assert plan_json_path.exists()
        plan_data = json.loads(plan_json_path.read_text(encoding="utf-8"))
        assert len(plan_data["sections"]) == 2

    def test_run_assemble_with_style_profile(self, tmp_path):
        """스타일 프로파일과 함께 조립."""
        from sandoc.assemble import run_assemble

        project_dir = tmp_path / "styled-project"
        project_dir.mkdir()
        drafts_dir = project_dir / "output" / "drafts" / "current"
        drafts_dir.mkdir(parents=True)

        (drafts_dir / "01_test.md").write_text(
            "# 테스트\n\n테스트 내용입니다.\n", encoding="utf-8"
        )

        # 스타일 프로파일 생성
        style_data = {
            "paperSize": {"type": "A4", "width": "210.0mm", "height": "297.0mm"},
            "margins": {
                "top": "10.0mm", "bottom": "15.0mm",
                "left": "20.0mm", "right": "20.0mm",
                "header": "15.0mm", "footer": "10.0mm",
            },
            "characterStyles": {
                "bodyText": {"font": "맑은 고딕", "size": "10pt", "bold": False},
            },
            "paragraphStyles": {
                "default": {"alignment": "justify", "lineSpacing": 160},
            },
        }
        style_path = project_dir / "style-profile.json"
        style_path.write_text(json.dumps(style_data, ensure_ascii=False), encoding="utf-8")

        result = run_assemble(project_dir, style_profile_path=style_path)
        assert result["success"] is True

    def test_run_assemble_custom_output(self, tmp_path):
        """사용자 지정 출력 경로."""
        from sandoc.assemble import run_assemble

        project_dir = tmp_path / "custom-out"
        project_dir.mkdir()
        drafts_dir = project_dir / "output" / "drafts" / "current"
        drafts_dir.mkdir(parents=True)

        (drafts_dir / "01_section.md").write_text(
            "# 섹션\n\n내용\n", encoding="utf-8"
        )

        custom_output = tmp_path / "my_output.hwpx"
        result = run_assemble(project_dir, output_path=custom_output)

        assert result["success"] is True
        assert result["hwpx_path"] == str(custom_output)
        assert custom_output.exists()

    def test_run_assemble_hwpx_valid_structure(self, tmp_path):
        """조립된 HWPX가 올바른 ZIP 구조를 가짐."""
        from sandoc.assemble import run_assemble

        project_dir = tmp_path / "valid-struct"
        project_dir.mkdir()
        drafts_dir = project_dir / "output" / "drafts" / "current"
        drafts_dir.mkdir(parents=True)

        for i in range(3):
            (drafts_dir / f"0{i+1}_section_{i}.md").write_text(
                f"# 섹션 {i+1}\n\n내용 {i+1}\n", encoding="utf-8"
            )

        result = run_assemble(project_dir)
        assert result["success"] is True

        # ZIP 내부 구조 검증
        with zipfile.ZipFile(result["hwpx_path"], "r") as zf:
            names = zf.namelist()
            assert "mimetype" in names
            assert "META-INF/manifest.xml" in names
            assert "Contents/content.hpf" in names
            assert "Contents/header.xml" in names
            assert "Contents/section0.xml" in names


# ═══════════════════════════════════════════════════════════════
#  SAMPLE PROJECT 테스트
# ═══════════════════════════════════════════════════════════════

class TestSampleProject:
    """샘플 프로젝트 구조 및 데이터 검증."""

    @pytest.mark.skipif(not SAMPLE_PROJECT.exists(), reason="샘플 프로젝트 필요")
    def test_sample_project_exists(self):
        """샘플 프로젝트 디렉토리 존재."""
        assert SAMPLE_PROJECT.is_dir()

    @pytest.mark.skipif(not SAMPLE_PROJECT.exists(), reason="샘플 프로젝트 필요")
    def test_sample_context_json(self):
        """샘플 context.json 유효성."""
        context_path = SAMPLE_PROJECT / "context.json"
        assert context_path.exists()

        data = json.loads(context_path.read_text(encoding="utf-8"))
        assert data["project_name"] == "sample-창업도약"
        assert len(data["documents"]) > 0
        assert data["template_analysis"] is not None
        assert data["announcement_analysis"] is not None
        assert len(data["missing_info"]) > 0

    @pytest.mark.skipif(not SAMPLE_PROJECT.exists(), reason="샘플 프로젝트 필요")
    def test_sample_drafts_exist(self):
        """샘플 초안 마크다운 파일 존재."""
        drafts_dir = SAMPLE_PROJECT / "output" / "drafts" / "current"
        assert drafts_dir.is_dir()

        md_files = sorted(drafts_dir.glob("*.md"))
        assert len(md_files) == 9

    @pytest.mark.skipif(not SAMPLE_PROJECT.exists(), reason="샘플 프로젝트 필요")
    def test_sample_drafts_content(self):
        """샘플 초안 마크다운 파일에 # 제목이 있는지 확인."""
        drafts_dir = SAMPLE_PROJECT / "output" / "drafts" / "current"
        for md_path in sorted(drafts_dir.glob("*.md")):
            text = md_path.read_text(encoding="utf-8")
            assert text.strip(), f"빈 파일: {md_path.name}"
            assert text.strip().startswith("#"), f"# 제목 없음: {md_path.name}"

    @pytest.mark.skipif(not SAMPLE_PROJECT.exists(), reason="샘플 프로젝트 필요")
    def test_assemble_sample_project(self, tmp_path):
        """샘플 프로젝트의 초안으로 HWPX 조립."""
        from sandoc.assemble import run_assemble

        # 임시 디렉토리에 출력하여 원본 변경 방지
        project_copy = tmp_path / "sample-copy"
        shutil.copytree(SAMPLE_PROJECT, project_copy)

        result = run_assemble(project_copy)
        assert result["success"] is True
        assert result["section_count"] == 9
        assert result["total_chars"] > 0


# ═══════════════════════════════════════════════════════════════
#  CLI 테스트
# ═══════════════════════════════════════════════════════════════

class TestExtractCLI:
    """sandoc extract CLI 명령어 테스트."""

    def test_extract_help(self):
        """extract 명령어 --help 작동."""
        from sandoc.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["extract", "--help"])
        assert result.exit_code == 0
        assert "프로젝트 폴더" in result.output or "extract" in result.output

    def test_extract_nonexistent_dir(self):
        """존재하지 않는 디렉토리 → 오류."""
        from sandoc.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["extract", "/nonexistent/path"])
        assert result.exit_code != 0

    def test_extract_empty_project(self, tmp_path):
        """빈 프로젝트 폴더에서 extract 실행."""
        from sandoc.cli import main

        project_dir = tmp_path / "cli-empty"
        project_dir.mkdir()
        (project_dir / "docs").mkdir()

        runner = CliRunner()
        result = runner.invoke(main, ["extract", str(project_dir)])
        assert result.exit_code == 0
        assert "추출 완료" in result.output

        # context.json 생성 확인
        context_path = project_dir / "context.json"
        assert context_path.exists()

        # missing_info.json 생성 확인
        missing_path = project_dir / "missing_info.json"
        assert missing_path.exists()

    def test_extract_custom_output(self, tmp_path):
        """사용자 지정 출력 경로에 context.json 저장."""
        from sandoc.cli import main

        project_dir = tmp_path / "cli-custom"
        project_dir.mkdir()
        (project_dir / "docs").mkdir()

        custom_output = tmp_path / "my_context.json"

        runner = CliRunner()
        result = runner.invoke(main, ["extract", str(project_dir), "-o", str(custom_output)])
        assert result.exit_code == 0
        assert custom_output.exists()


class TestAssembleCLI:
    """sandoc assemble CLI 명령어 테스트."""

    def test_assemble_help(self):
        """assemble 명령어 --help 작동."""
        from sandoc.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["assemble", "--help"])
        assert result.exit_code == 0
        assert "assemble" in result.output.lower() or "HWPX" in result.output

    def test_assemble_nonexistent_dir(self):
        """존재하지 않는 디렉토리 → 오류."""
        from sandoc.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["assemble", "/nonexistent/path"])
        assert result.exit_code != 0

    def test_assemble_no_drafts(self, tmp_path):
        """초안 없이 assemble → 실패."""
        from sandoc.cli import main

        project_dir = tmp_path / "cli-no-drafts"
        project_dir.mkdir()

        runner = CliRunner()
        result = runner.invoke(main, ["assemble", str(project_dir)])
        assert result.exit_code == 1

    def test_assemble_with_drafts(self, tmp_path):
        """초안으로 assemble → 성공."""
        from sandoc.cli import main

        project_dir = tmp_path / "cli-with-drafts"
        project_dir.mkdir()
        drafts_dir = project_dir / "output" / "drafts" / "current"
        drafts_dir.mkdir(parents=True)

        (drafts_dir / "01_overview.md").write_text(
            "# 개요\n\n테스트 내용\n", encoding="utf-8"
        )

        runner = CliRunner()
        result = runner.invoke(main, ["assemble", str(project_dir)])
        assert result.exit_code == 0
        assert "조립 완료" in result.output


# ═══════════════════════════════════════════════════════════════
#  통합 테스트: extract → (AI writes sections) → assemble
# ═══════════════════════════════════════════════════════════════

class TestFullWorkflow:
    """extract → assemble 전체 워크플로우 테스트."""

    def test_workflow_with_mock_data(self, tmp_path):
        """모의 데이터로 전체 워크플로우 실행."""
        from sandoc.extract import run_extract
        from sandoc.assemble import run_assemble

        # 1. 프로젝트 세팅
        project_dir = tmp_path / "workflow-test"
        project_dir.mkdir()
        (project_dir / "docs").mkdir()

        # 2. Extract (빈 프로젝트)
        extract_result = run_extract(project_dir)
        assert "context" in extract_result
        assert len(extract_result["context"]["missing_info"]) > 0

        # context.json 저장
        context_path = project_dir / "context.json"
        context_path.write_text(
            json.dumps(extract_result["context"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 3. AI가 섹션을 작성했다고 시뮬레이션
        drafts_dir = project_dir / "output" / "drafts" / "current"
        drafts_dir.mkdir(parents=True)

        sections = [
            ("01_company_overview", "기업 개요", "기업명: (주)테스트AI"),
            ("02_problem_recognition", "문제인식", "기존 시스템의 한계를 극복"),
            ("03_solution", "목표시장 분석", "국내 시장 규모 1조원"),
        ]
        for stem, title, body in sections:
            (drafts_dir / f"{stem}.md").write_text(
                f"# {title}\n\n{body}\n", encoding="utf-8"
            )

        # 4. Assemble
        assemble_result = run_assemble(project_dir)
        assert assemble_result["success"] is True
        assert assemble_result["section_count"] == 3
        assert Path(assemble_result["hwpx_path"]).exists()

    @pytest.mark.skipif(not SAMPLE_PROJECT.exists(), reason="샘플 프로젝트 필요")
    def test_workflow_with_sample_project(self, tmp_path):
        """샘플 프로젝트로 전체 워크플로우 (assemble 단계만)."""
        from sandoc.assemble import run_assemble

        project_copy = tmp_path / "workflow-sample"
        shutil.copytree(SAMPLE_PROJECT, project_copy)

        result = run_assemble(project_copy)
        assert result["success"] is True
        assert result["section_count"] == 9

        # HWPX 검증
        hwpx_path = Path(result["hwpx_path"])
        assert hwpx_path.exists()

        with zipfile.ZipFile(hwpx_path, "r") as zf:
            mt = zf.read("mimetype").decode("utf-8").strip()
            assert mt == "application/hwp+zip"
