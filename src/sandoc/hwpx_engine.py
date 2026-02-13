"""
sandoc.hwpx_engine — HWPX 출력 엔진 (스타일 미러링)

HWPX(ZIP 패키지) 문서를 직접 생성·편집하여,
원본 양식의 서식을 그대로 미러링한 사업계획서를 출력합니다.

주요 기능:
  - HWPX ZIP 구조 생성 (mimetype, META-INF, Contents/)
  - 스타일 프로파일 기반 서식 미러링
  - 섹션별 콘텐츠 삽입 (텍스트, 표, 이미지 placeholder)
  - 원본 HWPX 편집 (텍스트 찾기/바꾸기)
  - HWP → HWPX 변환 (pyhwp 위임)
  - hwpx-mcp-server 연동 (한컴오피스 호환 HWPX 출력)
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

# ── hwpx-mcp-server 가용성 확인 ──────────────────────────────────
_has_hwpx_mcp = False
try:
    from hwpx_mcp_server.hwpx_ops import HwpxOps as _HwpxOps  # noqa: F401

    _has_hwpx_mcp = True
except ImportError:
    _HwpxOps = None  # type: ignore[assignment,misc]

# ── HWPX 네임스페이스 ────────────────────────────────────────────
# HWPX(OWPML)에서 사용하는 XML 네임스페이스
HWPX_NS = {
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
    "hh": "http://www.hancom.co.kr/hwpml/2011/head",
    "ha": "http://www.hancom.co.kr/hwpml/2011/app",
    "config": "urn:oasis:names:tc:opendocument:xmlns:config:1.0",
    "odf": "urn:oasis:names:tc:opendocument:xmlns:container",
}

# HWPX 단위 변환
HWPUNIT_PER_MM = 283.46  # 7200 / 25.4
PT_TO_HWPUNIT = 100  # 폰트 크기: pt × 100


# ── 스타일 프로파일 로더 ──────────────────────────────────────────

class StyleMirror:
    """
    style-profile.json 에서 읽은 서식을 HWPX XML 속성으로 변환합니다.
    """

    def __init__(self, profile: dict[str, Any] | None = None):
        self.profile = profile or {}
        self._char_styles = self.profile.get("characterStyles", {})
        self._para_styles = self.profile.get("paragraphStyles", {})
        self._fonts = self.profile.get("fonts", [])
        self._margins = self.profile.get("margins", {})
        self._paper = self.profile.get("paperSize", {})

    @classmethod
    def from_file(cls, path: str | Path) -> StyleMirror:
        """JSON 파일에서 StyleMirror 생성."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"스타일 프로파일 파일 없음: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(data)

    @classmethod
    def default(cls) -> StyleMirror:
        """기본(fallback) 스타일 미러 생성."""
        return cls({
            "paperSize": {"type": "A4", "width": "210.0mm", "height": "297.0mm"},
            "margins": {
                "top": "10.0mm", "bottom": "15.0mm",
                "left": "20.0mm", "right": "20.0mm",
                "header": "15.0mm", "footer": "10.0mm",
                "gutter": "0.0mm",
            },
            "characterStyles": {
                "bodyText": {
                    "font": "맑은 고딕", "size": "10pt",
                    "bold": False, "italic": False,
                },
                "sectionTitle": {
                    "font": "HY헤드라인M", "size": "18pt",
                    "bold": False, "italic": True,
                },
                "tableHeader": {
                    "font": "맑은 고딕", "size": "10pt",
                    "bold": True, "italic": False,
                },
                "tableCell": {
                    "font": "맑은 고딕", "size": "9pt",
                    "bold": False, "italic": False,
                },
            },
            "paragraphStyles": {
                "default": {
                    "alignment": "justify",
                    "lineSpacing": 160,
                    "lineSpacingUnit": "percent",
                },
                "sectionTitle": {
                    "alignment": "distribute",
                    "lineSpacing": 160,
                },
            },
        })

    # ── 속성 접근 ─────────────────────────────────────────────

    def get_paper_width_mm(self) -> float:
        """용지 너비 (mm)."""
        raw = self._paper.get("width", "210.0mm")
        return float(str(raw).replace("mm", ""))

    def get_paper_height_mm(self) -> float:
        """용지 높이 (mm)."""
        raw = self._paper.get("height", "297.0mm")
        return float(str(raw).replace("mm", ""))

    def get_margin_mm(self, side: str) -> float:
        """여백 (mm). side: top/bottom/left/right/header/footer/gutter."""
        raw = self._margins.get(side, "0mm")
        return float(str(raw).replace("mm", ""))

    def get_char_style(self, style_name: str) -> dict[str, Any]:
        """문자 스타일 딕셔너리 반환."""
        return self._char_styles.get(style_name, self._char_styles.get("bodyText", {}))

    def get_para_style(self, style_name: str) -> dict[str, Any]:
        """문단 스타일 딕셔너리 반환."""
        return self._para_styles.get(style_name, self._para_styles.get("default", {}))

    def get_font_name(self, style_name: str) -> str:
        """스타일의 폰트 이름."""
        cs = self.get_char_style(style_name)
        font = cs.get("font", "맑은 고딕")
        # "HY헤드라인M / HY울릉도M" 같은 경우 첫 번째 사용
        if "/" in font:
            font = font.split("/")[0].strip()
        return font

    def get_font_size_pt(self, style_name: str) -> float:
        """스타일의 폰트 크기 (pt)."""
        cs = self.get_char_style(style_name)
        size_str = str(cs.get("size", "10pt"))
        # "14-16pt" 같은 경우 첫 번째 사용
        size_str = size_str.replace("pt", "").split("-")[0].strip()
        try:
            return float(size_str)
        except ValueError:
            return 10.0

    def get_line_spacing(self, style_name: str) -> int:
        """줄간격 (%)."""
        ps = self.get_para_style(style_name)
        return int(ps.get("lineSpacing", 160))

    def get_alignment(self, style_name: str) -> str:
        """정렬. justify/distribute/left/center/right."""
        ps = self.get_para_style(style_name)
        return ps.get("alignment", "justify")

    def get_font_list(self) -> list[str]:
        """프로파일에 정의된 모든 폰트 이름."""
        names = []
        for f in self._fonts:
            name = f.get("name", "")
            if name and name not in names:
                names.append(name)
        return names or ["맑은 고딕", "함초롬바탕", "함초롬돋움"]


# ── HWPX 문서 빌더 ──────────────────────────────────────────────

class HwpxBuilder:
    """
    HWPX 문서를 처음부터 조립합니다.

    HWPX ZIP 구조:
      mimetype
      META-INF/manifest.xml
      Contents/
        content.hpf        (패키지 descriptor)
        header.xml          (문서 헤더: 폰트, 스타일 정의)
        section0.xml        (본문 섹션)
    """

    def __init__(self, style: StyleMirror | None = None):
        self.style = style or StyleMirror.default()
        self._sections: list[dict[str, Any]] = []
        self._font_list: list[str] = self.style.get_font_list()

    def add_section(
        self,
        title: str,
        content: str,
        style_name: str = "bodyText",
        section_key: str = "",
    ) -> None:
        """
        섹션(콘텐츠 블록)을 추가합니다.

        Args:
            title: 섹션 제목
            content: 본문 텍스트 (markdown-like, ◦/- 불릿 지원)
            style_name: 본문에 적용할 스타일 이름
            section_key: 섹션 식별 키
        """
        self._sections.append({
            "title": title,
            "content": content,
            "style_name": style_name,
            "section_key": section_key,
        })

    def build(self, output_path: str | Path) -> Path:
        """
        HWPX 파일을 생성합니다.

        hwpx-mcp-server가 설치되어 있으면 이를 사용하여 한컴오피스 호환
        HWPX를 생성합니다. 미설치 시 기존 XML 직접 생성으로 폴백합니다.

        Args:
            output_path: 출력 HWPX 파일 경로

        Returns:
            생성된 파일 경로
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if _has_hwpx_mcp:
            return self._build_with_mcp(output_path)
        else:
            logger.warning(
                "hwpx-mcp-server가 설치되지 않았습니다. "
                "한컴오피스에서 열 수 없는 레거시 HWPX를 생성합니다. "
                "pip install hwpx-mcp-server 로 설치하세요."
            )
            return self._build_legacy(output_path)

    def _build_with_mcp(self, output_path: Path) -> Path:
        """hwpx-mcp-server (HwpxOps)를 이용한 한컴 호환 HWPX 빌드."""
        assert _HwpxOps is not None
        ops = _HwpxOps()

        out_str = str(output_path)

        # 1) 빈 문서 생성
        ops.make_blank(out_str)

        # 2) 섹션별 콘텐츠 삽입
        for section in self._sections:
            title = section["title"]
            content = section["content"]

            # 제목 (볼드, 큰 폰트)
            title_style: dict[str, Any] = {"bold": True}
            font_size = self.style.get_font_size_pt("sectionTitle")
            if font_size and font_size != 10.0:
                title_style["fontSize"] = font_size
            ops.add_paragraph(out_str, title, run_style=title_style)

            # 본문 줄 단위 파싱
            lines = content.split("\n") if content else []
            # 성능: 순수 텍스트 줄은 벌크 삽입
            bulk_buf: list[str] = []

            for line in lines:
                stripped = line.strip()

                if not stripped:
                    # 빈 줄
                    bulk_buf.append("")
                    continue

                # 표 행 (| 로 시작) — 그대로 텍스트로 유지
                if stripped.startswith("|"):
                    if set(stripped.replace("|", "").replace("-", "").strip()) <= {"", " "}:
                        continue  # 표 구분선 건너뛰기
                    bulk_buf.append(stripped)
                    continue

                # 일반 텍스트 (불릿 포함)
                bulk_buf.append(stripped)

            # 버퍼 플러시
            if bulk_buf:
                ops.insert_paragraphs_bulk(out_str, bulk_buf)

            # 섹션 간 빈 줄
            ops.add_paragraph(out_str, "")

        logger.info("HWPX 빌드 완료 (hwpx-mcp-server): %s (%d 섹션)", output_path, len(self._sections))
        return output_path

    def _build_legacy(self, output_path: Path) -> Path:
        """레거시: 직접 XML 생성 기반 HWPX 빌드 (한컴 비호환)."""
        with tempfile.TemporaryDirectory(prefix="sandoc_hwpx_build_") as tmp_dir:
            tmp = Path(tmp_dir)

            # 1) mimetype
            (tmp / "mimetype").write_text(
                "application/hwp+zip", encoding="utf-8"
            )

            # 2) META-INF/manifest.xml
            meta_dir = tmp / "META-INF"
            meta_dir.mkdir()
            self._write_manifest(meta_dir / "manifest.xml")

            # 3) Contents/
            contents_dir = tmp / "Contents"
            contents_dir.mkdir()

            # 3a) content.hpf
            self._write_content_hpf(contents_dir / "content.hpf")

            # 3b) header.xml (폰트, 문자모양, 문단모양 정의)
            self._write_header(contents_dir / "header.xml")

            # 3c) section0.xml (본문)
            self._write_section(contents_dir / "section0.xml")

            # 4) ZIP 패키징 (mimetype은 비압축)
            with zipfile.ZipFile(output_path, "w") as zf:
                # mimetype MUST be first and uncompressed
                zf.write(
                    tmp / "mimetype", "mimetype",
                    compress_type=zipfile.ZIP_STORED,
                )
                # 나머지 파일
                for fpath in sorted(tmp.rglob("*")):
                    if fpath.is_file() and fpath.name != "mimetype":
                        arcname = str(fpath.relative_to(tmp))
                        zf.write(fpath, arcname, compress_type=zipfile.ZIP_DEFLATED)

        logger.info("HWPX 빌드 완료 (레거시): %s (%d 섹션)", output_path, len(self._sections))
        return output_path

    # ── XML 생성 내부 메서드 ──────────────────────────────────

    def _write_manifest(self, path: Path) -> None:
        """META-INF/manifest.xml 생성."""
        root = ET.Element("manifest")
        root.set("xmlns", "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0")

        entries = [
            ("/", "application/hwp+zip"),
            ("Contents/content.hpf", "application/xml"),
            ("Contents/header.xml", "application/xml"),
            ("Contents/section0.xml", "application/xml"),
        ]
        for full_path, media_type in entries:
            entry = ET.SubElement(root, "file-entry")
            entry.set("full-path", full_path)
            entry.set("media-type", media_type)

        self._write_xml(root, path)

    def _write_content_hpf(self, path: Path) -> None:
        """Contents/content.hpf — 패키지 디스크립터."""
        root = ET.Element("ha:HWPDocumentPackage")
        root.set("xmlns:ha", HWPX_NS["ha"])
        root.set("version", "1.0")

        # FileHeader
        fh = ET.SubElement(root, "ha:FileHeader")
        fh.set("Version", "1.0.0.0")

        # BodyText 참조
        body = ET.SubElement(root, "ha:BodyText")
        body.set("Count", "1")
        sec_ref = ET.SubElement(body, "ha:SectionRef")
        sec_ref.set("Href", "section0.xml")

        # Head 참조
        head = ET.SubElement(root, "ha:Head")
        head_ref = ET.SubElement(head, "ha:HeadRef")
        head_ref.set("Href", "header.xml")

        self._write_xml(root, path)

    def _write_header(self, path: Path) -> None:
        """Contents/header.xml — 폰트·문자모양·문단모양 정의."""
        root = ET.Element("hh:Head")
        root.set("xmlns:hh", HWPX_NS["hh"])
        root.set("xmlns:hc", HWPX_NS["hc"])

        # 1) 폰트 리스트
        font_list = ET.SubElement(root, "hh:FontFaces")
        for i, font_name in enumerate(self._font_list):
            for script_type in ["한글", "영문", "한자", "일본어", "기타", "기호", "사용자"]:
                face = ET.SubElement(font_list, "hh:FontFace")
                face.set("Id", str(i))
                face.set("Type", script_type)
                face.set("Name", font_name)

        # 2) 문자 모양
        char_shapes = ET.SubElement(root, "hh:CharShapes")
        style_entries = [
            ("bodyText", 0),
            ("sectionTitle", 1),
            ("tableHeader", 2),
            ("tableCell", 3),
        ]
        for style_name, cs_id in style_entries:
            cs = ET.SubElement(char_shapes, "hh:CharShape")
            cs.set("Id", str(cs_id))

            font_size = self.style.get_font_size_pt(style_name)
            cs.set("Height", str(int(font_size * PT_TO_HWPUNIT)))

            char_style = self.style.get_char_style(style_name)
            if char_style.get("bold"):
                cs.set("Bold", "true")
            if char_style.get("italic"):
                cs.set("Italic", "true")
            if char_style.get("underline"):
                cs.set("Underline", "true")

            # 색상
            color = char_style.get("color", "rgb(0,0,0)")
            if color and "rgb" in str(color):
                cs.set("TextColor", _parse_rgb_to_hex(str(color)))

            # 폰트 참조
            font_name = self.style.get_font_name(style_name)
            font_idx = 0
            if font_name in self._font_list:
                font_idx = self._font_list.index(font_name)
            for script_type in ["한글", "영문", "한자", "일본어", "기타", "기호", "사용자"]:
                font_ref = ET.SubElement(cs, "hh:FontRef")
                font_ref.set("Type", script_type)
                font_ref.set("Id", str(font_idx))

        # 3) 문단 모양
        para_shapes = ET.SubElement(root, "hh:ParaShapes")
        para_entries = [
            ("default", 0),
            ("sectionTitle", 1),
        ]
        for para_name, ps_id in para_entries:
            ps = ET.SubElement(para_shapes, "hh:ParaShape")
            ps.set("Id", str(ps_id))

            alignment = self.style.get_alignment(para_name)
            align_map = {
                "justify": "Justify",
                "distribute": "Distribute",
                "left": "Left",
                "center": "Center",
                "right": "Right",
            }
            ps.set("Align", align_map.get(alignment, "Justify"))

            line_spacing = self.style.get_line_spacing(para_name)
            ps.set("LineSpacing", str(line_spacing))
            ps.set("LineSpacingType", "Percent")

        self._write_xml(root, path)

    def _write_section(self, path: Path) -> None:
        """Contents/section0.xml — 본문 콘텐츠."""
        root = ET.Element("hs:Section")
        root.set("xmlns:hs", HWPX_NS["hs"])
        root.set("xmlns:hp", HWPX_NS["hp"])
        root.set("xmlns:hc", HWPX_NS["hc"])

        # 페이지 정의
        page_def = ET.SubElement(root, "hs:PageDef")
        w_mm = self.style.get_paper_width_mm()
        h_mm = self.style.get_paper_height_mm()
        page_def.set("Width", str(int(w_mm * HWPUNIT_PER_MM)))
        page_def.set("Height", str(int(h_mm * HWPUNIT_PER_MM)))

        margin = ET.SubElement(page_def, "hs:Margin")
        for side in ["Top", "Bottom", "Left", "Right", "Header", "Footer", "Gutter"]:
            val = self.style.get_margin_mm(side.lower())
            margin.set(side, str(int(val * HWPUNIT_PER_MM)))

        # 섹션별 콘텐츠 삽입
        for sec in self._sections:
            self._add_content_paragraphs(root, sec)

        self._write_xml(root, path)

    def _add_content_paragraphs(
        self, parent: ET.Element, section: dict[str, Any]
    ) -> None:
        """섹션의 제목 + 본문을 HWPX 문단으로 변환."""
        title = section["title"]
        content = section["content"]

        # 제목 문단
        self._add_paragraph(
            parent, title,
            char_shape_id=1,  # sectionTitle
            para_shape_id=1,
        )

        # 본문 줄 단위 파싱
        for line in content.split("\n"):
            stripped = line.strip()
            if not stripped:
                # 빈 줄 → 빈 문단
                self._add_paragraph(parent, "", char_shape_id=0, para_shape_id=0)
                continue

            # 표 행 (| 로 시작)
            if stripped.startswith("|"):
                # 표 구분선 건너뛰기
                if set(stripped.replace("|", "").replace("-", "").strip()) <= {"", " "}:
                    continue
                # 표 셀을 텍스트로 유지 (단순화)
                self._add_paragraph(parent, stripped, char_shape_id=0, para_shape_id=0)
                continue

            # 불릿(◦, -, □) 텍스트
            self._add_paragraph(parent, stripped, char_shape_id=0, para_shape_id=0)

    def _add_paragraph(
        self,
        parent: ET.Element,
        text: str,
        char_shape_id: int = 0,
        para_shape_id: int = 0,
    ) -> ET.Element:
        """HWPX 문단 요소 생성."""
        para = ET.SubElement(parent, "hp:Paragraph")
        para.set("ParaShapeId", str(para_shape_id))

        if text:
            run = ET.SubElement(para, "hp:Run")
            run.set("CharShapeId", str(char_shape_id))
            t_elem = ET.SubElement(run, "hp:T")
            t_elem.text = text

        return para

    @staticmethod
    def _write_xml(root: ET.Element, path: Path) -> None:
        """XML 파일 저장 (UTF-8, 선언 포함)."""
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        with open(path, "wb") as f:
            tree.write(f, encoding="utf-8", xml_declaration=True)


# ── HWPX 텍스트 편집 ─────────────────────────────────────────────

def edit_hwpx_text(
    hwpx_path: str | Path,
    replacements: dict[str, str],
    output_path: str | Path | None = None,
) -> Path:
    """
    HWPX 파일 내 XML에서 텍스트를 찾아 바꿉니다.

    HWPX는 ZIP 패키지이므로, 압축 해제 → XML 수정 → 재압축 합니다.

    Args:
        hwpx_path: 입력 HWPX 파일 경로
        replacements: {찾을 텍스트: 바꿀 텍스트} 딕셔너리
        output_path: 출력 HWPX 파일 경로 (기본: 원본 덮어쓰기)

    Returns:
        수정된 HWPX 파일 경로

    Raises:
        FileNotFoundError: HWPX 파일이 없는 경우
        ValueError: 유효한 HWPX 파일이 아닌 경우
    """
    hwpx_path = Path(hwpx_path)
    if not hwpx_path.exists():
        raise FileNotFoundError(f"HWPX 파일을 찾을 수 없습니다: {hwpx_path}")

    if output_path is None:
        output_path = hwpx_path
    else:
        output_path = Path(output_path)

    # 임시 디렉토리에 압축 해제
    with tempfile.TemporaryDirectory(prefix="sandoc_hwpx_") as tmp_dir:
        tmp_path = Path(tmp_dir)

        # ZIP 압축 해제
        try:
            with zipfile.ZipFile(hwpx_path, "r") as zf:
                zf.extractall(tmp_path)
        except zipfile.BadZipFile:
            raise ValueError(f"유효한 HWPX(ZIP) 파일이 아닙니다: {hwpx_path}")

        # XML 파일에서 텍스트 찾기/바꾸기
        replaced_count = 0
        for xml_file in tmp_path.rglob("*.xml"):
            try:
                content = xml_file.read_text(encoding="utf-8")
                modified = False
                for old_text, new_text in replacements.items():
                    if old_text in content:
                        content = content.replace(old_text, new_text)
                        modified = True
                        replaced_count += 1

                if modified:
                    xml_file.write_text(content, encoding="utf-8")
            except (UnicodeDecodeError, PermissionError) as e:
                logger.warning("XML 파일 처리 중 오류: %s — %s", xml_file, e)
                continue

        # 재압축
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in tmp_path.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(tmp_path)
                    zf.write(file_path, arcname)

    logger.info("HWPX 텍스트 편집 완료: %d건 교체 → %s", replaced_count, output_path)
    return output_path


# ── HWPX 검증 ─────────────────────────────────────────────────────

def validate_hwpx(hwpx_path: str | Path) -> dict[str, Any]:
    """
    HWPX 파일의 구조를 검증합니다.

    Args:
        hwpx_path: 검증할 HWPX 파일 경로

    Returns:
        검증 결과 딕셔너리:
          - valid: bool
          - has_mimetype: bool
          - has_manifest: bool
          - has_content_hpf: bool
          - has_header: bool
          - has_sections: bool
          - section_count: int
          - file_count: int
          - errors: list[str]
    """
    hwpx_path = Path(hwpx_path)
    result: dict[str, Any] = {
        "valid": False,
        "has_mimetype": False,
        "has_manifest": False,
        "has_content_hpf": False,
        "has_header": False,
        "has_sections": False,
        "section_count": 0,
        "file_count": 0,
        "errors": [],
    }

    if not hwpx_path.exists():
        result["errors"].append(f"파일 없음: {hwpx_path}")
        return result

    try:
        with zipfile.ZipFile(hwpx_path, "r") as zf:
            names = zf.namelist()
            result["file_count"] = len(names)

            result["has_mimetype"] = "mimetype" in names
            result["has_manifest"] = "META-INF/manifest.xml" in names
            result["has_content_hpf"] = "Contents/content.hpf" in names
            result["has_header"] = "Contents/header.xml" in names

            # 섹션 파일 확인
            section_files = [n for n in names if n.startswith("Contents/section") and n.endswith(".xml")]
            result["has_sections"] = len(section_files) > 0
            result["section_count"] = len(section_files)

            # mimetype 내용 확인
            if result["has_mimetype"]:
                mt = zf.read("mimetype").decode("utf-8", errors="replace").strip()
                if mt != "application/hwp+zip":
                    result["errors"].append(f"잘못된 mimetype: {mt}")

            # 필수 파일 확인
            if not result["has_mimetype"]:
                result["errors"].append("mimetype 파일 없음")
            if not result["has_content_hpf"]:
                result["errors"].append("Contents/content.hpf 없음")
            if not result["has_sections"]:
                result["errors"].append("섹션 파일 없음")

            result["valid"] = (
                result["has_mimetype"]
                and result["has_content_hpf"]
                and result["has_sections"]
                and len(result["errors"]) == 0
            )

    except zipfile.BadZipFile:
        result["errors"].append("유효한 ZIP 파일이 아닙니다")
    except Exception as e:
        result["errors"].append(f"검증 오류: {e}")

    return result


# ── HWP → HWPX 변환 ──────────────────────────────────────────────

def hwp_to_hwpx(
    hwp_path: str | Path,
    output_path: str | Path | None = None,
) -> Path:
    """
    HWP 파일을 HWPX(ODF-like XML 패키지)로 변환합니다.

    hwpx-mcp-server가 설치되어 있으면 이를 우선 사용하고,
    없으면 pyhwp의 hwp5html 도구에 위임합니다.

    Args:
        hwp_path: 입력 HWP 파일 경로
        output_path: 출력 HWPX 파일 경로 (기본: 같은 위치에 .hwpx 확장자)

    Returns:
        생성된 HWPX 파일 경로

    Raises:
        FileNotFoundError: HWP 파일이 없는 경우
        RuntimeError: 변환 실패 시
    """
    hwp_path = Path(hwp_path)
    if not hwp_path.exists():
        raise FileNotFoundError(f"HWP 파일을 찾을 수 없습니다: {hwp_path}")

    if output_path is None:
        output_path = hwp_path.with_suffix(".hwpx")
    else:
        output_path = Path(output_path)

    # 1) hwpx-mcp-server 사용 시도
    if _has_hwpx_mcp:
        try:
            assert _HwpxOps is not None
            ops = _HwpxOps()
            result = ops.convert_hwp_to_hwpx(str(hwp_path), str(output_path))
            logger.info("HWP → HWPX 변환 완료 (hwpx-mcp-server): %s → %s", hwp_path, output_path)
            return output_path
        except Exception as e:
            logger.warning("hwpx-mcp-server 변환 실패, pyhwp 폴백 시도: %s", e)

    # 2) pyhwp의 hwp5html 폴백
    try:
        result = subprocess.run(
            ["hwp5html", "--output", str(output_path), str(hwp_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"hwp5html 변환 실패 (exit code {result.returncode}): "
                f"{result.stderr}"
            )
        logger.info("HWP → HWPX 변환 완료 (pyhwp): %s → %s", hwp_path, output_path)
        return output_path

    except FileNotFoundError:
        raise RuntimeError(
            "HWP → HWPX 변환 도구를 찾을 수 없습니다. "
            "pip install hwpx-mcp-server 또는 pip install pyhwp 로 설치하세요."
        )


# ── HWPX-MCP 서버 연동 ────────────────────────────────────────────

class HwpxMcpClient:
    """
    hwpx-mcp-server 로컬 Python API를 이용한 HWPX 생성/편집 클라이언트.

    hwpx-mcp-server가 설치되어 있으면 HwpxOps를 직접 사용합니다.
    """

    def __init__(self, server_url: str = "http://localhost:3000"):
        self.server_url = server_url
        self._connected = False
        self._ops = _HwpxOps() if _has_hwpx_mcp else None

    @property
    def available(self) -> bool:
        """hwpx-mcp-server를 사용할 수 있는지 여부."""
        return self._ops is not None

    def connect(self) -> bool:
        """MCP 서버 연결 (로컬 API 사용 시 항상 True)."""
        if self._ops is not None:
            self._connected = True
            return True
        logger.warning("hwpx-mcp-server가 설치되지 않았습니다.")
        return False

    def create_document(self, output_path: str) -> dict[str, Any]:
        """새 빈 HWPX 문서를 생성합니다."""
        if self._ops is None:
            raise RuntimeError("hwpx-mcp-server가 설치되지 않았습니다.")
        return self._ops.make_blank(output_path)

    def add_paragraph(
        self,
        path: str,
        text: str,
        run_style: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """문서에 문단을 추가합니다."""
        if self._ops is None:
            raise RuntimeError("hwpx-mcp-server가 설치되지 않았습니다.")
        kwargs: dict[str, Any] = {}
        if run_style:
            kwargs["run_style"] = run_style
        return self._ops.add_paragraph(path, text, **kwargs)

    def insert_paragraphs_bulk(
        self,
        path: str,
        paragraphs: list[str],
        run_style: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """문서에 여러 문단을 일괄 추가합니다."""
        if self._ops is None:
            raise RuntimeError("hwpx-mcp-server가 설치되지 않았습니다.")
        kwargs: dict[str, Any] = {}
        if run_style:
            kwargs["run_style"] = run_style
        return self._ops.insert_paragraphs_bulk(path, paragraphs, **kwargs)

    def add_table(
        self,
        path: str,
        rows: int,
        cols: int,
    ) -> dict[str, Any]:
        """문서에 표를 삽입합니다."""
        if self._ops is None:
            raise RuntimeError("hwpx-mcp-server가 설치되지 않았습니다.")
        return self._ops.add_table(path, rows, cols)

    def fill_template(
        self,
        source: str,
        output: str,
        replacements: dict[str, str],
    ) -> dict[str, Any]:
        """템플릿에서 플레이스홀더를 치환합니다."""
        if self._ops is None:
            raise RuntimeError("hwpx-mcp-server가 설치되지 않았습니다.")
        return self._ops.fill_template(source, output, replacements)

    def convert_hwp_to_hwpx(
        self,
        source: str,
        output: str | None = None,
    ) -> dict[str, Any]:
        """HWP 파일을 HWPX로 변환합니다."""
        if self._ops is None:
            raise RuntimeError("hwpx-mcp-server가 설치되지 않았습니다.")
        return self._ops.convert_hwp_to_hwpx(source, output)

    def validate(self, path: str) -> dict[str, Any]:
        """HWPX 파일 구조를 검증합니다."""
        if self._ops is None:
            raise RuntimeError("hwpx-mcp-server가 설치되지 않았습니다.")
        return self._ops.validate_structure(path)


# ── 유틸리티 ─────────────────────────────────────────────────────

def _parse_rgb_to_hex(rgb_str: str) -> str:
    """'rgb(0,0,255)' → '#0000FF'."""
    import re
    match = re.search(r"rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", rgb_str)
    if match:
        r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return f"#{r:02X}{g:02X}{b:02X}"
    return "#000000"
