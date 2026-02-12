"""
sandoc.visualize -- 사업계획서 시각화 자료 생성

프로젝트의 초안 섹션에서 데이터를 분석하여:
  - 매출 추이 바 차트 (bar chart)
  - 사업비 구성 파이 차트 (pie chart)
  - TAM/SAM/SOM 퍼널 차트 (funnel)
  - 팀 조직도 (org chart)
  - 사업 로드맵 타임라인

SVG 문자열을 직접 생성합니다 (외부 의존성 없음).
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── 차트 설정 상수 ─────────────────────────────────────────────

CHART_COLORS = [
    "#2563EB",  # blue
    "#059669",  # green
    "#D97706",  # amber
    "#DC2626",  # red
    "#7C3AED",  # purple
    "#0891B2",  # cyan
    "#EA580C",  # orange
    "#4F46E5",  # indigo
]

PIE_COLORS = ["#2563EB", "#059669", "#D97706", "#DC2626", "#7C3AED"]

FONT_FAMILY = "'Pretendard', 'Malgun Gothic', sans-serif"


# ── 데이터 추출 ──────────────────────────────────────────────

def _extract_numbers(text: str) -> list[int]:
    """텍스트에서 금액(숫자) 추출. 쉼표 포함 숫자 및 '억원' 단위 처리."""
    amounts = []
    # "4.5억원" 패턴
    for m in re.finditer(r"(\d+(?:\.\d+)?)억원?", text):
        amounts.append(int(float(m.group(1)) * 100_000_000))
    # "50,000,000" 패턴
    for m in re.finditer(r"(\d{1,3}(?:,\d{3})+)원?", text):
        val = int(m.group(1).replace(",", ""))
        if val >= 1_000_000:  # 100만원 이상만
            amounts.append(val)
    return amounts


def _extract_revenue_data(sections: dict[str, str]) -> list[dict[str, Any]]:
    """섹션에서 매출 추이 데이터 추출."""
    revenues: list[dict[str, Any]] = []

    # growth_strategy, market_analysis, financial_plan 에서 매출 관련 데이터 탐색
    for key in ["market_analysis", "growth_strategy", "financial_plan",
                "business_model", "funding_plan"]:
        text = sections.get(key, "")
        # "2023년" ~ "2027년" 패턴의 연도별 매출
        for m in re.finditer(r"(20\d{2})(?:년)?[^0-9]*?(\d+(?:\.\d+)?)억", text):
            revenues.append({
                "year": m.group(1),
                "amount": float(m.group(2)),
                "unit": "억원",
            })

    # 중복 연도 제거 (첫 번째 값 사용)
    seen = set()
    unique: list[dict[str, Any]] = []
    for r in revenues:
        if r["year"] not in seen:
            seen.add(r["year"])
            unique.append(r)
    return sorted(unique, key=lambda x: x["year"])


def _extract_budget_data(sections: dict[str, str]) -> dict[str, int]:
    """섹션에서 사업비 구성 데이터 추출."""
    budget: dict[str, int] = {}

    for key in ["growth_strategy", "funding_plan", "financial_plan",
                "company_overview"]:
        text = sections.get(key, "")

        # 정부지원금/정부지원사업비
        m = re.search(r"정부지원(?:금|사업비)[^0-9]*?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?억)", text)
        if m and "정부지원" not in budget:
            val = m.group(1)
            if "억" in val:
                budget["정부지원"] = int(float(val.replace("억", "")) * 100_000_000)
            else:
                budget["정부지원"] = int(val.replace(",", ""))

        # 자기부담(현금)
        m = re.search(r"자기부담\(현금\)[^0-9]*?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?억)", text)
        if m and "현금" not in budget:
            val = m.group(1)
            if "억" in val:
                budget["현금"] = int(float(val.replace("억", "")) * 100_000_000)
            else:
                budget["현금"] = int(val.replace(",", ""))

        # 자기부담(현물)
        m = re.search(r"자기부담\(현물\)[^0-9]*?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?억)", text)
        if m and "현물" not in budget:
            val = m.group(1)
            if "억" in val:
                budget["현물"] = int(float(val.replace("억", "")) * 100_000_000)
            else:
                budget["현물"] = int(val.replace(",", ""))

    return budget


def _extract_market_data(sections: dict[str, str]) -> dict[str, float]:
    """TAM/SAM/SOM 데이터 추출."""
    market: dict[str, float] = {}

    for key in ["solution", "market_analysis", "problem_recognition"]:
        text = sections.get(key, "")

        # TAM
        m = re.search(r"(?:TAM|전체\s*시장|총\s*시장)[^0-9]*?(\d+(?:\.\d+)?)\s*(?:조|억)", text, re.I)
        if m and "TAM" not in market:
            unit_m = re.search(r"조|억", text[m.start():m.end() + 10])
            val = float(m.group(1))
            market["TAM"] = val * 10000 if unit_m and unit_m.group() == "조" else val

        # SAM
        m = re.search(r"(?:SAM|유효\s*시장|서비스\s*가능\s*시장)[^0-9]*?(\d+(?:\.\d+)?)\s*(?:조|억)", text, re.I)
        if m and "SAM" not in market:
            unit_m = re.search(r"조|억", text[m.start():m.end() + 10])
            val = float(m.group(1))
            market["SAM"] = val * 10000 if unit_m and unit_m.group() == "조" else val

        # SOM
        m = re.search(r"(?:SOM|수익\s*시장|목표\s*시장\s*규모|실제\s*목표)[^0-9]*?(\d+(?:\.\d+)?)\s*(?:조|억)", text, re.I)
        if m and "SOM" not in market:
            unit_m = re.search(r"조|억", text[m.start():m.end() + 10])
            val = float(m.group(1))
            market["SOM"] = val * 10000 if unit_m and unit_m.group() == "조" else val

    return market


def _extract_team_data(sections: dict[str, str]) -> list[dict[str, str]]:
    """팀 정보 추출."""
    team: list[dict[str, str]] = []
    text = sections.get("team", "")

    # 표에서 추출: | 기고용 | 1 | CTO | AI/ML |
    for m in re.finditer(
        r"\|\s*(기고용|채용예정)\s*\|\s*\d+\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]*)\s*\|",
        text,
    ):
        team.append({
            "position": m.group(2).strip(),
            "role": m.group(3).strip(),
            "type": m.group(1).strip(),
        })

    # 대표자 정보
    m_ceo = re.search(r"(\S+)\s*대표", text)
    if m_ceo:
        team.insert(0, {
            "position": "대표이사",
            "role": "경영총괄",
            "type": "대표",
        })

    return team


def _extract_milestones(sections: dict[str, str]) -> list[dict[str, str]]:
    """로드맵/마일스톤 데이터 추출."""
    milestones: list[dict[str, str]] = []
    text = sections.get("market_analysis", "") + sections.get("growth_strategy", "")

    # 표에서 추출: | 1 | AI 모델 개발 | 2025.06~08 | 세부내용 |
    for m in re.finditer(
        r"\|\s*\d+\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]*)\s*\|",
        text,
    ):
        task = m.group(1).strip()
        period = m.group(2).strip()
        detail = m.group(3).strip()
        if "순번" in task or "---" in task:
            continue
        milestones.append({
            "task": task,
            "period": period,
            "detail": detail,
        })

    return milestones


# ── SVG 차트 생성기 ──────────────────────────────────────────

def generate_bar_chart_svg(
    data: list[dict[str, Any]],
    title: str = "매출 추이",
    width: int = 600,
    height: int = 400,
) -> str:
    """바 차트 SVG 생성."""
    if not data:
        return ""

    margin = {"top": 60, "right": 40, "bottom": 60, "left": 80}
    chart_w = width - margin["left"] - margin["right"]
    chart_h = height - margin["top"] - margin["bottom"]

    values = [d["amount"] for d in data]
    max_val = max(values) if values else 1
    # 깔끔한 최대값 계산
    magnitude = 10 ** (len(str(int(max_val))) - 1)
    nice_max = math.ceil(max_val / magnitude) * magnitude

    bar_count = len(data)
    bar_gap = chart_w * 0.15 / max(bar_count, 1)
    bar_width = (chart_w - bar_gap * (bar_count + 1)) / max(bar_count, 1)
    bar_width = min(bar_width, 80)  # 최대 바 너비

    # 그리드 라인 (5등분)
    grid_lines = ""
    for i in range(6):
        y = margin["top"] + chart_h - (chart_h * i / 5)
        val = nice_max * i / 5
        grid_lines += (
            f'  <line x1="{margin["left"]}" y1="{y}" '
            f'x2="{width - margin["right"]}" y2="{y}" '
            f'stroke="#E5E7EB" stroke-dasharray="4,4"/>\n'
            f'  <text x="{margin["left"] - 10}" y="{y + 4}" '
            f'text-anchor="end" fill="#6B7280" font-size="11" '
            f'font-family="{FONT_FAMILY}">{val:.0f}</text>\n'
        )

    # 바 렌더링
    bars = ""
    total_bars_width = bar_width * bar_count + bar_gap * (bar_count - 1)
    start_x = margin["left"] + (chart_w - total_bars_width) / 2

    for i, d in enumerate(data):
        x = start_x + i * (bar_width + bar_gap)
        bar_h = (d["amount"] / nice_max) * chart_h if nice_max > 0 else 0
        y = margin["top"] + chart_h - bar_h
        color = CHART_COLORS[i % len(CHART_COLORS)]

        bars += (
            f'  <rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" '
            f'height="{bar_h:.1f}" fill="{color}" rx="4" ry="4">\n'
            f'    <animate attributeName="height" from="0" to="{bar_h:.1f}" dur="0.6s" fill="freeze"/>\n'
            f'    <animate attributeName="y" from="{margin["top"] + chart_h}" to="{y:.1f}" dur="0.6s" fill="freeze"/>\n'
            f'  </rect>\n'
            f'  <text x="{x + bar_width / 2:.1f}" y="{y - 8:.1f}" '
            f'text-anchor="middle" fill="#374151" font-size="12" '
            f'font-weight="bold" font-family="{FONT_FAMILY}">'
            f'{d["amount"]:.1f}{d.get("unit", "")}</text>\n'
            f'  <text x="{x + bar_width / 2:.1f}" y="{margin["top"] + chart_h + 20:.1f}" '
            f'text-anchor="middle" fill="#4B5563" font-size="12" '
            f'font-family="{FONT_FAMILY}">{d["year"]}</text>\n'
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">\n'
        f'  <rect width="{width}" height="{height}" fill="white" rx="8"/>\n'
        f'  <text x="{width / 2}" y="30" text-anchor="middle" '
        f'font-size="16" font-weight="bold" fill="#111827" '
        f'font-family="{FONT_FAMILY}">{title}</text>\n'
        f'  <text x="{width / 2}" y="48" text-anchor="middle" '
        f'font-size="11" fill="#9CA3AF" '
        f'font-family="{FONT_FAMILY}">(단위: 억원)</text>\n'
        f'{grid_lines}'
        f'{bars}'
        f'</svg>'
    )
    return svg


def generate_pie_chart_svg(
    data: dict[str, int],
    title: str = "사업비 구성",
    width: int = 500,
    height: int = 400,
) -> str:
    """파이 차트 SVG 생성."""
    if not data:
        return ""

    total = sum(data.values())
    if total == 0:
        return ""

    cx, cy = width * 0.4, height * 0.5
    radius = min(cx, cy) * 0.65

    labels = {
        "정부지원": "정부지원금",
        "현금": "자부담(현금)",
        "현물": "자부담(현물)",
    }

    paths = ""
    legend = ""
    start_angle = -90  # 12시 방향부터
    legend_y = height * 0.25

    for i, (key, value) in enumerate(data.items()):
        pct = value / total
        angle = pct * 360
        end_angle = start_angle + angle
        color = PIE_COLORS[i % len(PIE_COLORS)]

        # SVG arc path
        large_arc = 1 if angle > 180 else 0
        start_rad = math.radians(start_angle)
        end_rad = math.radians(end_angle)

        x1 = cx + radius * math.cos(start_rad)
        y1 = cy + radius * math.sin(start_rad)
        x2 = cx + radius * math.cos(end_rad)
        y2 = cy + radius * math.sin(end_rad)

        paths += (
            f'  <path d="M{cx},{cy} L{x1:.2f},{y1:.2f} '
            f'A{radius},{radius} 0 {large_arc},1 {x2:.2f},{y2:.2f} Z" '
            f'fill="{color}" stroke="white" stroke-width="2">\n'
            f'    <animate attributeName="opacity" from="0" to="1" dur="0.5s" fill="freeze"/>\n'
            f'  </path>\n'
        )

        # 라벨 (파이 중앙)
        mid_rad = math.radians(start_angle + angle / 2)
        label_r = radius * 0.6
        lx = cx + label_r * math.cos(mid_rad)
        ly = cy + label_r * math.sin(mid_rad)

        if pct >= 0.08:  # 8% 이상일 때만 파이 내부 라벨 표시
            paths += (
                f'  <text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" '
                f'fill="white" font-size="12" font-weight="bold" '
                f'font-family="{FONT_FAMILY}">{pct:.0%}</text>\n'
            )

        # 범례
        display_label = labels.get(key, key)
        amount_str = f"{value / 100_000_000:.0f}억원" if value >= 100_000_000 else f"{value / 10_000:.0f}만원"
        legend += (
            f'  <rect x="{width * 0.72}" y="{legend_y}" width="14" height="14" '
            f'fill="{color}" rx="3"/>\n'
            f'  <text x="{width * 0.72 + 20}" y="{legend_y + 12}" '
            f'fill="#374151" font-size="12" font-family="{FONT_FAMILY}">'
            f'{display_label} ({amount_str}, {pct:.1%})</text>\n'
        )
        legend_y += 28

        start_angle = end_angle

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">\n'
        f'  <rect width="{width}" height="{height}" fill="white" rx="8"/>\n'
        f'  <text x="{width / 2}" y="30" text-anchor="middle" '
        f'font-size="16" font-weight="bold" fill="#111827" '
        f'font-family="{FONT_FAMILY}">{title}</text>\n'
        f'{paths}'
        f'{legend}'
        f'</svg>'
    )
    return svg


def generate_funnel_chart_svg(
    data: dict[str, float],
    title: str = "시장 규모 분석 (TAM/SAM/SOM)",
    width: int = 600,
    height: int = 400,
) -> str:
    """퍼널 차트 SVG 생성 (stacked horizontal bars)."""
    if not data:
        return ""

    margin = {"top": 60, "right": 40, "bottom": 40, "left": 120}
    chart_w = width - margin["left"] - margin["right"]
    chart_h = height - margin["top"] - margin["bottom"]

    labels_map = {"TAM": "TAM (전체 시장)", "SAM": "SAM (유효 시장)", "SOM": "SOM (목표 시장)"}
    keys = ["TAM", "SAM", "SOM"]
    available = [(k, data[k]) for k in keys if k in data]
    if not available:
        return ""

    max_val = max(v for _, v in available) if available else 1
    bar_height = min(chart_h / len(available) * 0.6, 60)
    gap = (chart_h - bar_height * len(available)) / (len(available) + 1)

    bars = ""
    for i, (key, value) in enumerate(available):
        y = margin["top"] + gap + i * (bar_height + gap)
        bar_w = (value / max_val) * chart_w if max_val > 0 else 0
        # 퍼널 효과: 점점 좁아짐
        x_offset = (chart_w - bar_w) / 2
        color = CHART_COLORS[i % len(CHART_COLORS)]
        label = labels_map.get(key, key)

        val_str = f"{value:.0f}억원" if value < 10000 else f"{value / 10000:.1f}조원"

        bars += (
            f'  <rect x="{margin["left"] + x_offset:.1f}" y="{y:.1f}" '
            f'width="{bar_w:.1f}" height="{bar_height:.1f}" '
            f'fill="{color}" rx="6" opacity="0.85">\n'
            f'    <animate attributeName="width" from="0" to="{bar_w:.1f}" dur="0.6s" fill="freeze"/>\n'
            f'  </rect>\n'
            f'  <text x="{margin["left"] - 10}" y="{y + bar_height / 2 + 5:.1f}" '
            f'text-anchor="end" fill="#374151" font-size="13" font-weight="bold" '
            f'font-family="{FONT_FAMILY}">{label}</text>\n'
            f'  <text x="{margin["left"] + chart_w / 2:.1f}" y="{y + bar_height / 2 + 5:.1f}" '
            f'text-anchor="middle" fill="white" font-size="14" font-weight="bold" '
            f'font-family="{FONT_FAMILY}">{val_str}</text>\n'
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">\n'
        f'  <rect width="{width}" height="{height}" fill="white" rx="8"/>\n'
        f'  <text x="{width / 2}" y="30" text-anchor="middle" '
        f'font-size="16" font-weight="bold" fill="#111827" '
        f'font-family="{FONT_FAMILY}">{title}</text>\n'
        f'{bars}'
        f'</svg>'
    )
    return svg


def generate_org_chart_svg(
    team: list[dict[str, str]],
    title: str = "조직 구성도",
    width: int = 700,
    height: int = 350,
) -> str:
    """팀 조직도 SVG 생성."""
    if not team:
        return ""

    box_w, box_h = 130, 55
    gap_x, gap_y = 20, 60
    start_y = 70

    # 대표를 최상위에, 나머지를 아래에 배치
    ceo = None
    members = []
    for t in team:
        if t.get("type") == "대표" or "대표" in t.get("position", ""):
            ceo = t
        else:
            members.append(t)

    if ceo is None and team:
        ceo = team[0]
        members = team[1:]

    boxes = ""
    lines = ""

    # CEO 박스
    ceo_x = (width - box_w) / 2
    ceo_y = start_y
    boxes += (
        f'  <rect x="{ceo_x}" y="{ceo_y}" width="{box_w}" height="{box_h}" '
        f'fill="#1E40AF" rx="8" stroke="#1E3A8A" stroke-width="1"/>\n'
        f'  <text x="{ceo_x + box_w / 2}" y="{ceo_y + 22}" text-anchor="middle" '
        f'fill="white" font-size="13" font-weight="bold" '
        f'font-family="{FONT_FAMILY}">{ceo["position"]}</text>\n'
        f'  <text x="{ceo_x + box_w / 2}" y="{ceo_y + 40}" text-anchor="middle" '
        f'fill="#BFDBFE" font-size="10" font-family="{FONT_FAMILY}">'
        f'{ceo.get("role", "")[:16]}</text>\n'
    )

    # 멤버 박스들
    if members:
        total_w = len(members) * box_w + (len(members) - 1) * gap_x
        start_x = (width - total_w) / 2
        member_y = ceo_y + box_h + gap_y

        for i, mem in enumerate(members):
            mx = start_x + i * (box_w + gap_x)
            is_hire = mem.get("type") == "채용예정"
            fill = "#F3F4F6" if is_hire else "#EFF6FF"
            stroke = "#9CA3AF" if is_hire else "#3B82F6"
            text_color = "#6B7280" if is_hire else "#1E40AF"
            style_note = " (예정)" if is_hire else ""

            boxes += (
                f'  <rect x="{mx}" y="{member_y}" width="{box_w}" height="{box_h}" '
                f'fill="{fill}" rx="8" stroke="{stroke}" stroke-width="1.5" '
                f'stroke-dasharray="{"6,3" if is_hire else "none"}"/>\n'
                f'  <text x="{mx + box_w / 2}" y="{member_y + 22}" text-anchor="middle" '
                f'fill="{text_color}" font-size="12" font-weight="bold" '
                f'font-family="{FONT_FAMILY}">{mem["position"]}{style_note}</text>\n'
                f'  <text x="{mx + box_w / 2}" y="{member_y + 40}" text-anchor="middle" '
                f'fill="#6B7280" font-size="10" font-family="{FONT_FAMILY}">'
                f'{mem.get("role", "")[:16]}</text>\n'
            )

            # 연결선
            lines += (
                f'  <line x1="{ceo_x + box_w / 2}" y1="{ceo_y + box_h}" '
                f'x2="{mx + box_w / 2}" y2="{member_y}" '
                f'stroke="#CBD5E1" stroke-width="1.5"/>\n'
            )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">\n'
        f'  <rect width="{width}" height="{height}" fill="white" rx="8"/>\n'
        f'  <text x="{width / 2}" y="30" text-anchor="middle" '
        f'font-size="16" font-weight="bold" fill="#111827" '
        f'font-family="{FONT_FAMILY}">{title}</text>\n'
        f'{lines}'
        f'{boxes}'
        f'</svg>'
    )
    return svg


def generate_timeline_svg(
    milestones: list[dict[str, str]],
    title: str = "사업 추진 일정",
    width: int = 700,
    height: int = 300,
) -> str:
    """타임라인 SVG 생성."""
    if not milestones:
        return ""

    margin = {"top": 60, "right": 40, "bottom": 40, "left": 40}
    chart_w = width - margin["left"] - margin["right"]
    n = len(milestones)
    line_y = height * 0.45

    # 타임라인 선
    elements = (
        f'  <line x1="{margin["left"]}" y1="{line_y}" '
        f'x2="{width - margin["right"]}" y2="{line_y}" '
        f'stroke="#CBD5E1" stroke-width="3" stroke-linecap="round"/>\n'
    )

    segment_w = chart_w / max(n, 1)

    for i, ms in enumerate(milestones):
        cx = margin["left"] + segment_w * i + segment_w / 2
        color = CHART_COLORS[i % len(CHART_COLORS)]

        # 마일스톤 점
        elements += (
            f'  <circle cx="{cx}" cy="{line_y}" r="8" fill="{color}" '
            f'stroke="white" stroke-width="3"/>\n'
        )

        # 위에 작업명
        elements += (
            f'  <text x="{cx}" y="{line_y - 20}" text-anchor="middle" '
            f'fill="#374151" font-size="11" font-weight="bold" '
            f'font-family="{FONT_FAMILY}">{ms["task"][:12]}</text>\n'
        )

        # 아래에 기간
        elements += (
            f'  <text x="{cx}" y="{line_y + 25}" text-anchor="middle" '
            f'fill="#6B7280" font-size="10" font-family="{FONT_FAMILY}">'
            f'{ms["period"]}</text>\n'
        )

        # 상세 내용 (한 줄)
        if ms.get("detail"):
            elements += (
                f'  <text x="{cx}" y="{line_y + 42}" text-anchor="middle" '
                f'fill="#9CA3AF" font-size="9" font-family="{FONT_FAMILY}">'
                f'{ms["detail"][:18]}</text>\n'
            )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">\n'
        f'  <rect width="{width}" height="{height}" fill="white" rx="8"/>\n'
        f'  <text x="{width / 2}" y="30" text-anchor="middle" '
        f'font-size="16" font-weight="bold" fill="#111827" '
        f'font-family="{FONT_FAMILY}">{title}</text>\n'
        f'{elements}'
        f'</svg>'
    )
    return svg


# ── 메인 실행 함수 ──────────────────────────────────────────

def _read_sections(drafts_dir: Path) -> dict[str, str]:
    """초안 디렉토리에서 섹션 내용을 읽어 dict로 반환."""
    sections: dict[str, str] = {}
    for md_path in sorted(drafts_dir.glob("*.md")):
        # 파일명에서 섹션 키 추출
        stem = md_path.stem
        key = re.sub(r"^\d+[-_]", "", stem)
        sections[key] = md_path.read_text(encoding="utf-8")
    return sections


def run_visualize(
    project_dir: Path,
    drafts_dir: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """
    프로젝트 초안에서 시각화 자료를 생성합니다.

    Args:
        project_dir: 프로젝트 루트 디렉토리
        drafts_dir: 초안 디렉토리 (기본: project_dir/output/drafts/current/)
        output_dir: 출력 디렉토리 (기본: project_dir/output/visuals/)

    Returns:
        생성 결과 딕셔너리
    """
    result: dict[str, Any] = {
        "success": False,
        "charts": [],
        "output_dir": "",
        "errors": [],
    }

    try:
        # 초안 디렉토리
        if drafts_dir is None:
            drafts_dir = project_dir / "output" / "drafts" / "current"

        if not drafts_dir.is_dir():
            result["errors"].append(f"초안 디렉토리가 없습니다: {drafts_dir}")
            return result

        # 출력 디렉토리
        if output_dir is None:
            output_dir = project_dir / "output" / "visuals"
        output_dir.mkdir(parents=True, exist_ok=True)
        result["output_dir"] = str(output_dir)

        # 섹션 읽기
        sections = _read_sections(drafts_dir)
        if not sections:
            result["errors"].append("마크다운 파일이 없습니다.")
            return result

        logger.info("섹션 %d개 읽기 완료", len(sections))

        charts_generated: list[dict[str, str]] = []

        # 1. 매출 추이 바 차트
        revenue_data = _extract_revenue_data(sections)
        if revenue_data:
            svg = generate_bar_chart_svg(revenue_data, "매출 추이 (Revenue Growth)")
            if svg:
                svg_path = output_dir / "revenue_bar_chart.svg"
                svg_path.write_text(svg, encoding="utf-8")
                config = {"type": "bar", "title": "매출 추이", "data": revenue_data}
                (output_dir / "revenue_bar_chart.json").write_text(
                    json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                charts_generated.append({"type": "bar", "file": str(svg_path), "title": "매출 추이"})
                logger.info("매출 추이 바 차트 생성: %s", svg_path)

        # 2. 사업비 구성 파이 차트
        budget_data = _extract_budget_data(sections)
        if budget_data:
            svg = generate_pie_chart_svg(budget_data, "사업비 구성 (Budget Allocation)")
            if svg:
                svg_path = output_dir / "budget_pie_chart.svg"
                svg_path.write_text(svg, encoding="utf-8")
                config = {"type": "pie", "title": "사업비 구성", "data": budget_data}
                (output_dir / "budget_pie_chart.json").write_text(
                    json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                charts_generated.append({"type": "pie", "file": str(svg_path), "title": "사업비 구성"})
                logger.info("사업비 파이 차트 생성: %s", svg_path)

        # 3. TAM/SAM/SOM 퍼널 차트
        market_data = _extract_market_data(sections)
        if market_data:
            svg = generate_funnel_chart_svg(market_data, "시장 규모 분석 (TAM/SAM/SOM)")
            if svg:
                svg_path = output_dir / "market_funnel_chart.svg"
                svg_path.write_text(svg, encoding="utf-8")
                config = {"type": "funnel", "title": "시장 규모", "data": market_data}
                (output_dir / "market_funnel_chart.json").write_text(
                    json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                charts_generated.append({"type": "funnel", "file": str(svg_path), "title": "시장 규모"})
                logger.info("시장 퍼널 차트 생성: %s", svg_path)

        # 4. 조직도
        team_data = _extract_team_data(sections)
        if team_data:
            svg = generate_org_chart_svg(team_data, "조직 구성도 (Organization)")
            if svg:
                svg_path = output_dir / "org_chart.svg"
                svg_path.write_text(svg, encoding="utf-8")
                config = {"type": "org", "title": "조직 구성도", "data": team_data}
                (output_dir / "org_chart.json").write_text(
                    json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                charts_generated.append({"type": "org", "file": str(svg_path), "title": "조직 구성도"})
                logger.info("조직도 생성: %s", svg_path)

        # 5. 사업 추진 일정 타임라인
        milestone_data = _extract_milestones(sections)
        if milestone_data:
            svg = generate_timeline_svg(milestone_data, "사업 추진 일정 (Roadmap)")
            if svg:
                svg_path = output_dir / "timeline_chart.svg"
                svg_path.write_text(svg, encoding="utf-8")
                config = {"type": "timeline", "title": "추진 일정", "data": milestone_data}
                (output_dir / "timeline_chart.json").write_text(
                    json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                charts_generated.append({"type": "timeline", "file": str(svg_path), "title": "추진 일정"})
                logger.info("타임라인 생성: %s", svg_path)

        result["charts"] = charts_generated
        result["success"] = True

        logger.info("시각화 완료: %d개 차트 생성", len(charts_generated))

    except Exception as e:
        result["success"] = False
        result["errors"].append(str(e))
        logger.error("시각화 오류: %s", e)

    return result
