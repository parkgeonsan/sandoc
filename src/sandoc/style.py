"""
sandoc.style — 스타일 프로파일 추출 및 관리

HWP 파일에서 폰트, 여백, 문단 스타일을 추출하여
재사용 가능한 StyleProfile 로 관리합니다.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from sandoc.parser import parse_hwp, HwpParseResult

logger = logging.getLogger(__name__)


# ── 데이터 클래스 ─────────────────────────────────────────────────

@dataclass
class FontSpec:
    """폰트 사양."""
    name: str
    size_pt: float = 10.0
    bold: bool = False
    italic: bool = False


@dataclass
class MarginSpec:
    """여백 사양 (mm 단위)."""
    top: float = 10.0
    bottom: float = 15.0
    left: float = 20.0
    right: float = 20.0
    header: float = 15.0
    footer: float = 10.0
    gutter: float = 0.0


@dataclass
class SectionSpec:
    """섹션(페이지) 사양."""
    paper_width_mm: float = 210.0
    paper_height_mm: float = 297.0
    margins: MarginSpec = field(default_factory=MarginSpec)


@dataclass
class StyleProfile:
    """
    문서 스타일 프로파일.

    HWP 파일에서 추출한 폰트, 여백, 섹션 정보를 담고 있으며
    JSON 으로 저장/로드할 수 있습니다.
    """
    name: str = ""
    source_file: str = ""
    fonts: list[FontSpec] = field(default_factory=list)
    primary_font: FontSpec = field(default_factory=lambda: FontSpec(name="함초롬바탕"))
    heading_font: FontSpec = field(default_factory=lambda: FontSpec(name="함초롬돋움", size_pt=14.0, bold=True))
    body_font: FontSpec = field(default_factory=lambda: FontSpec(name="함초롬바탕", size_pt=10.0))
    sections: list[SectionSpec] = field(default_factory=list)
    styles: list[dict[str, Any]] = field(default_factory=list)
    char_shapes_count: int = 0
    font_names: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """JSON 문자열로 변환."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# ── 스타일 추출 ───────────────────────────────────────────────────

def extract_style_profile(hwp_path: str | Path) -> StyleProfile:
    """
    HWP 파일에서 스타일 프로파일을 추출합니다.

    Args:
        hwp_path: HWP 파일 경로

    Returns:
        StyleProfile: 추출된 스타일 프로파일
    """
    hwp_path = Path(hwp_path)
    parsed = parse_hwp(hwp_path)

    profile = StyleProfile(
        name=hwp_path.stem,
        source_file=str(hwp_path),
    )

    # 폰트 정보 수집
    profile.font_names = [f.name for f in parsed.fonts if f.name]
    for font_info in parsed.fonts:
        if font_info.name:
            profile.fonts.append(FontSpec(name=font_info.name))

    # 문자 모양에서 대표 폰트/크기 추출
    if parsed.char_shapes:
        profile.char_shapes_count = len(parsed.char_shapes)

        # 가장 많이 사용된 폰트 크기 → 본문 폰트
        size_counts: dict[float, int] = {}
        for cs in parsed.char_shapes:
            size = cs.font_size_pt
            size_counts[size] = size_counts.get(size, 0) + 1

        if size_counts:
            # 가장 빈번한 크기 = 본문
            body_size = max(size_counts, key=size_counts.get)  # type: ignore[arg-type]
            # 가장 큰 크기 = 제목
            heading_size = max(size_counts.keys())

            # 본문 폰트 설정
            body_cs = next(
                (cs for cs in parsed.char_shapes if cs.font_size_pt == body_size),
                None,
            )
            if body_cs and body_cs.font_ids and profile.font_names:
                font_idx = body_cs.font_ids[0]  # 한글 스크립트
                if font_idx < len(profile.font_names):
                    profile.body_font = FontSpec(
                        name=profile.font_names[font_idx],
                        size_pt=body_size,
                        bold=body_cs.bold,
                    )
                    profile.primary_font = profile.body_font

            # 제목 폰트 설정
            if heading_size != body_size:
                heading_cs = next(
                    (cs for cs in parsed.char_shapes if cs.font_size_pt == heading_size),
                    None,
                )
                if heading_cs and heading_cs.font_ids and profile.font_names:
                    font_idx = heading_cs.font_ids[0]
                    if font_idx < len(profile.font_names):
                        profile.heading_font = FontSpec(
                            name=profile.font_names[font_idx],
                            size_pt=heading_size,
                            bold=heading_cs.bold or True,
                        )

    # 페이지 레이아웃 → 섹션
    layout = parsed.page_layout
    section = SectionSpec(
        paper_width_mm=layout.paper_width_mm,
        paper_height_mm=layout.paper_height_mm,
        margins=MarginSpec(
            top=layout.margin_top_mm,
            bottom=layout.margin_bottom_mm,
            left=layout.margin_left_mm,
            right=layout.margin_right_mm,
            header=layout.margin_header_mm,
            footer=layout.margin_footer_mm,
            gutter=layout.margin_gutter_mm,
        ),
    )
    profile.sections.append(section)

    # 스타일 정보
    profile.styles = parsed.styles

    logger.info(
        "스타일 프로파일 추출 완료: %s (폰트 %d개, 문자모양 %d개)",
        profile.name, len(profile.font_names), profile.char_shapes_count,
    )

    return profile


# ── 저장/로드 ─────────────────────────────────────────────────────

def save_style_profile(profile: StyleProfile, output_path: str | Path) -> Path:
    """
    스타일 프로파일을 JSON 파일로 저장합니다.

    Args:
        profile: 저장할 스타일 프로파일
        output_path: 저장 경로 (.json)

    Returns:
        저장된 파일 경로
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(profile.to_json(), encoding="utf-8")
    logger.info("스타일 프로파일 저장: %s", output_path)
    return output_path


def load_style_profile(path: str | Path) -> StyleProfile:
    """
    JSON 파일에서 스타일 프로파일을 로드합니다.

    Args:
        path: JSON 파일 경로

    Returns:
        StyleProfile: 로드된 스타일 프로파일
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"스타일 프로파일 파일을 찾을 수 없습니다: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    # FontSpec 복원
    fonts = [FontSpec(**f) for f in data.get("fonts", [])]
    primary_font = FontSpec(**data["primary_font"]) if "primary_font" in data else FontSpec(name="함초롬바탕")
    heading_font = FontSpec(**data["heading_font"]) if "heading_font" in data else FontSpec(name="함초롬돋움")
    body_font = FontSpec(**data["body_font"]) if "body_font" in data else FontSpec(name="함초롬바탕")

    # SectionSpec 복원
    sections = []
    for s in data.get("sections", []):
        margins_data = s.get("margins", {})
        margins = MarginSpec(**margins_data) if margins_data else MarginSpec()
        sections.append(SectionSpec(
            paper_width_mm=s.get("paper_width_mm", 210.0),
            paper_height_mm=s.get("paper_height_mm", 297.0),
            margins=margins,
        ))

    return StyleProfile(
        name=data.get("name", ""),
        source_file=data.get("source_file", ""),
        fonts=fonts,
        primary_font=primary_font,
        heading_font=heading_font,
        body_font=body_font,
        sections=sections,
        styles=data.get("styles", []),
        char_shapes_count=data.get("char_shapes_count", 0),
        font_names=data.get("font_names", []),
    )
