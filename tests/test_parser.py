"""
sandoc 파서 테스트

tests/v1-data/ 에 실제 파일이 있을 때만 실행됩니다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# 테스트 데이터 경로
V1_DATA = Path(__file__).parent / "v1-data"

HWP_FILE = V1_DATA / "[별첨 1] 2025년도 창업도약패키지(일반형) 창업기업 사업계획서 양식.hwp"
PDF_FILE = V1_DATA / "[공고문] 2025년도 창업도약패키지(일반형) 창업기업 모집 수정공고.pdf"

has_hwp = HWP_FILE.exists()
has_pdf = PDF_FILE.exists()


# ── HWP 파서 테스트 ───────────────────────────────────────────────

@pytest.mark.skipif(not has_hwp, reason="HWP 테스트 파일 없음")
class TestParseHwp:
    """HWP 파서 테스트."""

    def test_parse_hwp_returns_result(self) -> None:
        from sandoc.parser import parse_hwp, HwpParseResult

        result = parse_hwp(HWP_FILE)
        assert isinstance(result, HwpParseResult)
        assert result.file_path == str(HWP_FILE)

    def test_hwp_has_paragraphs(self) -> None:
        from sandoc.parser import parse_hwp

        result = parse_hwp(HWP_FILE)
        assert len(result.paragraphs) > 0, "HWP 에서 문단이 추출되어야 합니다"

    def test_hwp_has_text(self) -> None:
        from sandoc.parser import parse_hwp

        result = parse_hwp(HWP_FILE)
        assert len(result.full_text) > 0, "HWP 에서 텍스트가 추출되어야 합니다"

    def test_hwp_version(self) -> None:
        from sandoc.parser import parse_hwp

        result = parse_hwp(HWP_FILE)
        assert result.version, "HWP 버전 정보가 있어야 합니다"
        assert result.version.startswith("5"), "HWP 5.x 버전이어야 합니다"

    def test_hwp_has_fonts(self) -> None:
        from sandoc.parser import parse_hwp

        result = parse_hwp(HWP_FILE)
        assert len(result.fonts) > 0, "HWP 에서 폰트 정보가 추출되어야 합니다"

    def test_hwp_has_sections(self) -> None:
        from sandoc.parser import parse_hwp

        result = parse_hwp(HWP_FILE)
        assert len(result.sections) > 0, "HWP 에서 섹션이 있어야 합니다"

    def test_hwp_page_layout(self) -> None:
        from sandoc.parser import parse_hwp

        result = parse_hwp(HWP_FILE)
        layout = result.page_layout
        # A4 기본 크기 확인 (오차 허용)
        assert 200 < layout.paper_width_mm < 220, f"용지 폭이 A4 범위여야 합니다: {layout.paper_width_mm}"
        assert 290 < layout.paper_height_mm < 300, f"용지 높이가 A4 범위여야 합니다: {layout.paper_height_mm}"


# ── PDF 파서 테스트 ───────────────────────────────────────────────

@pytest.mark.skipif(not has_pdf, reason="PDF 테스트 파일 없음")
class TestParsePdf:
    """PDF 파서 테스트."""

    def test_parse_pdf_returns_result(self) -> None:
        from sandoc.parser import parse_pdf, PdfParseResult

        result = parse_pdf(PDF_FILE)
        assert isinstance(result, PdfParseResult)
        assert result.file_path == str(PDF_FILE)

    def test_pdf_has_pages(self) -> None:
        from sandoc.parser import parse_pdf

        result = parse_pdf(PDF_FILE)
        assert result.page_count > 0, "PDF 에서 페이지가 추출되어야 합니다"

    def test_pdf_has_text(self) -> None:
        from sandoc.parser import parse_pdf

        result = parse_pdf(PDF_FILE)
        assert len(result.full_text) > 0, "PDF 에서 텍스트가 추출되어야 합니다"

    def test_pdf_contains_keywords(self) -> None:
        from sandoc.parser import parse_pdf

        result = parse_pdf(PDF_FILE)
        text = result.full_text
        # 공고문에서 기대되는 키워드
        assert "창업" in text or "사업" in text, "공고문에 '창업' 또는 '사업' 키워드가 있어야 합니다"


# ── parse_any 테스트 ──────────────────────────────────────────────

@pytest.mark.skipif(not has_hwp, reason="HWP 테스트 파일 없음")
def test_parse_any_hwp() -> None:
    from sandoc.parser import parse_any, HwpParseResult

    result = parse_any(HWP_FILE)
    assert isinstance(result, HwpParseResult)


@pytest.mark.skipif(not has_pdf, reason="PDF 테스트 파일 없음")
def test_parse_any_pdf() -> None:
    from sandoc.parser import parse_any, PdfParseResult

    result = parse_any(PDF_FILE)
    assert isinstance(result, PdfParseResult)


def test_parse_any_unsupported() -> None:
    from sandoc.parser import parse_any

    with pytest.raises(ValueError, match="지원하지 않는"):
        parse_any("test.xyz")


# ── 에러 케이스 테스트 ────────────────────────────────────────────

def test_parse_hwp_file_not_found() -> None:
    from sandoc.parser import parse_hwp

    with pytest.raises(FileNotFoundError):
        parse_hwp("/nonexistent/file.hwp")


def test_parse_pdf_file_not_found() -> None:
    from sandoc.parser import parse_pdf

    with pytest.raises(FileNotFoundError):
        parse_pdf("/nonexistent/file.pdf")
