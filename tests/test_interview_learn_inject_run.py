"""
tests/test_interview_learn_inject_run.py — interview, learn, inject, run 명령어 테스트

sandoc interview: 누락 정보 설문지 생성 / 답변 병합
sandoc learn: 지식 축적
sandoc inject: HWP 템플릿 삽입 매핑
sandoc run: 전체 파이프라인
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

# ── 프로젝트 경로 ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
SAMPLE_PROJECT = PROJECT_ROOT / "projects" / "sample-창업도약"


# ── 테스트 픽스처 ─────────────────────────────────────────────

@pytest.fixture
def project_with_missing_info(tmp_path) -> Path:
    """missing_info.json 이 있는 프로젝트."""
    project_dir = tmp_path / "test-interview"
    project_dir.mkdir()
    (project_dir / "docs").mkdir()
    (project_dir / "output").mkdir()

    context = {
        "project_name": "test-interview",
        "documents": [],
        "template_analysis": None,
        "announcement_analysis": None,
        "style_profile": None,
        "company_info_found": {"from_docs": {}},
        "missing_info": [
            "company_name", "ceo_name", "item_name",
            "funding_amount", "team_members",
        ],
    }
    (project_dir / "context.json").write_text(
        json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    missing_info = {
        "project_name": "test-interview",
        "missing_fields": [
            "company_name", "ceo_name", "business_registration_no",
            "establishment_date", "employee_count", "address",
            "item_name", "item_summary", "product_description",
            "problem_background", "problem_statement", "development_motivation",
            "target_market", "target_customer", "competitive_advantage",
            "key_features", "business_model", "growth_strategy",
            "marketing_plan", "funding_amount", "self_funding_cash",
            "ceo_background", "team_members", "budget_items",
        ],
        "total_missing": 24,
        "instructions": "아래 항목들은 문서에서 자동 추출되지 않았습니다.",
    }
    (project_dir / "missing_info.json").write_text(
        json.dumps(missing_info, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return project_dir


@pytest.fixture
def project_with_drafts(tmp_path) -> Path:
    """초안 마크다운이 있는 프로젝트."""
    project_dir = tmp_path / "test-drafts"
    project_dir.mkdir()
    (project_dir / "docs").mkdir()
    drafts_dir = project_dir / "output" / "drafts" / "current"
    drafts_dir.mkdir(parents=True)

    # context.json
    context = {
        "project_name": "test-drafts",
        "documents": [],
        "template_analysis": {
            "file": "양식.hwp",
            "sections": [
                {"title": "□ 신청 및 일반현황", "level": 0},
                {"title": "1. 문제인식 (Problem)", "level": 0},
            ],
            "tables_count": 5,
            "input_fields": ["기업명", "대표자"],
            "total_paragraphs": 100,
        },
        "announcement_analysis": {
            "title": "2026년 창업도약패키지 공고",
            "scoring_criteria": [],
            "key_dates": [],
        },
        "style_profile": None,
        "company_info_found": {"from_docs": {}},
        "missing_info": ["company_name"],
    }
    (project_dir / "context.json").write_text(
        json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # missing_info.json
    missing_info = {
        "project_name": "test-drafts",
        "missing_fields": ["company_name"],
        "total_missing": 1,
        "instructions": "미입력 필드",
    }
    (project_dir / "missing_info.json").write_text(
        json.dumps(missing_info, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 9개 섹션 초안 생성
    sections = [
        ("01_company_overview.md", "기업 개요 및 일반현황",
         "◦ 기업명: (주)테스트AI\n◦ 대표자: 김대표\n◦ 직원수: 12명\n"
         "◦ 사업비 구성\n  - 총사업비: 285,000,000원\n  - 정부지원금: 200,000,000원\n"
         "  - 자기부담(현금): 30,000,000원\n  - 자기부담(현물): 55,000,000원"),
        ("02_problem_recognition.md", "1. 문제인식 (Problem)",
         "◦ 외부 환경 분석\n  - 국내 시장의 기존 솔루션은 고가이며 보급률 5% 미만\n"
         "◦ 개발 동기\n  - 현장 어려움을 직접 경험하고 AI 기반 솔루션 개발\n"
         "기존 대비 60% 저렴한 도입비용 달성"),
        ("03_solution.md", "2-1. 목표시장(고객) 분석",
         "◦ TAM: 5조원\n◦ SAM: 3000억원\n◦ SOM: 500억원\n"
         "◦ 경쟁사\n  - A사: 고가\n  - B사: 기능 제한"),
        ("04_business_model.md", "2-2. 사업화 추진 성과",
         "◦ 사업 모델: SaaS + 하드웨어\n"
         "| 순번 | 시장 | 제품 | 매출 |\n|---|---|---|---|\n| 1 | 중소기업 | AI | 4.5억 |\n"
         "2023년 매출 8억, 2024년 매출 12억, 2025년 매출 18.5억 목표"),
        ("05_market_analysis.md", "3-1. 사업화 추진 전략",
         "◦ 성장 전략\n  - 시장 점유율 5% → 10%\n"
         "| 순번 | 추진내용 | 추진기간 |\n|---|---|---|\n| 1 | AI 고도화 | 2025.06~08 |"),
        ("06_growth_strategy.md", "3-2. 자금운용 계획",
         "◦ 총사업비: 285,000,000원\n◦ 정부지원금: 200,000,000원\n"
         "| 비목 | 금액 |\n|---|---|\n| 재료비 | 50,000,000 |"),
        ("07_team.md", "4. 기업 구성 (Team)",
         "◦ 대표자 역량: 서울대 석사, 10년 경력\n"
         "| 직위 | 담당 | 역량 |\n|---|---|---|\n| CTO | AI 개발 | 박사 |"),
        ("08_financial_plan.md", "재무 계획 종합 분석",
         "◦ 사업비 검증: 총 285,000,000원\n◦ 투자유치: 0원"),
        ("09_funding_plan.md", "사업비 집행 계획 (상세)",
         "◦ 재료비: 50,000,000원\n◦ 인건비: 60,000,000원"),
    ]

    for filename, title, content in sections:
        (drafts_dir / filename).write_text(
            f"# {title}\n\n{content}\n", encoding="utf-8"
        )

    return project_dir


# ═══════════════════════════════════════════════════════════════
#  INTERVIEW 모듈 테스트
# ═══════════════════════════════════════════════════════════════

class TestInterviewModule:
    """sandoc.interview 모듈 단위 테스트."""

    def test_import(self):
        """interview 모듈 임포트 가능."""
        from sandoc.interview import run_interview, FIELD_METADATA, CATEGORY_ORDER
        assert callable(run_interview)
        assert len(FIELD_METADATA) > 20
        assert len(CATEGORY_ORDER) == 4

    def test_group_by_category(self):
        """필드를 카테고리별로 그룹핑."""
        from sandoc.interview import _group_by_category
        fields = ["company_name", "ceo_name", "item_name", "funding_amount"]
        grouped = _group_by_category(fields)
        assert "기업정보" in grouped
        assert "아이템정보" in grouped
        assert "재무정보" in grouped
        assert "company_name" in grouped["기업정보"]
        assert "item_name" in grouped["아이템정보"]

    def test_build_questionnaire_md(self):
        """설문지 마크다운 생성."""
        from sandoc.interview import _build_questionnaire_md, _group_by_category
        fields = ["company_name", "ceo_name", "item_name"]
        grouped = _group_by_category(fields)
        md = _build_questionnaire_md(grouped, "test-project")
        assert "설문지" in md
        assert "기업명" in md
        assert "대표자명" in md
        assert "창업아이템명" in md
        assert "test-project" in md

    def test_build_json_template(self):
        """JSON 템플릿 생성."""
        from sandoc.interview import _build_json_template, _group_by_category
        fields = ["company_name", "funding_amount", "team_members"]
        grouped = _group_by_category(fields)
        template = _build_json_template(grouped)
        assert template["company_name"] == ""
        assert template["funding_amount"] == 0
        assert template["team_members"] == []
        assert "_comments" in template

    def test_generate_questionnaire(self, project_with_missing_info):
        """설문지 + JSON 템플릿 생성."""
        from sandoc.interview import run_interview

        result = run_interview(project_with_missing_info)
        assert result["success"] is True
        assert result["mode"] == "generate"
        assert result["questionnaire_path"] is not None
        assert result["template_path"] is not None

        # 파일 존재 확인
        assert Path(result["questionnaire_path"]).exists()
        assert Path(result["template_path"]).exists()

        # 설문지 내용 확인
        q_text = Path(result["questionnaire_path"]).read_text(encoding="utf-8")
        assert "기업정보" in q_text
        assert "기업명" in q_text

        # JSON 템플릿 내용 확인
        t_data = json.loads(Path(result["template_path"]).read_text(encoding="utf-8"))
        assert "company_name" in t_data
        assert "_comments" in t_data

    def test_fill_answers(self, project_with_missing_info, tmp_path):
        """답변 JSON 병합."""
        from sandoc.interview import run_interview

        answers = {
            "company_name": "(주)테스트회사",
            "ceo_name": "홍길동",
            "item_name": "AI 시스템",
        }
        answers_path = tmp_path / "answers.json"
        answers_path.write_text(json.dumps(answers, ensure_ascii=False), encoding="utf-8")

        result = run_interview(project_with_missing_info, fill_path=answers_path)
        assert result["success"] is True
        assert result["mode"] == "fill"
        assert result["merged_fields"] == 3

        # context.json 에 병합 확인
        ctx = json.loads(
            (project_with_missing_info / "context.json").read_text(encoding="utf-8")
        )
        found = ctx["company_info_found"]["from_docs"]
        assert found["company_name"] == "(주)테스트회사"
        assert found["ceo_name"] == "홍길동"

        # missing_info 업데이트 확인
        assert "company_name" not in ctx["missing_info"]

    def test_no_missing_info_file(self, tmp_path):
        """missing_info.json 없으면 오류."""
        from sandoc.interview import run_interview
        project_dir = tmp_path / "no-missing"
        project_dir.mkdir()

        result = run_interview(project_dir)
        assert result["success"] is False
        assert len(result["errors"]) > 0

    def test_empty_missing_fields(self, tmp_path):
        """누락 필드가 없으면 바로 성공."""
        from sandoc.interview import run_interview
        project_dir = tmp_path / "no-missing-fields"
        project_dir.mkdir()

        missing_info = {
            "project_name": "test",
            "missing_fields": [],
            "total_missing": 0,
        }
        (project_dir / "missing_info.json").write_text(
            json.dumps(missing_info), encoding="utf-8"
        )

        result = run_interview(project_dir)
        assert result["success"] is True


# ═══════════════════════════════════════════════════════════════
#  LEARN 모듈 테스트
# ═══════════════════════════════════════════════════════════════

class TestLearnModule:
    """sandoc.learn 모듈 단위 테스트."""

    def test_import(self):
        """learn 모듈 임포트 가능."""
        from sandoc.learn import run_learn, SECTION_CATEGORY_MAP
        assert callable(run_learn)
        assert len(SECTION_CATEGORY_MAP) == 9

    def test_extract_expressions(self):
        """효과적 표현 추출."""
        from sandoc.learn import _extract_expressions
        text = "기존 대비 60% 저렴한 솔루션\n국내 시장 점유율 5% 이상 달성"
        expressions = _extract_expressions(text, "solution", "실현가능성")
        # 패턴에 매칭되는 표현이 있어야 함
        assert isinstance(expressions, list)

    def test_extract_patterns(self):
        """구조적 패턴 추출."""
        from sandoc.learn import _extract_patterns
        text = (
            "◦ 핵심 기능\n  - AI 자동화\n  - 모니터링\n\n"
            "| 항목 | 설명 |\n|---|---|\n| A | B |\n"
        )
        patterns = _extract_patterns(text, "solution", "실현가능성")
        assert len(patterns) > 0
        types = [p["type"] for p in patterns]
        assert "table" in types or "bullet_hierarchy" in types

    def test_extract_lesson(self):
        """교훈 추출."""
        from sandoc.learn import _extract_lesson
        text = "◦ " * 10 + "내용 " * 50 + "\n| 항목 | 값 |\n|---|---|\n| A | B |"
        lesson = _extract_lesson(text, "team", "팀구성")
        assert lesson is not None
        assert "team" in lesson

    def test_extract_lesson_short(self):
        """너무 짧은 내용은 교훈 없음."""
        from sandoc.learn import _extract_lesson
        lesson = _extract_lesson("짧음", "test", "기타")
        assert lesson is None

    def test_run_learn_no_drafts(self, tmp_path):
        """초안 없음 → 오류."""
        from sandoc.learn import run_learn
        project_dir = tmp_path / "no-learn"
        project_dir.mkdir()

        result = run_learn(project_dir)
        assert result["success"] is False
        assert len(result["errors"]) > 0

    def test_run_learn_with_drafts(self, project_with_drafts, tmp_path):
        """초안으로 지식 축적."""
        from sandoc.learn import run_learn

        knowledge_dir = tmp_path / "knowledge"
        result = run_learn(project_with_drafts, knowledge_dir=knowledge_dir)
        assert result["success"] is True
        assert len(result["processed_sections"]) > 0

        # 지식 디렉토리 생성 확인
        assert knowledge_dir.is_dir()
        assert (knowledge_dir / "expressions").is_dir()
        assert (knowledge_dir / "patterns").is_dir()

        # lessons.md 생성 확인
        assert result["lessons_path"] is not None
        lessons_path = Path(result["lessons_path"])
        assert lessons_path.exists()
        lessons_text = lessons_path.read_text(encoding="utf-8")
        assert "학습 기록" in lessons_text

        # processing_history.json 확인
        history_path = knowledge_dir / "processing_history.json"
        assert history_path.exists()
        history = json.loads(history_path.read_text(encoding="utf-8"))
        assert len(history) > 0
        assert history[0]["project"] == "test-drafts"

    def test_run_learn_expressions_saved(self, project_with_drafts, tmp_path):
        """표현 파일 저장 확인."""
        from sandoc.learn import run_learn

        knowledge_dir = tmp_path / "knowledge"
        result = run_learn(project_with_drafts, knowledge_dir=knowledge_dir)

        # 표현 파일이 생성되었으면 내용 확인
        if result["expressions_count"] > 0:
            expr_files = list((knowledge_dir / "expressions").glob("*.json"))
            assert len(expr_files) > 0
            data = json.loads(expr_files[0].read_text(encoding="utf-8"))
            assert isinstance(data, list)

    def test_run_learn_patterns_saved(self, project_with_drafts, tmp_path):
        """패턴 파일 저장 확인."""
        from sandoc.learn import run_learn

        knowledge_dir = tmp_path / "knowledge"
        result = run_learn(project_with_drafts, knowledge_dir=knowledge_dir)

        if result["patterns_count"] > 0:
            pat_files = list((knowledge_dir / "patterns").glob("*.json"))
            assert len(pat_files) > 0
            data = json.loads(pat_files[0].read_text(encoding="utf-8"))
            assert isinstance(data, list)
            assert "type" in data[0]


# ═══════════════════════════════════════════════════════════════
#  INJECT 모듈 테스트
# ═══════════════════════════════════════════════════════════════

class TestInjectModule:
    """sandoc.inject 모듈 단위 테스트."""

    def test_import(self):
        """inject 모듈 임포트 가능."""
        from sandoc.inject import run_inject, TEMPLATE_SECTION_MAP
        assert callable(run_inject)
        assert len(TEMPLATE_SECTION_MAP) == 9

    def test_section_title_match(self):
        """양식 섹션 제목 매칭."""
        from sandoc.inject import _section_title_match
        assert _section_title_match("□ 신청 및 일반현황", "□ 신청 및 일반현황") is True
        assert _section_title_match("1. 문제인식 (Problem)", "1. 문제인식(Problem)") is True
        assert _section_title_match("문제인식", "1. 문제인식 (Problem)") is True
        assert _section_title_match("완전 다른 제목", "xyz") is False

    def test_run_inject_no_drafts(self, tmp_path):
        """초안 없음 → 오류."""
        from sandoc.inject import run_inject
        project_dir = tmp_path / "no-inject"
        project_dir.mkdir()

        result = run_inject(project_dir)
        assert result["success"] is False
        assert len(result["errors"]) > 0

    def test_run_inject_with_drafts(self, project_with_drafts):
        """초안으로 삽입 매핑 생성."""
        from sandoc.inject import run_inject

        result = run_inject(project_with_drafts)
        assert result["success"] is True
        assert result["mappings_count"] > 0
        assert result["map_path"] is not None
        assert result["instructions_path"] is not None

        # injection_map.json 검증
        map_path = Path(result["map_path"])
        assert map_path.exists()
        map_data = json.loads(map_path.read_text(encoding="utf-8"))
        assert "mappings" in map_data
        assert len(map_data["mappings"]) > 0

        # 각 매핑에 필수 필드가 있는지 확인
        for mapping in map_data["mappings"]:
            assert "template_section" in mapping
            assert "draft_file" in mapping
            assert "injection_type" in mapping
            assert "target_markers" in mapping

    def test_injection_instructions_content(self, project_with_drafts):
        """삽입 지시서 내용 확인."""
        from sandoc.inject import run_inject

        result = run_inject(project_with_drafts)
        instr_path = Path(result["instructions_path"])
        content = instr_path.read_text(encoding="utf-8")

        assert "삽입 지시서" in content
        assert "hwpx-mcp" in content
        assert "사전 요구사항" in content
        assert "삽입 절차" in content
        assert "마무리 확인사항" in content

    def test_inject_map_all_sections(self, project_with_drafts):
        """9개 섹션 모두 매핑."""
        from sandoc.inject import run_inject

        result = run_inject(project_with_drafts)
        assert result["mappings_count"] == 9

    def test_inject_with_template_info(self, project_with_drafts):
        """양식 정보가 있으면 매칭 시도."""
        from sandoc.inject import run_inject

        result = run_inject(project_with_drafts)
        map_data = json.loads(Path(result["map_path"]).read_text(encoding="utf-8"))

        # template_analysis 에 섹션이 있으므로 일부 매칭
        has_matched = any(
            m.get("matched_in_template") for m in map_data["mappings"]
        )
        assert has_matched is True


# ═══════════════════════════════════════════════════════════════
#  RUN (PIPELINE) 모듈 테스트
# ═══════════════════════════════════════════════════════════════

class TestRunModule:
    """sandoc.run 모듈 단위 테스트."""

    def test_import(self):
        """run 모듈 임포트 가능."""
        from sandoc.run import run_pipeline
        assert callable(run_pipeline)

    def test_run_empty_project(self, tmp_path):
        """빈 프로젝트 → extract 성공, 나머지 건너뜀."""
        from sandoc.run import run_pipeline

        project_dir = tmp_path / "empty-run"
        project_dir.mkdir()
        (project_dir / "docs").mkdir()

        result = run_pipeline(project_dir)
        # extract는 성공하지만 drafts가 없어서 부분 성공
        assert result["steps"]["extract"]["success"] is True
        assert "초안 파일이 없습니다" in result.get("errors", [""])[0]

    def test_run_with_drafts(self, project_with_drafts):
        """초안이 있는 프로젝트로 전체 파이프라인."""
        from sandoc.run import run_pipeline

        result = run_pipeline(project_with_drafts, skip_extract=True)
        assert result["success"] is True

        # visualize 성공
        assert result["steps"]["visualize"]["success"] is True

        # review 성공
        assert result["steps"]["review"]["success"] is True
        assert result["summary"]["overall_score"] is not None

        # assemble 성공
        assert result["steps"]["assemble"]["success"] is True
        assert result["summary"]["hwpx_path"] is not None

    def test_run_skip_steps(self, project_with_drafts):
        """단계 건너뛰기."""
        from sandoc.run import run_pipeline

        result = run_pipeline(
            project_with_drafts,
            skip_extract=True,
            skip_visualize=True,
            skip_review=True,
        )
        assert result["success"] is True
        # assemble 만 실행
        assert "visualize" not in result["steps"]
        assert "review" not in result["steps"]
        assert result["steps"]["assemble"]["success"] is True

    def test_run_with_company_info(self, project_with_drafts, tmp_path):
        """회사 정보 병합 포함 파이프라인."""
        from sandoc.run import run_pipeline

        company_info = {
            "company_name": "(주)파이프라인테스트",
            "ceo_name": "김테스트",
            "item_name": "AI 시스템",
        }
        info_path = tmp_path / "company.json"
        info_path.write_text(json.dumps(company_info, ensure_ascii=False), encoding="utf-8")

        result = run_pipeline(
            project_with_drafts,
            company_info_path=info_path,
            skip_extract=True,
        )

        assert result["steps"]["merge"]["success"] is True
        assert result["steps"]["merge"]["merged_fields"] == 3

    def test_merge_company_info(self, project_with_drafts, tmp_path):
        """회사 정보 병합 함수 직접 테스트."""
        from sandoc.run import _merge_company_info

        company_info = {"company_name": "(주)머지테스트", "ceo_name": "박머지"}
        info_path = tmp_path / "company.json"
        info_path.write_text(json.dumps(company_info, ensure_ascii=False), encoding="utf-8")

        merge_result = _merge_company_info(project_with_drafts, info_path)
        assert merge_result["success"] is True
        assert merge_result["merged_fields"] == 2

        # context.json 에 병합 확인
        ctx = json.loads(
            (project_with_drafts / "context.json").read_text(encoding="utf-8")
        )
        assert ctx["company_info_found"]["from_docs"]["company_name"] == "(주)머지테스트"

    def test_merge_without_context(self, tmp_path):
        """context.json 없어도 새로 생성."""
        from sandoc.run import _merge_company_info

        project_dir = tmp_path / "no-ctx"
        project_dir.mkdir()

        company_info = {"company_name": "(주)신규"}
        info_path = tmp_path / "company.json"
        info_path.write_text(json.dumps(company_info, ensure_ascii=False), encoding="utf-8")

        merge_result = _merge_company_info(project_dir, info_path)
        assert merge_result["success"] is True

        # 새로 생성된 context.json 확인
        assert (project_dir / "context.json").exists()


# ═══════════════════════════════════════════════════════════════
#  CLI 테스트
# ═══════════════════════════════════════════════════════════════

class TestInterviewCLI:
    """sandoc interview CLI 명령어 테스트."""

    def test_interview_help(self):
        """interview --help 작동."""
        from sandoc.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["interview", "--help"])
        assert result.exit_code == 0
        assert "설문지" in result.output or "interview" in result.output.lower()

    def test_interview_nonexistent(self):
        """존재하지 않는 디렉토리 → 오류."""
        from sandoc.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["interview", "/nonexistent/path"])
        assert result.exit_code != 0

    def test_interview_generate(self, project_with_missing_info):
        """설문지 생성 CLI."""
        from sandoc.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["interview", str(project_with_missing_info)])
        assert result.exit_code == 0
        assert "설문지 생성 완료" in result.output

    def test_interview_fill(self, project_with_missing_info, tmp_path):
        """답변 병합 CLI."""
        from sandoc.cli import main

        answers = {"company_name": "(주)CLI테스트"}
        answers_path = tmp_path / "ans.json"
        answers_path.write_text(json.dumps(answers, ensure_ascii=False), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(main, [
            "interview", str(project_with_missing_info),
            "--fill", str(answers_path),
        ])
        assert result.exit_code == 0
        assert "병합 완료" in result.output


class TestLearnCLI:
    """sandoc learn CLI 명령어 테스트."""

    def test_learn_help(self):
        """learn --help 작동."""
        from sandoc.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["learn", "--help"])
        assert result.exit_code == 0
        assert "지식" in result.output or "learn" in result.output.lower()

    def test_learn_nonexistent(self):
        """존재하지 않는 디렉토리 → 오류."""
        from sandoc.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["learn", "/nonexistent/path"])
        assert result.exit_code != 0

    def test_learn_with_drafts(self, project_with_drafts, tmp_path):
        """초안으로 learn CLI 실행."""
        from sandoc.cli import main
        runner = CliRunner()
        result = runner.invoke(main, [
            "learn", str(project_with_drafts),
            "-k", str(tmp_path / "knowledge"),
        ])
        assert result.exit_code == 0
        assert "지식 축적 완료" in result.output


class TestInjectCLI:
    """sandoc inject CLI 명령어 테스트."""

    def test_inject_help(self):
        """inject --help 작동."""
        from sandoc.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["inject", "--help"])
        assert result.exit_code == 0
        assert "매핑" in result.output or "inject" in result.output.lower()

    def test_inject_nonexistent(self):
        """존재하지 않는 디렉토리 → 오류."""
        from sandoc.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["inject", "/nonexistent/path"])
        assert result.exit_code != 0

    def test_inject_with_drafts(self, project_with_drafts):
        """초안으로 inject CLI 실행."""
        from sandoc.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["inject", str(project_with_drafts)])
        assert result.exit_code == 0
        assert "삽입 매핑 생성 완료" in result.output


class TestRunCLI:
    """sandoc run CLI 명령어 테스트."""

    def test_run_help(self):
        """run --help 작동."""
        from sandoc.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["run", "--help"])
        assert result.exit_code == 0
        assert "파이프라인" in result.output or "run" in result.output.lower()

    def test_run_nonexistent(self):
        """존재하지 않는 디렉토리 → 오류."""
        from sandoc.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["run", "/nonexistent/path"])
        assert result.exit_code != 0

    def test_run_with_drafts(self, project_with_drafts):
        """초안이 있는 프로젝트로 run CLI 실행."""
        from sandoc.cli import main
        runner = CliRunner()
        result = runner.invoke(main, [
            "run", str(project_with_drafts),
            "--skip-extract",
        ])
        assert result.exit_code == 0
        assert "파이프라인 완료" in result.output

    def test_run_empty_project(self, tmp_path):
        """빈 프로젝트 → 부분 완료 (extract만 성공)."""
        from sandoc.cli import main

        project_dir = tmp_path / "cli-empty-run"
        project_dir.mkdir()
        (project_dir / "docs").mkdir()

        runner = CliRunner()
        result = runner.invoke(main, ["run", str(project_dir)])
        # extract 성공 후 drafts 없으므로 부분 완료
        assert result.exit_code == 0
        assert "부분 완료" in result.output or "파이프라인" in result.output


# ═══════════════════════════════════════════════════════════════
#  통합 테스트: interview → learn → inject → run
# ═══════════════════════════════════════════════════════════════

class TestNewCommandsIntegration:
    """새 명령어 통합 워크플로우."""

    def test_interview_then_fill(self, project_with_missing_info, tmp_path):
        """interview → fill → context 업데이트 워크플로우."""
        from sandoc.interview import run_interview

        # 1. 설문지 생성
        gen_result = run_interview(project_with_missing_info)
        assert gen_result["success"] is True

        # 2. JSON 템플릿에서 일부 필드 채우기
        template = json.loads(
            Path(gen_result["template_path"]).read_text(encoding="utf-8")
        )
        template.pop("_comments", None)
        template["company_name"] = "(주)통합테스트"
        template["ceo_name"] = "김통합"
        template["item_name"] = "통합 AI 시스템"
        template["funding_amount"] = 200000000

        answers_path = tmp_path / "filled.json"
        answers_path.write_text(
            json.dumps(template, ensure_ascii=False), encoding="utf-8"
        )

        # 3. 답변 병합
        fill_result = run_interview(project_with_missing_info, fill_path=answers_path)
        assert fill_result["success"] is True
        assert fill_result["merged_fields"] >= 3

        # 4. context.json 확인
        ctx = json.loads(
            (project_with_missing_info / "context.json").read_text(encoding="utf-8")
        )
        found = ctx["company_info_found"]["from_docs"]
        assert found["company_name"] == "(주)통합테스트"

        # 5. missing_info 줄었는지 확인
        assert "company_name" not in ctx["missing_info"]

    def test_learn_then_check_files(self, project_with_drafts, tmp_path):
        """learn → 지식 파일 확인 워크플로우."""
        from sandoc.learn import run_learn

        knowledge_dir = tmp_path / "k"
        result = run_learn(project_with_drafts, knowledge_dir=knowledge_dir)
        assert result["success"] is True

        # lessons.md 에 내용이 있는지
        lessons_path = Path(result["lessons_path"])
        text = lessons_path.read_text(encoding="utf-8")
        assert "test-drafts" in text

        # processing_history.json 에 기록이 있는지
        history = json.loads(
            (knowledge_dir / "processing_history.json").read_text(encoding="utf-8")
        )
        assert any(h["project"] == "test-drafts" for h in history)

    def test_inject_produces_complete_map(self, project_with_drafts):
        """inject → 모든 섹션 매핑 확인."""
        from sandoc.inject import run_inject

        result = run_inject(project_with_drafts)
        assert result["success"] is True

        map_data = json.loads(Path(result["map_path"]).read_text(encoding="utf-8"))
        section_keys = [m["section_key"] for m in map_data["mappings"]]

        # 핵심 섹션 모두 포함
        assert "company_overview" in section_keys
        assert "problem_recognition" in section_keys
        assert "solution" in section_keys
        assert "team" in section_keys
        assert "growth_strategy" in section_keys

    @pytest.mark.skipif(not SAMPLE_PROJECT.exists(), reason="샘플 프로젝트 필요")
    def test_full_new_commands_with_sample(self, tmp_path):
        """샘플 프로젝트로 모든 새 명령어 실행."""
        from sandoc.learn import run_learn
        from sandoc.inject import run_inject

        project_copy = tmp_path / "sample-full"
        shutil.copytree(SAMPLE_PROJECT, project_copy)

        # learn
        knowledge_dir = tmp_path / "knowledge"
        learn_result = run_learn(project_copy, knowledge_dir=knowledge_dir)
        assert learn_result["success"] is True
        assert learn_result["processed_sections"]

        # inject
        inject_result = run_inject(project_copy)
        assert inject_result["success"] is True
        assert inject_result["mappings_count"] == 9
