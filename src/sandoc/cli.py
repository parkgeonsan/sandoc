"""
sandoc.cli — 명령행 인터페이스

Usage:
    sandoc analyze <file>      양식 또는 공고문 분석
    sandoc classify <folder>   폴더 내 문서 분류
    sandoc profile <hwp_file>  HWP 스타일 프로파일 추출
    sandoc generate [options]  사업계획서 초안 생성 (스텁)
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click

logger = logging.getLogger("sandoc")


def _setup_logging(verbose: bool) -> None:
    """로깅 설정."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(name)s | %(levelname)s | %(message)s",
        stream=sys.stderr,
    )


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="상세 로그 출력")
@click.version_option(package_name="sandoc")
def main(verbose: bool) -> None:
    """sandoc — AI-powered Korean business plan generator (사업계획서 생성기)"""
    _setup_logging(verbose)


# ── analyze ───────────────────────────────────────────────────────

@main.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("-o", "--output", type=click.Path(), default=None, help="결과 저장 경로 (JSON)")
def analyze(file: str, output: str | None) -> None:
    """양식(HWP) 또는 공고문(PDF)을 분석합니다."""
    from sandoc.analyzer import analyze_template, analyze_announcement

    path = Path(file)
    ext = path.suffix.lower()

    if ext == ".hwp":
        click.echo(f"📄 HWP 양식 분석 중: {path.name}")
        result = analyze_template(path)

        click.echo(f"\n{'='*60}")
        click.echo(f"📊 분석 결과: {path.name}")
        click.echo(f"{'='*60}")
        click.echo(f"  문단 수: {result.total_paragraphs}")
        click.echo(f"  섹션 수: {len(result.sections)}")
        click.echo(f"  표 수:   {result.tables_count}")
        click.echo(f"  입력필드: {len(result.input_fields)}")

        if result.sections:
            click.echo(f"\n📑 섹션 목록:")
            for s in result.sections[:20]:
                click.echo(f"    {s.title}")

        if result.input_fields:
            click.echo(f"\n✏️  입력 필드:")
            for f in result.input_fields[:10]:
                click.echo(f"    {f[:80]}")

        if output:
            _save_json({"type": "template_analysis", "sections": len(result.sections),
                        "tables": result.tables_count, "fields": len(result.input_fields)}, output)

    elif ext == ".pdf":
        click.echo(f"📄 PDF 공고문 분석 중: {path.name}")
        result = analyze_announcement(path)  # type: ignore[assignment]

        click.echo(f"\n{'='*60}")
        click.echo(f"📊 분석 결과: {path.name}")
        click.echo(f"{'='*60}")
        click.echo(f"  제목:    {result.title}")  # type: ignore[attr-defined]
        click.echo(f"  페이지:  {result.total_pages}")  # type: ignore[attr-defined]
        click.echo(f"  평가항목: {len(result.scoring_criteria)}")  # type: ignore[attr-defined]
        click.echo(f"  주요일정: {len(result.key_dates)}")  # type: ignore[attr-defined]

        if result.scoring_criteria:  # type: ignore[attr-defined]
            click.echo(f"\n📋 평가 기준:")
            for c in result.scoring_criteria[:15]:  # type: ignore[attr-defined]
                click.echo(f"    {c.item} ({c.score}점)" if c.score else f"    {c.item}")

        if output:
            _save_json({"type": "announcement_analysis", "title": result.title,  # type: ignore[attr-defined]
                        "criteria": len(result.scoring_criteria),  # type: ignore[attr-defined]
                        "dates": len(result.key_dates)}, output)  # type: ignore[attr-defined]
    else:
        click.echo(f"❌ 지원하지 않는 형식: {ext} (지원: .hwp, .pdf)", err=True)
        raise SystemExit(1)


# ── classify ──────────────────────────────────────────────────────

@main.command()
@click.argument("folder", type=click.Path(exists=True, file_okay=False))
@click.option("-o", "--output", type=click.Path(), default=None, help="결과 저장 경로 (JSON)")
def classify(folder: str, output: str | None) -> None:
    """폴더 내 문서를 카테고리별로 분류합니다."""
    from sandoc.analyzer import classify_documents

    click.echo(f"📁 문서 분류 중: {folder}")
    results = classify_documents(folder)

    click.echo(f"\n{'='*60}")
    click.echo(f"📊 분류 결과: {len(results)}개 파일")
    click.echo(f"{'='*60}")

    # 카테고리별 그룹핑
    categories: dict[str, list] = {}
    for doc in results:
        cat = doc.category
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(doc)

    for cat, docs in sorted(categories.items()):
        click.echo(f"\n📂 {cat} ({len(docs)}개):")
        for doc in docs:
            conf = f" [{doc.confidence:.0%}]" if doc.confidence > 0 else ""
            click.echo(f"    {doc.filename}{conf}")

    if output:
        data = [
            {"file": d.filename, "category": d.category, "confidence": d.confidence}
            for d in results
        ]
        _save_json({"type": "classification", "files": data}, output)


# ── profile ───────────────────────────────────────────────────────

@main.command()
@click.argument("hwp_file", type=click.Path(exists=True))
@click.option("-o", "--output", type=click.Path(), default=None, help="프로파일 저장 경로 (JSON)")
def profile(hwp_file: str, output: str | None) -> None:
    """HWP 파일에서 스타일 프로파일을 추출합니다."""
    from sandoc.style import extract_style_profile, save_style_profile

    path = Path(hwp_file)
    click.echo(f"🎨 스타일 프로파일 추출 중: {path.name}")

    prof = extract_style_profile(path)

    click.echo(f"\n{'='*60}")
    click.echo(f"🎨 스타일 프로파일: {prof.name}")
    click.echo(f"{'='*60}")
    click.echo(f"  본문 폰트: {prof.body_font.name} ({prof.body_font.size_pt}pt)")
    click.echo(f"  제목 폰트: {prof.heading_font.name} ({prof.heading_font.size_pt}pt)")
    click.echo(f"  전체 폰트: {', '.join(prof.font_names[:10])}")
    click.echo(f"  문자모양:  {prof.char_shapes_count}개")

    if prof.sections:
        s = prof.sections[0]
        click.echo(f"  용지 크기: {s.paper_width_mm}×{s.paper_height_mm}mm")
        click.echo(
            f"  여백(상/하/좌/우): "
            f"{s.margins.top}/{s.margins.bottom}/"
            f"{s.margins.left}/{s.margins.right}mm"
        )

    if output:
        save_style_profile(prof, output)
        click.echo(f"\n💾 저장됨: {output}")
    else:
        # 기본 위치에 저장
        default_output = Path("profiles") / f"{prof.name}.json"
        default_output.parent.mkdir(parents=True, exist_ok=True)
        save_style_profile(prof, default_output)
        click.echo(f"\n💾 저장됨: {default_output}")


# ── generate ──────────────────────────────────────────────────────

@main.command()
@click.option("--title", default="사업계획서", help="사업계획서 제목")
@click.option("--sections", default=None, help="섹션 목록 (쉼표 구분)")
@click.option("-o", "--output", type=click.Path(), default=None, help="결과 저장 경로 (JSON)")
def generate(title: str, sections: str | None, output: str | None) -> None:
    """사업계획서 초안을 생성합니다. (스텁)"""
    from sandoc.generator import generate_plan

    section_list = None
    if sections:
        section_list = [s.strip() for s in sections.split(",")]

    click.echo(f"📝 사업계획서 생성 중: {title}")
    click.echo(f"   (현재 스텁 모드 — 향후 LLM 연동 예정)")

    plan = generate_plan(
        template_sections=section_list,
        context={"title": title},
    )

    click.echo(f"\n{'='*60}")
    click.echo(f"📝 생성 결과: {plan.title}")
    click.echo(f"{'='*60}")
    click.echo(f"  섹션 수: {len(plan.sections)}")
    click.echo(f"  총 단어: {plan.total_word_count}")

    for sec in plan.sections:
        click.echo(f"\n--- {sec.title} ---")
        click.echo(sec.content[:200])
        if len(sec.content) > 200:
            click.echo("  ...")

    if output:
        data = {
            "title": plan.title,
            "sections": [
                {"title": s.title, "content": s.content, "words": s.word_count}
                for s in plan.sections
            ],
            "total_words": plan.total_word_count,
        }
        _save_json(data, output)
        click.echo(f"\n💾 저장됨: {output}")


# ── 유틸리티 ──────────────────────────────────────────────────────

def _save_json(data: dict, path: str) -> None:
    """결과를 JSON 파일로 저장."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
