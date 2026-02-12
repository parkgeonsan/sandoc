"""
sandoc.assemble — 작성된 섹션 마크다운을 HWPX로 조립

output/drafts/current/ 의 *.md 파일을 읽어:
  - plan.json 형식으로 변환
  - 스타일 프로파일 적용
  - HWPX 문서 빌드
  - HTML 출력 (차트 인라인 포함, 목차, 페이지 번호)
  - 결과 검증
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from sandoc.generator import GeneratedPlan, GeneratedSection, SECTION_DEFS
from sandoc.hwpx_engine import HwpxBuilder, StyleMirror, validate_hwpx

logger = logging.getLogger(__name__)

# 섹션 키 이름 → 인덱스 매핑
SECTION_KEY_INDEX = {sd["key"]: i for i, sd in enumerate(SECTION_DEFS)}


def run_assemble(
    project_dir: Path,
    drafts_dir: Path | None = None,
    style_profile_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """
    작성된 섹션 마크다운 파일을 HWPX 문서로 조립합니다.

    Args:
        project_dir: 프로젝트 루트 디렉토리
        drafts_dir: 섹션 마크다운 파일 디렉토리 (기본: project_dir/output/drafts/current/)
        style_profile_path: 스타일 프로파일 JSON 경로
        output_path: HWPX 출력 경로

    Returns:
        조립 결과 딕셔너리
    """
    result: dict[str, Any] = {
        "success": False,
        "hwpx_path": "",
        "plan_json_path": "",
        "section_count": 0,
        "total_chars": 0,
        "validation": {},
        "errors": [],
    }

    try:
        # ── 1. 초안 디렉토리 결정 ──────────────────────────────
        if drafts_dir is None:
            drafts_dir = project_dir / "output" / "drafts" / "current"

        if not drafts_dir.is_dir():
            result["errors"].append(f"초안 디렉토리가 없습니다: {drafts_dir}")
            return result

        # ── 2. 마크다운 파일 읽기 ──────────────────────────────
        md_files = sorted(drafts_dir.glob("*.md"))
        if not md_files:
            result["errors"].append(f"마크다운 파일이 없습니다: {drafts_dir}")
            return result

        logger.info("마크다운 파일 %d개 발견: %s", len(md_files), drafts_dir)

        # ── 3. GeneratedPlan 구성 ──────────────────────────────
        plan = _build_plan_from_markdowns(md_files)
        result["section_count"] = len(plan.sections)
        result["total_chars"] = plan.total_word_count

        # ── 4. plan.json 저장 ──────────────────────────────────
        output_dir = project_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        plan_json_path = output_dir / "plan.json"
        plan_json_path.write_text(plan.to_json(), encoding="utf-8")
        result["plan_json_path"] = str(plan_json_path)

        # ── 5. 스타일 미러 초기화 ──────────────────────────────
        if style_profile_path is None:
            # 프로젝트 내 style-profile.json 탐색
            candidates = [
                project_dir / "style-profile.json",
                project_dir / "output" / "style-profile.json",
            ]
            for candidate in candidates:
                if candidate.exists():
                    style_profile_path = candidate
                    break

        if style_profile_path and style_profile_path.exists():
            style = StyleMirror.from_file(style_profile_path)
            logger.info("스타일 프로파일 로드: %s", style_profile_path)
        else:
            style = StyleMirror.default()
            logger.info("기본 스타일 사용")

        # ── 6. HWPX 빌드 ──────────────────────────────────────
        if output_path is None:
            output_path = output_dir / f"{plan.company_name or 'sandoc'}_사업계획서.hwpx"

        builder = HwpxBuilder(style=style)
        for section in plan.sections:
            builder.add_section(
                title=section.title,
                content=section.content,
                style_name="bodyText",
                section_key=section.section_key,
            )
        builder.build(output_path)
        result["hwpx_path"] = str(output_path)

        # ── 7. 검증 ──────────────────────────────────────────
        validation = validate_hwpx(output_path)
        result["validation"] = validation
        result["success"] = validation.get("valid", False)

        if not result["success"]:
            result["errors"].extend(validation.get("errors", []))

        # ── 8. HTML 출력 생성 ─────────────────────────────────
        try:
            visuals_dir = project_dir / "output" / "visuals"
            html = generate_html(
                plan,
                visuals_dir=visuals_dir if visuals_dir.is_dir() else None,
            )
            html_path = output_dir / f"{plan.company_name or 'sandoc'}_사업계획서.html"
            html_path.write_text(html, encoding="utf-8")
            result["html_path"] = str(html_path)
            logger.info("HTML 출력 생성: %s", html_path)
        except Exception as html_err:
            logger.warning("HTML 생성 오류 (무시): %s", html_err)

        logger.info(
            "HWPX 조립 완료: %s (%d 섹션, %d자)",
            output_path, result["section_count"], result["total_chars"],
        )

    except Exception as e:
        result["success"] = False
        result["errors"].append(str(e))
        logger.error("HWPX 조립 오류: %s", e)

    return result


def _build_plan_from_markdowns(md_files: list[Path]) -> GeneratedPlan:
    """마크다운 파일 목록에서 GeneratedPlan을 구성합니다."""
    plan = GeneratedPlan(
        title="사업계획서",
        company_name="",
    )

    for i, md_path in enumerate(md_files):
        text = md_path.read_text(encoding="utf-8")
        title, content = _parse_markdown_section(text)
        section_key = _infer_section_key(md_path.stem, i)

        section = GeneratedSection(
            title=title,
            content=content,
            section_key=section_key,
            section_index=i,
            word_count=len(content),
        )
        plan.sections.append(section)
        plan.total_word_count += section.word_count

    return plan


def _parse_markdown_section(text: str) -> tuple[str, str]:
    """마크다운 텍스트에서 제목(# heading)과 본문을 분리합니다."""
    lines = text.strip().split("\n")
    title = ""
    content_start = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#"):
            title = re.sub(r"^#+\s*", "", stripped)
            content_start = i + 1
            break

    if not title and lines:
        # # 없으면 첫 줄을 제목으로
        title = lines[0].strip()
        content_start = 1

    content = "\n".join(lines[content_start:]).strip()
    return title, content


def _infer_section_key(stem: str, index: int) -> str:
    """파일명에서 섹션 키를 추론합니다.

    파일명 패턴: 01_company_overview, 02_problem_recognition, etc.
    """
    # 숫자 접두사 제거: "01_company_overview" → "company_overview"
    key = re.sub(r"^\d+[-_]", "", stem)

    # SECTION_DEFS에 정의된 키인지 확인
    if key in SECTION_KEY_INDEX:
        return key

    # 알려진 키가 아니면 stem 그대로 사용
    return key


# ── HTML 출력 ─────────────────────────────────────────────────

def _md_to_html_body(text: str) -> str:
    """간단한 마크다운→HTML 변환 (외부 의존성 없음)."""
    lines = text.split("\n")
    html_lines: list[str] = []
    in_table = False

    for line in lines:
        stripped = line.strip()

        # 빈 줄
        if not stripped:
            if in_table:
                html_lines.append("</table>")
                in_table = False
            html_lines.append("")
            continue

        # 표 구분줄 (|---|) 건너뜀
        if re.match(r"^\s*\|[\s\-:|]+\|\s*$", stripped):
            continue

        # 표 행
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if not in_table:
                html_lines.append('<table class="data-table">')
                in_table = True
                # 첫 행은 헤더
                html_lines.append("  <tr>" + "".join(f"<th>{c}</th>" for c in cells) + "</tr>")
            else:
                html_lines.append("  <tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
            continue

        if in_table:
            html_lines.append("</table>")
            in_table = False

        # 헤딩
        m = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if m:
            level = len(m.group(1))
            text_content = m.group(2)
            anchor = re.sub(r"\s+", "-", text_content)
            html_lines.append(f'<h{level} id="{anchor}">{text_content}</h{level}>')
            continue

        # 볼드
        processed = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", stripped)
        # 불릿
        if stripped.startswith("◦") or stripped.startswith("○"):
            html_lines.append(f'<p class="bullet">{processed}</p>')
        elif stripped.startswith("  -"):
            html_lines.append(f'<p class="indent">{processed[2:].strip()}</p>')
        else:
            html_lines.append(f"<p>{processed}</p>")

    if in_table:
        html_lines.append("</table>")

    return "\n".join(html_lines)


def generate_html(
    plan: GeneratedPlan,
    visuals_dir: Path | None = None,
) -> str:
    """사업계획서를 HTML로 생성합니다 (차트 인라인, 목차, 인쇄 최적화)."""
    # 차트 SVG 로드
    chart_svgs: dict[str, str] = {}
    if visuals_dir and visuals_dir.is_dir():
        for svg_path in visuals_dir.glob("*.svg"):
            chart_svgs[svg_path.stem] = svg_path.read_text(encoding="utf-8")

    # 목차 생성
    toc_items = ""
    for i, section in enumerate(plan.sections):
        anchor = re.sub(r"\s+", "-", section.title)
        toc_items += f'  <li><a href="#{anchor}">{i + 1}. {section.title}</a></li>\n'

    # 섹션 HTML 생성
    sections_html = ""
    for i, section in enumerate(plan.sections):
        section_body = _md_to_html_body(section.content)
        anchor = re.sub(r"\s+", "-", section.title)

        # 섹션에 해당하는 차트 삽입
        chart_insert = ""
        key = section.section_key
        if key in ("growth_strategy", "financial_plan", "funding_plan") and "budget_pie_chart" in chart_svgs:
            chart_insert += f'<div class="chart-container">\n{chart_svgs.pop("budget_pie_chart")}\n</div>\n'
        if key in ("market_analysis", "growth_strategy") and "revenue_bar_chart" in chart_svgs:
            chart_insert += f'<div class="chart-container">\n{chart_svgs.pop("revenue_bar_chart")}\n</div>\n'
        if key in ("solution", "market_analysis") and "market_funnel_chart" in chart_svgs:
            chart_insert += f'<div class="chart-container">\n{chart_svgs.pop("market_funnel_chart")}\n</div>\n'
        if key == "team" and "org_chart" in chart_svgs:
            chart_insert += f'<div class="chart-container">\n{chart_svgs.pop("org_chart")}\n</div>\n'
        if key in ("market_analysis",) and "timeline_chart" in chart_svgs:
            chart_insert += f'<div class="chart-container">\n{chart_svgs.pop("timeline_chart")}\n</div>\n'

        sections_html += f'''
<section class="page-break" id="{anchor}">
  <h2>{i + 1}. {section.title}</h2>
  {section_body}
  {chart_insert}
</section>
'''

    # 나머지 차트 삽입 (부록)
    remaining_charts = ""
    if chart_svgs:
        remaining_charts = '<section class="page-break"><h2>참고 자료 (시각화)</h2>\n'
        for name, svg in chart_svgs.items():
            remaining_charts += f'<div class="chart-container">\n{svg}\n</div>\n'
        remaining_charts += "</section>\n"

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{plan.title or '사업계획서'}</title>
  <style>
    @page {{
      size: A4;
      margin: 20mm 15mm 25mm 15mm;
      @bottom-center {{
        content: counter(page) " / " counter(pages);
        font-size: 9pt;
        color: #999;
      }}
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: 'Pretendard', 'Malgun Gothic', '맑은 고딕', sans-serif;
      font-size: 10.5pt;
      line-height: 1.7;
      color: #1a1a1a;
      max-width: 210mm;
      margin: 0 auto;
      padding: 15mm;
      background: #fff;
    }}
    .cover {{
      text-align: center;
      padding: 80px 0 60px;
      border-bottom: 3px double #1E40AF;
      margin-bottom: 40px;
    }}
    .cover h1 {{
      font-size: 24pt;
      color: #1E40AF;
      margin-bottom: 16px;
      letter-spacing: -0.5px;
    }}
    .cover .company {{
      font-size: 14pt;
      color: #374151;
      margin-bottom: 8px;
    }}
    .cover .date {{
      font-size: 10pt;
      color: #9CA3AF;
    }}
    .toc {{
      background: #F9FAFB;
      border: 1px solid #E5E7EB;
      border-radius: 8px;
      padding: 24px 32px;
      margin: 30px 0;
    }}
    .toc h3 {{
      font-size: 13pt;
      color: #1E40AF;
      margin-bottom: 12px;
      border-bottom: 1px solid #E5E7EB;
      padding-bottom: 8px;
    }}
    .toc ol {{
      list-style: none;
      counter-reset: toc-counter;
      padding: 0;
    }}
    .toc li {{
      counter-increment: toc-counter;
      padding: 4px 0;
      font-size: 10.5pt;
    }}
    .toc li a {{
      color: #374151;
      text-decoration: none;
      border-bottom: 1px dotted #D1D5DB;
    }}
    .toc li a:hover {{ color: #1E40AF; }}
    h2 {{
      font-size: 14pt;
      color: #1E40AF;
      border-bottom: 2px solid #1E40AF;
      padding-bottom: 6px;
      margin: 32px 0 16px;
    }}
    h3 {{
      font-size: 12pt;
      color: #374151;
      margin: 20px 0 10px;
    }}
    h4 {{
      font-size: 11pt;
      color: #4B5563;
      margin: 16px 0 8px;
    }}
    p {{ margin: 6px 0; }}
    p.bullet {{
      padding-left: 16px;
      text-indent: -16px;
    }}
    p.indent {{
      padding-left: 24px;
      color: #374151;
    }}
    .data-table {{
      width: 100%;
      border-collapse: collapse;
      margin: 12px 0;
      font-size: 9.5pt;
    }}
    .data-table th, .data-table td {{
      border: 1px solid #D1D5DB;
      padding: 6px 10px;
      text-align: left;
    }}
    .data-table th {{
      background: #EFF6FF;
      color: #1E40AF;
      font-weight: 600;
    }}
    .data-table tr:nth-child(even) {{
      background: #F9FAFB;
    }}
    .chart-container {{
      text-align: center;
      margin: 24px auto;
      max-width: 100%;
    }}
    .chart-container svg {{
      max-width: 100%;
      height: auto;
    }}
    .page-break {{
      page-break-before: auto;
      page-break-inside: avoid;
    }}
    footer {{
      margin-top: 40px;
      padding-top: 16px;
      border-top: 1px solid #E5E7EB;
      text-align: center;
      font-size: 9pt;
      color: #9CA3AF;
    }}
    @media print {{
      body {{ padding: 0; }}
      .page-break {{ page-break-before: always; }}
      .page-break:first-of-type {{ page-break-before: avoid; }}
      footer {{ position: fixed; bottom: 10mm; left: 0; right: 0; }}
    }}
  </style>
</head>
<body>

<div class="cover">
  <h1>{plan.title or '사업계획서'}</h1>
  <p class="company">{plan.company_name}</p>
  <p class="date">Generated by sandoc</p>
</div>

<nav class="toc">
  <h3>목 차</h3>
  <ol>
{toc_items}
  </ol>
</nav>

{sections_html}

{remaining_charts}

<footer>
  <p>{plan.company_name} — {plan.title or '사업계획서'} | sandoc 자동생성</p>
</footer>

</body>
</html>"""

    return html
