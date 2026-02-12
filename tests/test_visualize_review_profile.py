"""
tests/test_visualize_review_profile.py — visualize, review, profile-register 테스트

sandoc visualize: 시각화 차트 생성
sandoc review: 사업계획서 자가 검토
sandoc profile-register: 기업 프로필 등록
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
def sample_project(tmp_path) -> Path:
    """재무 데이터가 있는 샘플 프로젝트 생성."""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()
    drafts_dir = project_dir / "output" / "drafts" / "current"
    drafts_dir.mkdir(parents=True)

    # 기업 개요
    (drafts_dir / "01_company_overview.md").write_text(
        "# 기업 개요 및 일반현황\n\n"
        "□ 신청 및 일반현황\n\n"
        "◦ 기업명: (주)테스트AI\n"
        "◦ 대표자: 김대표\n"
        "◦ 직원수: 12명\n\n"
        "◦ 사업비 구성\n"
        "  - 총사업비: 285,000,000원\n"
        "  - 정부지원금: 200,000,000원\n"
        "  - 자기부담(현금): 30,000,000원\n"
        "  - 자기부담(현물): 55,000,000원\n",
        encoding="utf-8",
    )

    # 문제인식
    (drafts_dir / "02_problem_recognition.md").write_text(
        "# 1. 문제인식 (Problem)\n\n"
        "1. 창업아이템 개발 동기(필요성) 및 현황\n\n"
        "◦ 외부 환경 분석\n"
        "  - 국내 시장의 기존 솔루션은 고가이며 중소기업 보급률이 낮은 문제가 있습니다.\n"
        "  - 기술 발전에 따른 필요성이 증가하고 있으나 현재 시장의 한계가 존재합니다.\n\n"
        "◦ 개발 동기 (필요성)\n"
        "  - 현장에서의 어려움을 직접 경험하고 AI 기반 저비용 솔루션 개발의 동기를 갖게 되었습니다.\n\n"
        "◦ 핵심 문제점\n"
        "  - 기존 솔루션은 비용이 높고 설치가 복잡합니다.\n",
        encoding="utf-8",
    )

    # 솔루션 (TAM/SAM/SOM 포함)
    (drafts_dir / "03_solution.md").write_text(
        "# 2-1. 목표시장(고객) 분석\n\n"
        "◦ 목표 시장\n"
        "  - TAM(전체 시장): 5조원 규모\n"
        "  - SAM(유효 시장): 3000억원\n"
        "  - SOM(목표 시장 규모): 500억원\n\n"
        "◦ 목표 고객\n"
        "  - 중소기업 및 스타트업\n\n"
        "◦ 핵심 기능/성능\n"
        "  - AI 자동화, 실시간 모니터링\n\n"
        "◦ 경쟁사 분석\n"
        "  - A사: 고가, 대기업 전용\n"
        "  - B사: 기능 제한적\n\n"
        "◦ 차별적 경쟁 우위\n"
        "  - 가격 60% 저렴, 설치 간편\n",
        encoding="utf-8",
    )

    # 사업화 모델 (매출 실적)
    (drafts_dir / "04_business_model.md").write_text(
        "# 2-2. 사업화 추진 성과\n\n"
        "◦ 사업 모델\n"
        "  - SaaS 구독 + 하드웨어 판매\n\n"
        "◦ 매출 실적\n"
        "  | 순번 | 목표시장(고객) | 제품·서비스 | 진입시기 | 판매량 | 가격 | 발생매출액 |\n"
        "  |------|-------------|-----------|---------|-------|------|----------|\n"
        "  | 1 | 중소기업 | AI 시스템 | 2023-03 | 15대 | 3,000만원 | 4.5억원 |\n"
        "  | 2 | 대기업 | 시스템+유지보수 | 2023-06 | 10대 | 3,500만원 | 3.5억원 |\n"
        "2023년 매출 8억, 2024년 매출 12억, 2025년 매출 18.5억 목표\n",
        encoding="utf-8",
    )

    # 사업화 추진 전략 (마일스톤)
    (drafts_dir / "05_market_analysis.md").write_text(
        "# 3-1. 사업화 추진 전략\n\n"
        "◦ 성장 전략\n"
        "  - 국내 시장 점유율 5% → 10% 확대 전략\n\n"
        "◦ 마케팅/판로 전략\n"
        "  - 전시회 참가, 레퍼런스 마케팅\n\n"
        "◦ 사업 추진 일정\n"
        "  | 순번 | 추진내용 | 추진기간 | 세부내용 |\n"
        "  |------|---------|---------|----------|\n"
        "  | 1 | AI 모델 고도화 | 2025.06~08 | 작물별 특화 모델 |\n"
        "  | 2 | 양산 체계 구축 | 2025.07~09 | 단가 20% 절감 |\n"
        "  | 3 | 해외 실증 | 2025.09~11 | 현지 3개 농가 |\n",
        encoding="utf-8",
    )

    # 자금운용 계획
    (drafts_dir / "06_growth_strategy.md").write_text(
        "# 3-2. 자금운용 계획\n\n"
        "◦ 사업비 총괄\n"
        "  - 총사업비: 285,000,000원 (100%)\n"
        "  - 정부지원사업비: 200,000,000원 (70.2%)\n"
        "  - 자기부담(현금): 30,000,000원 (10.5%)\n"
        "  - 자기부담(현물): 55,000,000원 (19.3%)\n\n"
        "◦ 사업비 구성 상세\n"
        "  | 순번 | 비목 | 산출근거 | 금액(원) | 재원 |\n"
        "  |------|------|---------|---------|------|\n"
        "  | 1 | 재료비 | 부품 구입 | 50,000,000 | 정부지원 |\n"
        "  | 2 | 인건비 | 개발 인력 | 60,000,000 | 정부지원 |\n",
        encoding="utf-8",
    )

    # 팀 구성
    (drafts_dir / "07_team.md").write_text(
        "# 4. 기업 구성 (Team)\n\n"
        "4-1-1. 대표자 역량\n\n"
        "◦ 김대표 대표\n"
        "  - 서울대 공학 석사, 10년 경력\n\n"
        "4-1-2. 전문 인력 현황\n"
        "  | 고용여부 | 순번 | 직위 | 담당업무 | 보유역량 |\n"
        "  |---------|------|------|---------|----------|\n"
        "  | 기고용 | 1 | CTO | AI/ML 개발 | 박사, 8년 경력 |\n"
        "  | 기고용 | 2 | 영업이사 | 영업/마케팅 | B2B 7년 |\n"
        "  | 채용예정 | 3 | 데이터엔지니어 | 데이터 파이프라인 | 5년 경력 |\n\n"
        "4-2. 보유 인프라 등 활용 계획\n"
        "◦ 산업재산권 현황: 특허 3건\n",
        encoding="utf-8",
    )

    # 재무 계획
    (drafts_dir / "08_financial_plan.md").write_text(
        "# 재무 계획 종합 분석\n\n"
        "◦ 사업비 구성 검증\n"
        "  - 총사업비: 285,000,000원\n"
        "  - 정부지원금: 200,000,000원\n\n"
        "◦ 투자유치 가점\n"
        "  - 투자유치 금액: 0원\n",
        encoding="utf-8",
    )

    # 사업비 집행 계획
    (drafts_dir / "09_funding_plan.md").write_text(
        "# 사업비 집행 계획 (상세)\n\n"
        "◦ 비목별 집행 계획\n"
        "  1. 재료비: 부품 구입\n"
        "     금액: 50,000,000원 (정부지원)\n"
        "  2. 인건비: 개발 인력\n"
        "     금액: 60,000,000원 (정부지원)\n",
        encoding="utf-8",
    )

    return project_dir


# ═══════════════════════════════════════════════════════════════
#  VISUALIZE 모듈 테스트
# ═══════════════════════════════════════════════════════════════

class TestVisualizeModule:
    """sandoc.visualize 모듈 단위 테스트."""

    def test_import(self):
        """visualize 모듈 임포트 가능."""
        from sandoc.visualize import (
            run_visualize,
            generate_bar_chart_svg,
            generate_pie_chart_svg,
            generate_funnel_chart_svg,
            generate_org_chart_svg,
            generate_timeline_svg,
        )
        assert callable(run_visualize)
        assert callable(generate_bar_chart_svg)

    def test_bar_chart_svg(self):
        """바 차트 SVG 생성."""
        from sandoc.visualize import generate_bar_chart_svg

        data = [
            {"year": "2023", "amount": 8.0, "unit": "억원"},
            {"year": "2024", "amount": 12.0, "unit": "억원"},
            {"year": "2025", "amount": 18.5, "unit": "억원"},
        ]
        svg = generate_bar_chart_svg(data, "매출 추이")
        assert svg.startswith("<svg")
        assert "</svg>" in svg
        assert "매출 추이" in svg
        assert "2023" in svg
        assert "2024" in svg
        assert "2025" in svg

    def test_bar_chart_empty(self):
        """빈 데이터 → 빈 문자열."""
        from sandoc.visualize import generate_bar_chart_svg
        assert generate_bar_chart_svg([]) == ""

    def test_pie_chart_svg(self):
        """파이 차트 SVG 생성."""
        from sandoc.visualize import generate_pie_chart_svg

        data = {
            "정부지원": 200_000_000,
            "현금": 30_000_000,
            "현물": 55_000_000,
        }
        svg = generate_pie_chart_svg(data, "사업비 구성")
        assert svg.startswith("<svg")
        assert "</svg>" in svg
        assert "사업비 구성" in svg
        assert "path" in svg.lower()

    def test_pie_chart_empty(self):
        """빈 데이터 → 빈 문자열."""
        from sandoc.visualize import generate_pie_chart_svg
        assert generate_pie_chart_svg({}) == ""

    def test_funnel_chart_svg(self):
        """퍼널 차트 SVG 생성."""
        from sandoc.visualize import generate_funnel_chart_svg

        data = {"TAM": 50000.0, "SAM": 3000.0, "SOM": 500.0}
        svg = generate_funnel_chart_svg(data)
        assert svg.startswith("<svg")
        assert "TAM" in svg
        assert "SAM" in svg
        assert "SOM" in svg

    def test_funnel_chart_empty(self):
        from sandoc.visualize import generate_funnel_chart_svg
        assert generate_funnel_chart_svg({}) == ""

    def test_org_chart_svg(self):
        """조직도 SVG 생성."""
        from sandoc.visualize import generate_org_chart_svg

        team = [
            {"position": "대표이사", "role": "경영총괄", "type": "대표"},
            {"position": "CTO", "role": "기술개발", "type": "기고용"},
            {"position": "영업이사", "role": "영업", "type": "기고용"},
        ]
        svg = generate_org_chart_svg(team)
        assert svg.startswith("<svg")
        assert "대표이사" in svg
        assert "CTO" in svg

    def test_org_chart_empty(self):
        from sandoc.visualize import generate_org_chart_svg
        assert generate_org_chart_svg([]) == ""

    def test_timeline_svg(self):
        """타임라인 SVG 생성."""
        from sandoc.visualize import generate_timeline_svg

        milestones = [
            {"task": "AI 모델 개발", "period": "2025.06~08", "detail": "고도화"},
            {"task": "양산 구축", "period": "2025.07~09", "detail": "단가 절감"},
        ]
        svg = generate_timeline_svg(milestones)
        assert svg.startswith("<svg")
        assert "AI" in svg
        assert "2025" in svg

    def test_timeline_empty(self):
        from sandoc.visualize import generate_timeline_svg
        assert generate_timeline_svg([]) == ""

    def test_run_visualize_no_drafts(self, tmp_path):
        """초안 없음 → 오류 반환."""
        from sandoc.visualize import run_visualize

        project_dir = tmp_path / "no-vis"
        project_dir.mkdir()
        result = run_visualize(project_dir)
        assert result["success"] is False
        assert len(result["errors"]) > 0

    def test_run_visualize_with_data(self, sample_project):
        """샘플 프로젝트로 시각화 생성."""
        from sandoc.visualize import run_visualize

        result = run_visualize(sample_project)
        assert result["success"] is True
        assert len(result["charts"]) > 0
        assert result["output_dir"]

        # 출력 디렉토리에 SVG 파일 존재 확인
        output_dir = Path(result["output_dir"])
        assert output_dir.is_dir()
        svg_files = list(output_dir.glob("*.svg"))
        assert len(svg_files) > 0

        # JSON 설정 파일도 생성 확인
        json_files = list(output_dir.glob("*.json"))
        assert len(json_files) > 0

    def test_run_visualize_budget_chart(self, sample_project):
        """사업비 파이 차트 생성 확인."""
        from sandoc.visualize import run_visualize

        result = run_visualize(sample_project)
        chart_types = [c["type"] for c in result["charts"]]
        assert "pie" in chart_types

    def test_run_visualize_revenue_chart(self, sample_project):
        """매출 추이 바 차트 생성 확인."""
        from sandoc.visualize import run_visualize

        result = run_visualize(sample_project)
        chart_types = [c["type"] for c in result["charts"]]
        assert "bar" in chart_types

    def test_run_visualize_funnel_chart(self, sample_project):
        """TAM/SAM/SOM 퍼널 차트 생성 확인."""
        from sandoc.visualize import run_visualize

        result = run_visualize(sample_project)
        chart_types = [c["type"] for c in result["charts"]]
        assert "funnel" in chart_types

    def test_extract_revenue_data(self):
        """매출 데이터 추출 테스트."""
        from sandoc.visualize import _extract_revenue_data
        sections = {
            "business_model": "2023년 매출 8억, 2024년 매출 12억, 2025년 매출 18.5억",
        }
        data = _extract_revenue_data(sections)
        assert len(data) == 3
        assert data[0]["year"] == "2023"
        assert data[0]["amount"] == 8.0

    def test_extract_budget_data(self):
        """사업비 데이터 추출 테스트."""
        from sandoc.visualize import _extract_budget_data
        sections = {
            "growth_strategy": (
                "정부지원금: 200,000,000원\n"
                "자기부담(현금): 30,000,000원\n"
                "자기부담(현물): 55,000,000원\n"
            ),
        }
        data = _extract_budget_data(sections)
        assert "정부지원" in data
        assert data["정부지원"] == 200_000_000

    def test_extract_market_data(self):
        """TAM/SAM/SOM 데이터 추출 테스트."""
        from sandoc.visualize import _extract_market_data
        sections = {
            "solution": "TAM(전체 시장): 5조원\nSAM(유효 시장): 3000억\nSOM(목표 시장 규모): 500억",
        }
        data = _extract_market_data(sections)
        assert "TAM" in data
        assert "SAM" in data
        assert "SOM" in data


# ═══════════════════════════════════════════════════════════════
#  REVIEW 모듈 테스트
# ═══════════════════════════════════════════════════════════════

class TestReviewModule:
    """sandoc.review 모듈 단위 테스트."""

    def test_import(self):
        """review 모듈 임포트 가능."""
        from sandoc.review import (
            run_review,
            _check_sections_present,
            _check_word_count,
            _check_keywords,
            _check_financial_consistency,
        )
        assert callable(run_review)

    def test_check_sections_present_all(self):
        """모든 섹션 존재."""
        from sandoc.review import _check_sections_present, REQUIRED_SECTIONS
        sections = {s: "내용" for s in REQUIRED_SECTIONS}
        present, missing = _check_sections_present(sections)
        assert len(present) == len(REQUIRED_SECTIONS)
        assert len(missing) == 0

    def test_check_sections_present_partial(self):
        """일부 섹션 누락."""
        from sandoc.review import _check_sections_present
        sections = {"company_overview": "내용", "problem_recognition": "내용"}
        present, missing = _check_sections_present(sections)
        assert len(present) == 2
        assert "solution" in missing

    def test_check_word_count_sufficient(self):
        """충분한 분량."""
        from sandoc.review import _check_word_count, MIN_CHARS_PER_SECTION
        sections = {"test": "가" * 600}
        result = _check_word_count(sections)
        assert result["test"]["sufficient"] is True
        assert result["test"]["chars"] == 600

    def test_check_word_count_insufficient(self):
        """부족한 분량."""
        from sandoc.review import _check_word_count
        sections = {"test": "짧은 내용"}
        result = _check_word_count(sections)
        assert result["test"]["sufficient"] is False

    def test_check_keywords(self):
        """키워드 검사."""
        from sandoc.review import _check_keywords
        sections = {
            "problem_recognition": "문제점과 필요성, 개발 동기, 배경, 현황 분석, 기존 한계와 어려움",
        }
        result = _check_keywords(sections)
        assert "문제인식" in result
        assert result["문제인식"]["coverage"] > 0.5

    def test_check_financial_consistency_good(self):
        """재무 데이터 일관성 양호."""
        from sandoc.review import _check_financial_consistency
        sections = {
            "growth_strategy": (
                "총사업비: 285,000,000원\n"
                "정부지원금: 200,000,000원\n"
                "자기부담(현금): 30,000,000원\n"
                "자기부담(현물): 55,000,000원\n"
            ),
        }
        result = _check_financial_consistency(sections)
        assert result["consistent"] is True

    def test_check_financial_consistency_mismatch(self):
        """재무 데이터 불일치."""
        from sandoc.review import _check_financial_consistency
        sections = {
            "company_overview": (
                "총사업비: 300,000,000원\n"
                "정부지원금: 200,000,000원\n"
                "자기부담(현금): 30,000,000원\n"
                "자기부담(현물): 55,000,000원\n"
            ),
        }
        result = _check_financial_consistency(sections)
        assert result["consistent"] is False
        assert len(result["issues"]) > 0

    def test_run_review_no_drafts(self, tmp_path):
        """초안 없음 → 오류."""
        from sandoc.review import run_review
        project_dir = tmp_path / "no-review"
        project_dir.mkdir()
        result = run_review(project_dir)
        assert result["success"] is False

    def test_run_review_with_data(self, sample_project):
        """샘플 프로젝트로 검토 실행."""
        from sandoc.review import run_review

        result = run_review(sample_project)
        assert result["success"] is True
        assert 0 <= result["overall_score"] <= 100
        assert result["output_path"]

        # review.md 생성 확인
        review_path = Path(result["output_path"])
        assert review_path.exists()
        content = review_path.read_text(encoding="utf-8")
        assert "사업계획서 자가 검토 보고서" in content
        assert "종합 준비도" in content

    def test_run_review_section_scores(self, sample_project):
        """섹션별 점수 반환."""
        from sandoc.review import run_review

        result = run_review(sample_project)
        assert "section_scores" in result
        assert len(result["section_scores"]) > 0

    def test_run_review_all_sections_present(self, sample_project):
        """모든 필수 섹션 존재."""
        from sandoc.review import run_review

        result = run_review(sample_project)
        assert len(result.get("missing_sections", [])) == 0

    def test_run_review_financial_check(self, sample_project):
        """재무 검증 결과 포함."""
        from sandoc.review import run_review

        result = run_review(sample_project)
        assert "financial" in result

    def test_run_review_custom_output(self, sample_project, tmp_path):
        """사용자 지정 출력 경로."""
        from sandoc.review import run_review

        custom = tmp_path / "my_review.md"
        result = run_review(sample_project, output_path=custom)
        assert result["success"] is True
        assert custom.exists()


# ═══════════════════════════════════════════════════════════════
#  PROFILE-REGISTER 모듈 테스트
# ═══════════════════════════════════════════════════════════════

class TestProfileRegisterModule:
    """sandoc.profile_register 모듈 단위 테스트."""

    def test_import(self):
        """profile_register 모듈 임포트 가능."""
        from sandoc.profile_register import (
            run_profile_register,
            extract_company_info,
            create_profile_from_info,
            save_profile,
        )
        assert callable(run_profile_register)

    def test_create_profile_basic(self):
        """기본 프로필 생성."""
        from sandoc.profile_register import create_profile_from_info

        info = {
            "company_name": "(주)테스트회사",
            "ceo_name": "김대표",
            "business_registration_no": "123-45-67890",
        }
        profile = create_profile_from_info(info)
        assert profile["company_name"] == "(주)테스트회사"
        assert profile["ceo_name"] == "김대표"
        assert profile["business_registration_no"] == "123-45-67890"

    def test_save_profile(self, tmp_path):
        """프로필 파일 저장."""
        from sandoc.profile_register import save_profile

        profile = {
            "profile_name": "(주)테스트",
            "company_name": "(주)테스트",
            "ceo_name": "홍길동",
        }
        path = save_profile(profile, tmp_path / "profiles")
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["company_name"] == "(주)테스트"

    def test_extract_from_text_doc(self, tmp_path):
        """텍스트 문서에서 정보 추출."""
        from sandoc.profile_register import extract_company_info

        # 사업자등록증 텍스트 시뮬레이션
        doc = tmp_path / "사업자등록증.txt"
        doc.write_text(
            "사업자등록증\n"
            "상호: (주)스마트테크\n"
            "대표자: 김창업\n"
            "사업자등록번호: 123-45-67890\n"
            "사업장 소재지: 서울시 강남구 테헤란로 123\n"
            "개업연월일: 2021-06-15\n",
            encoding="utf-8",
        )

        info = extract_company_info([doc])
        assert info.get("company_name") == "(주)스마트테크"
        assert info.get("ceo_name") == "김창업"
        assert "123-45-67890" in info.get("business_registration_no", "")

    def test_run_profile_register_manual(self, tmp_path):
        """수동 입력으로 프로필 등록."""
        from sandoc.profile_register import run_profile_register

        result = run_profile_register(
            company_name="(주)수동입력회사",
            ceo_name="박대표",
            profiles_dir=tmp_path / "profiles",
        )
        assert result["success"] is True
        assert result["profile_path"]
        assert Path(result["profile_path"]).exists()

        data = json.loads(Path(result["profile_path"]).read_text(encoding="utf-8"))
        assert data["company_name"] == "(주)수동입력회사"
        assert data["ceo_name"] == "박대표"

    def test_run_profile_register_from_docs(self, tmp_path):
        """문서에서 프로필 등록."""
        from sandoc.profile_register import run_profile_register

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "사업자등록증.txt").write_text(
            "사업자등록증\n상호: (주)문서추출\n대표자: 이추출\n"
            "사업자등록번호: 987-65-43210\n",
            encoding="utf-8",
        )

        result = run_profile_register(
            docs_path=docs_dir,
            profiles_dir=tmp_path / "profiles",
        )
        assert result["success"] is True
        assert "(주)문서추출" in Path(result["profile_path"]).read_text(encoding="utf-8")

    def test_run_profile_register_no_input(self, tmp_path):
        """입력 없이도 프로필 생성 (unknown)."""
        from sandoc.profile_register import run_profile_register

        result = run_profile_register(
            profiles_dir=tmp_path / "profiles",
        )
        assert result["success"] is True


# ═══════════════════════════════════════════════════════════════
#  HTML 출력 테스트
# ═══════════════════════════════════════════════════════════════

class TestHTMLGeneration:
    """assemble HTML 출력 테스트."""

    def test_generate_html_basic(self):
        """기본 HTML 생성."""
        from sandoc.assemble import generate_html
        from sandoc.generator import GeneratedPlan, GeneratedSection

        plan = GeneratedPlan(
            title="테스트 사업계획서",
            company_name="(주)테스트",
        )
        plan.sections.append(GeneratedSection(
            title="기업 개요",
            content="◦ 기업명: (주)테스트\n◦ 대표: 홍길동",
            section_key="company_overview",
            section_index=0,
            word_count=100,
        ))

        html = generate_html(plan)
        assert "<!DOCTYPE html>" in html
        assert "테스트 사업계획서" in html
        assert "(주)테스트" in html
        assert "기업 개요" in html
        assert "목 차" in html

    def test_generate_html_with_table(self):
        """표가 포함된 HTML 생성."""
        from sandoc.assemble import generate_html
        from sandoc.generator import GeneratedPlan, GeneratedSection

        plan = GeneratedPlan(title="테스트", company_name="테스트사")
        plan.sections.append(GeneratedSection(
            title="팀 구성",
            content=(
                "| 이름 | 직위 |\n"
                "|------|------|\n"
                "| 홍길동 | 대표 |\n"
                "| 김철수 | CTO |"
            ),
            section_key="team",
            section_index=0,
            word_count=50,
        ))

        html = generate_html(plan)
        assert "<table" in html
        assert "홍길동" in html

    def test_generate_html_with_charts(self, sample_project):
        """차트가 인라인된 HTML 생성."""
        from sandoc.visualize import run_visualize
        from sandoc.assemble import generate_html
        from sandoc.generator import GeneratedPlan, GeneratedSection

        # 먼저 시각화 생성
        run_visualize(sample_project)

        plan = GeneratedPlan(title="테스트", company_name="테스트사")
        plan.sections.append(GeneratedSection(
            title="자금운용 계획",
            content="사업비 총괄 내용",
            section_key="growth_strategy",
            section_index=0,
            word_count=50,
        ))

        visuals_dir = sample_project / "output" / "visuals"
        html = generate_html(plan, visuals_dir=visuals_dir)
        assert "chart-container" in html

    def test_assemble_produces_html(self, sample_project):
        """assemble 실행 시 HTML도 생성."""
        from sandoc.assemble import run_assemble

        result = run_assemble(sample_project)
        assert result["success"] is True
        # HTML 경로가 결과에 포함
        if result.get("html_path"):
            html_path = Path(result["html_path"])
            assert html_path.exists()
            content = html_path.read_text(encoding="utf-8")
            assert "<!DOCTYPE html>" in content

    def test_md_to_html_body(self):
        """마크다운→HTML 변환."""
        from sandoc.assemble import _md_to_html_body

        text = "# 제목\n\n◦ 항목 1\n  - 상세 내용\n\n**굵게**"
        html = _md_to_html_body(text)
        assert '<h1 id="제목">제목</h1>' in html
        assert "bullet" in html
        assert "<strong>굵게</strong>" in html


# ═══════════════════════════════════════════════════════════════
#  CLI 테스트
# ═══════════════════════════════════════════════════════════════

class TestVisualizeCLI:
    """sandoc visualize CLI 명령어 테스트."""

    def test_visualize_help(self):
        """visualize --help 작동."""
        from sandoc.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["visualize", "--help"])
        assert result.exit_code == 0
        assert "시각화" in result.output or "visualize" in result.output.lower()

    def test_visualize_nonexistent(self):
        """존재하지 않는 디렉토리 → 오류."""
        from sandoc.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["visualize", "/nonexistent/path"])
        assert result.exit_code != 0

    def test_visualize_with_data(self, sample_project):
        """샘플 프로젝트로 visualize 실행."""
        from sandoc.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["visualize", str(sample_project)])
        assert result.exit_code == 0
        assert "시각화 생성 완료" in result.output


class TestReviewCLI:
    """sandoc review CLI 명령어 테스트."""

    def test_review_help(self):
        """review --help 작동."""
        from sandoc.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["review", "--help"])
        assert result.exit_code == 0
        assert "검토" in result.output or "review" in result.output.lower()

    def test_review_nonexistent(self):
        """존재하지 않는 디렉토리 → 오류."""
        from sandoc.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["review", "/nonexistent/path"])
        assert result.exit_code != 0

    def test_review_with_data(self, sample_project):
        """샘플 프로젝트로 review 실행."""
        from sandoc.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["review", str(sample_project)])
        assert result.exit_code == 0
        assert "종합 점수" in result.output


class TestProfileRegisterCLI:
    """sandoc profile-register CLI 명령어 테스트."""

    def test_profile_register_help(self):
        """profile-register --help 작동."""
        from sandoc.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["profile-register", "--help"])
        assert result.exit_code == 0
        assert "프로필" in result.output or "profile" in result.output.lower()

    def test_profile_register_manual(self, tmp_path):
        """수동 입력으로 프로필 등록."""
        from sandoc.cli import main
        runner = CliRunner()
        result = runner.invoke(main, [
            "profile-register",
            "--company", "(주)CLI테스트",
            "--ceo", "김테스트",
            "-o", str(tmp_path / "profiles"),
        ])
        assert result.exit_code == 0
        assert "등록" in result.output or "성공" in result.output

    def test_profile_register_from_docs(self, tmp_path):
        """문서로 프로필 등록."""
        from sandoc.cli import main

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "사업자등록증.txt").write_text(
            "상호: (주)문서테스트\n대표자: 박CLI\n", encoding="utf-8"
        )

        runner = CliRunner()
        result = runner.invoke(main, [
            "profile-register",
            "-d", str(docs_dir),
            "-o", str(tmp_path / "profiles"),
        ])
        assert result.exit_code == 0


# ═══════════════════════════════════════════════════════════════
#  통합 테스트: visualize → review → assemble (with HTML)
# ═══════════════════════════════════════════════════════════════

class TestIntegrationWorkflow:
    """visualize → review → assemble 통합 워크플로우."""

    def test_full_workflow(self, sample_project):
        """전체 워크플로우: visualize → review → assemble."""
        from sandoc.visualize import run_visualize
        from sandoc.review import run_review
        from sandoc.assemble import run_assemble

        # 1. 시각화 생성
        vis_result = run_visualize(sample_project)
        assert vis_result["success"] is True
        assert len(vis_result["charts"]) >= 1

        # 2. 자가 검토
        review_result = run_review(sample_project)
        assert review_result["success"] is True
        assert review_result["overall_score"] > 0

        # 3. 조립 (HTML 포함)
        assemble_result = run_assemble(sample_project)
        assert assemble_result["success"] is True

        # HTML에 차트가 포함되었는지 확인
        if assemble_result.get("html_path"):
            html = Path(assemble_result["html_path"]).read_text(encoding="utf-8")
            assert "<!DOCTYPE html>" in html
            # SVG 차트가 인라인되었는지
            if vis_result["charts"]:
                assert "chart-container" in html

    @pytest.mark.skipif(not SAMPLE_PROJECT.exists(), reason="샘플 프로젝트 필요")
    def test_workflow_with_sample_project(self, tmp_path):
        """실제 샘플 프로젝트로 전체 워크플로우."""
        from sandoc.visualize import run_visualize
        from sandoc.review import run_review
        from sandoc.assemble import run_assemble

        project_copy = tmp_path / "workflow-sample"
        shutil.copytree(SAMPLE_PROJECT, project_copy)

        vis_result = run_visualize(project_copy)
        assert vis_result["success"] is True

        review_result = run_review(project_copy)
        assert review_result["success"] is True
        assert review_result["overall_score"] > 0

        assemble_result = run_assemble(project_copy)
        assert assemble_result["success"] is True
        assert assemble_result["section_count"] == 9
