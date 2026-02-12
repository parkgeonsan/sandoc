"""
sandoc.parser — HWP / PDF / 기타 문서 파서

HWP 5.x OLE2 파일을 olefile + zlib + struct 로 직접 파싱하여
텍스트, 표, 스타일 정보를 추출합니다.

참고: tests/v1-data/analysis/04-hwp-direct-parsing.md
"""

from __future__ import annotations

import logging
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import olefile

logger = logging.getLogger(__name__)

# ── HWP 5.x 레코드 태그 ID ──────────────────────────────────────
# Body text record tags (HWPTAG_BEGIN = 66)
HWPTAG_PARA_HEADER = 66                      # 문단 헤더
HWPTAG_PARA_TEXT = 67                         # 문단 텍스트
HWPTAG_PARA_CHAR_SHAPE = 68                  # 문단 문자 모양
HWPTAG_PARA_LINE_SEG = 69                     # 줄 나누기
HWPTAG_CTRL_HEADER = 71                       # 컨트롤 헤더
HWPTAG_LIST_HEADER = 72                       # 리스트 헤더
HWPTAG_SEC_DEF = 73                           # 구역 정의 (페이지 레이아웃 포함)
HWPTAG_COLUMN_DEF = 74                        # 단 정의
HWPTAG_TABLE = 75                             # 표 정의
HWPTAG_CELL_DEF = 77                          # 셀 정의

# DocInfo record tags
HWPTAG_DOCUMENT_PROPERTIES = 16              # 문서 속성
HWPTAG_ID_MAPPINGS = 17                      # ID 매핑
HWPTAG_FACE_NAME = 19                        # 폰트 이름
HWPTAG_BORDER_FILL = 20                      # 테두리/채우기
HWPTAG_CHAR_SHAPE = 21                       # 문자 모양
HWPTAG_TAB_DEF = 22                          # 탭 정의
HWPTAG_NUMBERING = 23                        # 번호 매기기
HWPTAG_BULLET = 24                           # 불릿
HWPTAG_PARA_SHAPE = 25                       # 문단 모양
HWPTAG_STYLE = 26                            # 스타일

# HWP 인라인 컨트롤 코드 (UTF-16LE 2바이트 문자)
# 0x0001~0x0008: 특수 컨트롤 문자, 각각 뒤에 14바이트(7 UTF-16LE chars) 추가 데이터
HWP_INLINE_CTRL_CHARS = set(range(0x0001, 0x0009))
# 0x000A: 줄바꿈, 0x000D: 문단 끝 — 일반 텍스트로 처리
HWP_CHAR_LINE_BREAK = 0x000A
HWP_CHAR_PARA_END = 0x000D

# ── HWP 단위 변환 ───────────────────────────────────────────────
HWPUNIT_TO_MM = 1 / 7200 * 25.4   # 1 HWP unit = 1/7200 inch
HWPUNIT_TO_PT = 1 / 100           # 폰트 크기용 (HWP는 pt × 100)


# ── 데이터 클래스 ────────────────────────────────────────────────

@dataclass
class HwpRecord:
    """HWP 5.x TLV 레코드."""
    tag_id: int
    level: int
    size: int
    data: bytes
    offset: int = 0

    @property
    def tag_name(self) -> str:
        """사람이 읽을 수 있는 태그 이름."""
        _names = {
            HWPTAG_PARA_HEADER: "PARA_HEADER",
            HWPTAG_PARA_TEXT: "PARA_TEXT",
            HWPTAG_PARA_CHAR_SHAPE: "PARA_CHAR_SHAPE",
            HWPTAG_PARA_LINE_SEG: "PARA_LINE_SEG",
            HWPTAG_CTRL_HEADER: "CTRL_HEADER",
            HWPTAG_LIST_HEADER: "LIST_HEADER",
            HWPTAG_SEC_DEF: "SEC_DEF",
            HWPTAG_TABLE: "TABLE",
            HWPTAG_CELL_DEF: "CELL_DEF",
        }
        return _names.get(self.tag_id, f"TAG_{self.tag_id}")


@dataclass
class HwpParagraph:
    """추출된 문단."""
    text: str
    char_shape_ids: list[int] = field(default_factory=list)
    style_id: int = 0
    level: int = 0


@dataclass
class HwpTable:
    """추출된 표 구조."""
    rows: int
    cols: int
    cells: list[list[str]] = field(default_factory=list)
    table_index: int = 0


@dataclass
class HwpPageLayout:
    """페이지 레이아웃 정보."""
    paper_width_mm: float = 210.0
    paper_height_mm: float = 297.0
    margin_top_mm: float = 10.0
    margin_bottom_mm: float = 15.0
    margin_left_mm: float = 20.0
    margin_right_mm: float = 20.0
    margin_header_mm: float = 15.0
    margin_footer_mm: float = 10.0
    margin_gutter_mm: float = 0.0


@dataclass
class HwpFontInfo:
    """폰트 정보."""
    name: str
    script_type: str = ""   # 한글/영문/한자/일본어/기타/기호/사용자


@dataclass
class HwpCharShape:
    """문자 모양 정보."""
    font_ids: list[int] = field(default_factory=list)  # 7개 스크립트별 폰트 인덱스
    font_size_pt: float = 10.0
    bold: bool = False
    italic: bool = False
    underline: bool = False
    color_rgb: tuple[int, int, int] = (0, 0, 0)


@dataclass
class HwpParseResult:
    """HWP 파싱 결과 전체."""
    file_path: str
    version: str = ""
    compressed: bool = True
    encrypted: bool = False

    paragraphs: list[HwpParagraph] = field(default_factory=list)
    tables: list[HwpTable] = field(default_factory=list)
    page_layout: HwpPageLayout = field(default_factory=HwpPageLayout)
    fonts: list[HwpFontInfo] = field(default_factory=list)
    char_shapes: list[HwpCharShape] = field(default_factory=list)
    styles: list[dict[str, Any]] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        """전체 텍스트를 하나의 문자열로."""
        return "\n".join(p.text for p in self.paragraphs if p.text.strip())

    @property
    def text_paragraphs(self) -> list[str]:
        """비어있지 않은 문단 텍스트 목록."""
        return [p.text for p in self.paragraphs if p.text.strip()]


@dataclass
class PdfParseResult:
    """PDF 파싱 결과."""
    file_path: str
    pages: list[str] = field(default_factory=list)
    tables: list[list[list[str]]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        return "\n\n".join(self.pages)

    @property
    def page_count(self) -> int:
        return len(self.pages)


# ── HWP 바이너리 파싱 함수들 ─────────────────────────────────────

def _read_hwp_header(ole: olefile.OleFileIO) -> dict[str, Any]:
    """FileHeader 스트림에서 버전, 압축/암호화 플래그 읽기."""
    header_data = ole.openstream("FileHeader").read()
    # 처음 32바이트: 시그니처 "HWP Document File"
    signature = header_data[:32].split(b"\x00")[0].decode("ascii", errors="replace")

    # 바이트 32~35: 버전 (little-endian uint32)
    if len(header_data) >= 36:
        version_raw = struct.unpack_from("<I", header_data, 32)[0]
        major = (version_raw >> 24) & 0xFF
        minor = (version_raw >> 16) & 0xFF
        build = (version_raw >> 8) & 0xFF
        revision = version_raw & 0xFF
        version = f"{major}.{minor}.{build}.{revision}"
    else:
        version = "unknown"

    # 바이트 36~39: 속성 플래그
    if len(header_data) >= 40:
        flags = struct.unpack_from("<I", header_data, 36)[0]
        compressed = bool(flags & 0x01)
        encrypted = bool(flags & 0x02)
    else:
        compressed = True
        encrypted = False

    return {
        "signature": signature,
        "version": version,
        "compressed": compressed,
        "encrypted": encrypted,
    }


def _decompress_stream(ole: olefile.OleFileIO, stream_name: str, compressed: bool = True) -> bytes:
    """OLE2 스트림 읽기 + zlib 압축 해제 (raw deflate, wbits=-15)."""
    raw = ole.openstream(stream_name).read()
    if not compressed:
        return raw
    try:
        return zlib.decompress(raw, -15)
    except zlib.error:
        logger.warning("zlib 압축 해제 실패: %s — 원본 데이터 반환", stream_name)
        return raw


def _parse_records(data: bytes) -> list[HwpRecord]:
    """
    바이너리 데이터에서 HWP 5.x TLV 레코드 파싱.

    레코드 헤더: 4바이트 (little-endian uint32)
      - TagID:  bits 0-9   (10 bits)
      - Level:  bits 10-19 (10 bits)
      - Size:   bits 20-31 (12 bits)
      - Size == 0xFFF → 다음 4바이트가 실제 크기 (uint32)
    """
    records: list[HwpRecord] = []
    pos = 0
    while pos + 4 <= len(data):
        header = struct.unpack_from("<I", data, pos)[0]
        tag_id = header & 0x3FF
        level = (header >> 10) & 0x3FF
        size = (header >> 20) & 0xFFF

        pos += 4

        # 확장 크기
        if size == 0xFFF:
            if pos + 4 > len(data):
                break
            size = struct.unpack_from("<I", data, pos)[0]
            pos += 4

        if pos + size > len(data):
            # 잘린 레코드 — 남은 데이터만 저장
            rec_data = data[pos:]
            records.append(HwpRecord(tag_id=tag_id, level=level, size=len(rec_data), data=rec_data, offset=pos))
            break

        rec_data = data[pos: pos + size]
        records.append(HwpRecord(tag_id=tag_id, level=level, size=size, data=rec_data, offset=pos))
        pos += size

    return records


def _decode_para_text(data: bytes) -> str:
    """
    PARA_TEXT 레코드에서 텍스트 추출 (UTF-16LE).

    HWP 인라인 컨트롤 코드(0x0001~0x0008)를 건너뛰고,
    줄바꿈(0x000A)과 문단 끝(0x000D)은 적절히 처리합니다.
    """
    chars: list[str] = []
    i = 0
    while i + 1 < len(data):
        code = struct.unpack_from("<H", data, i)[0]
        i += 2

        if code in HWP_INLINE_CTRL_CHARS:
            # 인라인 컨트롤: 추가 14바이트(7 UTF-16LE chars) 건너뛰기
            i += 14
            continue
        elif code == HWP_CHAR_LINE_BREAK:
            chars.append("\n")
        elif code == HWP_CHAR_PARA_END:
            # 문단 끝 — 무시 (문단 단위로 이미 분리됨)
            continue
        elif code < 0x0020 and code not in (0x0009, 0x000A, 0x000D):
            # 기타 제어문자 건너뛰기 (탭은 유지)
            if code == 0x0009:
                chars.append("\t")
            continue
        else:
            chars.append(chr(code))

    return "".join(chars)


def _parse_page_def(data: bytes) -> HwpPageLayout:
    """PAGE_DEF 레코드에서 페이지 레이아웃 추출."""
    layout = HwpPageLayout()
    if len(data) >= 40:
        vals = struct.unpack_from("<IIIIIIIII", data, 0)
        # 순서: 용지폭, 용지높이, 여백(좌, 우, 상, 하), 머리말, 꼬리말, 제본
        layout.paper_width_mm = round(vals[0] * HWPUNIT_TO_MM, 1)
        layout.paper_height_mm = round(vals[1] * HWPUNIT_TO_MM, 1)
        layout.margin_left_mm = round(vals[2] * HWPUNIT_TO_MM, 1)
        layout.margin_right_mm = round(vals[3] * HWPUNIT_TO_MM, 1)
        layout.margin_top_mm = round(vals[4] * HWPUNIT_TO_MM, 1)
        layout.margin_bottom_mm = round(vals[5] * HWPUNIT_TO_MM, 1)
        layout.margin_header_mm = round(vals[6] * HWPUNIT_TO_MM, 1)
        layout.margin_footer_mm = round(vals[7] * HWPUNIT_TO_MM, 1)
        layout.margin_gutter_mm = round(vals[8] * HWPUNIT_TO_MM, 1)
    return layout


def _parse_table_record(data: bytes) -> tuple[int, int]:
    """TABLE 레코드에서 행×열 크기 추출."""
    if len(data) >= 8:
        # TABLE 레코드 시작: 속성(4바이트) + 행 수(2바이트) + 열 수(2바이트)
        flags = struct.unpack_from("<I", data, 0)[0]
        rows = struct.unpack_from("<H", data, 4)[0]
        cols = struct.unpack_from("<H", data, 6)[0]
        return rows, cols
    return 0, 0


def _parse_face_name(data: bytes) -> str:
    """FACE_NAME 레코드에서 폰트 이름 추출."""
    if len(data) < 3:
        return ""
    # 속성(1바이트) + 이름 길이(2바이트 = UTF-16LE 문자 수) + 이름 데이터
    # name_len = struct.unpack_from("<H", data, 1)[0]
    # 이름은 offset 3부터 UTF-16LE
    # 실제로는 다양한 포맷이 있으므로 null-terminated 검색
    try:
        # 속성 바이트 건너뛰고, 이름 길이 읽기
        _prop = data[0]
        name_len = struct.unpack_from("<H", data, 1)[0]
        name_data = data[3: 3 + name_len * 2]
        return name_data.decode("utf-16-le", errors="replace").rstrip("\x00")
    except Exception:
        return ""


def _parse_char_shape(data: bytes) -> HwpCharShape:
    """CHAR_SHAPE 레코드에서 문자 모양 추출."""
    cs = HwpCharShape()
    if len(data) < 42:
        return cs

    # 7개 스크립트별 폰트 ID (각 2바이트 = 14바이트, offset 0~13)
    cs.font_ids = [struct.unpack_from("<H", data, i * 2)[0] for i in range(7)]

    # offset 14~20: 장평 비율 (각 1바이트, 100 = 100%)
    # offset 21~27: 자간 (각 1바이트)
    # offset 28~34: 상대 크기 (각 1바이트, 100 = 100%)
    # offset 35~41: 글자 위치 (각 1바이트)
    # offset 42~45: 폰트 크기 (uint32, pt × 100)
    if len(data) >= 46:
        font_size_raw = struct.unpack_from("<I", data, 42)[0]
        cs.font_size_pt = round(font_size_raw * HWPUNIT_TO_PT, 1)

    # offset 46~49: 속성 (uint32)
    if len(data) >= 50:
        attr = struct.unpack_from("<I", data, 46)[0]
        cs.italic = bool(attr & 0x01)
        cs.bold = bool(attr & 0x02)
        cs.underline = bool(attr & 0x04)

    # offset 60~63: 글자색 (COLORREF: 0x00BBGGRR)
    if len(data) >= 64:
        color = struct.unpack_from("<I", data, 60)[0]
        if color != 0xFFFFFFFF:  # 0xFFFFFFFF는 기본색
            r = color & 0xFF
            g = (color >> 8) & 0xFF
            b = (color >> 16) & 0xFF
            cs.color_rgb = (r, g, b)

    return cs


# ── 메인 파싱 함수 ───────────────────────────────────────────────

def parse_hwp(path: str | Path) -> HwpParseResult:
    """
    HWP 5.x 파일을 파싱하여 텍스트, 표, 스타일 정보를 추출합니다.

    Args:
        path: HWP 파일 경로

    Returns:
        HwpParseResult: 파싱된 문서 데이터

    Raises:
        FileNotFoundError: 파일이 존재하지 않는 경우
        ValueError: HWP 파일이 아니거나 암호화된 경우
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

    if not olefile.isOleFile(str(path)):
        raise ValueError(f"OLE2(HWP) 파일이 아닙니다: {path}")

    result = HwpParseResult(file_path=str(path))

    with olefile.OleFileIO(str(path)) as ole:
        # 1) 파일 헤더 파싱
        header = _read_hwp_header(ole)
        result.version = header["version"]
        result.compressed = header["compressed"]
        result.encrypted = header["encrypted"]

        logger.info(
            "HWP 파일 열기: %s (v%s, compressed=%s, encrypted=%s)",
            path.name, result.version, result.compressed, result.encrypted,
        )

        if result.encrypted:
            raise ValueError(f"암호화된 HWP 파일은 지원하지 않습니다: {path}")

        # 2) DocInfo 파싱 — 폰트, 문자 모양, 스타일
        if ole.exists("DocInfo"):
            docinfo_data = _decompress_stream(ole, "DocInfo", result.compressed)
            docinfo_records = _parse_records(docinfo_data)
            _extract_docinfo(docinfo_records, result)

        # 3) BodyText 섹션 파싱
        section_idx = 0
        while True:
            stream_name = f"BodyText/Section{section_idx}"
            if not ole.exists(stream_name):
                break
            result.sections.append(stream_name)

            body_data = _decompress_stream(ole, stream_name, result.compressed)
            body_records = _parse_records(body_data)
            _extract_body_content(body_records, result)

            section_idx += 1

        logger.info(
            "파싱 완료: %d 문단, %d 표, %d 폰트, %d 섹션",
            len(result.paragraphs), len(result.tables),
            len(result.fonts), len(result.sections),
        )

    return result


def _extract_docinfo(records: list[HwpRecord], result: HwpParseResult) -> None:
    """DocInfo 레코드에서 폰트, 문자 모양, 스타일 추출."""
    for rec in records:
        if rec.tag_id == HWPTAG_FACE_NAME:
            name = _parse_face_name(rec.data)
            if name:
                result.fonts.append(HwpFontInfo(name=name))

        elif rec.tag_id == HWPTAG_CHAR_SHAPE:
            cs = _parse_char_shape(rec.data)
            result.char_shapes.append(cs)

        elif rec.tag_id == HWPTAG_STYLE:
            # 스타일 레코드: 이름(UTF-16LE null-terminated) + 속성
            try:
                # 한글 이름: null-terminated UTF-16LE
                end = rec.data.find(b"\x00\x00")
                if end >= 0:
                    # null-terminated 이지만 UTF-16LE 이므로 짝수 위치에서 끊기
                    end_pos = end + (1 if end % 2 == 0 else 0)
                    style_name = rec.data[:end_pos].decode("utf-16-le", errors="replace").rstrip("\x00")
                else:
                    style_name = rec.data.decode("utf-16-le", errors="replace").rstrip("\x00")
                result.styles.append({"name": style_name})
            except Exception:
                result.styles.append({"name": ""})


def _extract_body_content(records: list[HwpRecord], result: HwpParseResult) -> None:
    """BodyText 레코드에서 문단, 표, 페이지 레이아웃 추출."""
    table_index = len(result.tables)

    # 표 셀 텍스트를 수집하기 위한 상태 변수
    current_table: HwpTable | None = None
    cell_texts: list[str] = []
    in_table = False

    for rec in records:
        if rec.tag_id == HWPTAG_PARA_TEXT:
            text = _decode_para_text(rec.data)
            if text:
                para = HwpParagraph(text=text, level=rec.level)
                result.paragraphs.append(para)

                # 표 내부 텍스트 수집
                if in_table and current_table is not None:
                    cell_texts.append(text)

        elif rec.tag_id == HWPTAG_TABLE:
            # 이전 표 마무리
            if current_table is not None:
                _finalize_table(current_table, cell_texts)
                result.tables.append(current_table)
                cell_texts = []

            rows, cols = _parse_table_record(rec.data)
            if rows > 0 and cols > 0:
                current_table = HwpTable(rows=rows, cols=cols, table_index=table_index)
                in_table = True
                table_index += 1
                logger.debug("표 발견: %d×%d (index=%d)", rows, cols, table_index - 1)
            else:
                current_table = None
                in_table = False

        elif rec.tag_id == HWPTAG_SEC_DEF:
            # 구역 정의에서 페이지 레이아웃 추출
            result.page_layout = _parse_page_def(rec.data)

    # 마지막 표 마무리
    if current_table is not None:
        _finalize_table(current_table, cell_texts)
        result.tables.append(current_table)


def _finalize_table(table: HwpTable, cell_texts: list[str]) -> None:
    """수집된 셀 텍스트를 행×열 구조로 재배열."""
    if table.rows == 0 or table.cols == 0:
        table.cells = [cell_texts]
        return

    cells: list[list[str]] = []
    for r in range(table.rows):
        row: list[str] = []
        for c in range(table.cols):
            idx = r * table.cols + c
            if idx < len(cell_texts):
                row.append(cell_texts[idx])
            else:
                row.append("")
        cells.append(row)
    table.cells = cells


# ── PDF 파싱 ─────────────────────────────────────────────────────

def parse_pdf(path: str | Path) -> PdfParseResult:
    """
    PDF 파일에서 텍스트와 표를 추출합니다.

    Args:
        path: PDF 파일 경로

    Returns:
        PdfParseResult: 파싱된 PDF 데이터

    Raises:
        FileNotFoundError: 파일이 존재하지 않는 경우
        ImportError: pdfplumber가 설치되지 않은 경우
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

    try:
        import pdfplumber
    except ImportError:
        raise ImportError(
            "pdfplumber가 설치되지 않았습니다. "
            "pip install pdfplumber 로 설치하세요."
        )

    result = PdfParseResult(file_path=str(path))

    with pdfplumber.open(str(path)) as pdf:
        result.metadata = pdf.metadata or {}

        for page in pdf.pages:
            # 텍스트 추출
            text = page.extract_text() or ""
            result.pages.append(text)

            # 표 추출
            tables = page.extract_tables() or []
            for table in tables:
                # pdfplumber table: list[list[str | None]]
                cleaned = []
                for row in table:
                    cleaned.append([cell or "" for cell in row])
                result.tables.append(cleaned)

    logger.info("PDF 파싱 완료: %d 페이지, %d 표", result.page_count, len(result.tables))
    return result


# ── 자동 감지 파서 ───────────────────────────────────────────────

def parse_any(path: str | Path) -> HwpParseResult | PdfParseResult:
    """
    파일 확장자를 기반으로 적절한 파서를 자동 선택합니다.

    Args:
        path: 문서 파일 경로

    Returns:
        HwpParseResult 또는 PdfParseResult

    Raises:
        ValueError: 지원하지 않는 파일 형식인 경우
    """
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".hwp":
        return parse_hwp(path)
    elif suffix == ".pdf":
        return parse_pdf(path)
    else:
        raise ValueError(
            f"지원하지 않는 파일 형식입니다: {suffix} "
            f"(지원: .hwp, .pdf)"
        )
