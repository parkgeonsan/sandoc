"""
sandoc.cli — 명령행 인터페이스

Usage:
    sandoc analyze <file>      양식 또는 공고문 분석
    sandoc classify <folder>   폴더 내 문서 분류
    sandoc profile <hwp_file>  HWP 스타일 프로파일 추출
    sandoc generate [options]  사업계획서 생성 파이프라인
    sandoc build [options]     사업계획서 HWPX 출력 (스타일 미러링)
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
@click.option("--company-info", "-c", type=click.Path(exists=True), default=None,
              help="회사 정보 JSON 파일")
@click.option("--template", "-t", type=click.Path(exists=True), default=None,
              help="HWP 양식 파일")
@click.option("--announcement", "-a", type=click.Path(exists=True), default=None,
              help="PDF 공고문 파일")
@click.option("--style", "-s", type=click.Path(exists=True), default=None,
              help="스타일 프로파일 JSON")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="결과 저장 디렉토리")
@click.option("--prompts-only", is_flag=True, default=False,
              help="프롬프트만 생성 (콘텐츠 생성 없이)")
@click.option("--sample", is_flag=True, default=False,
              help="샘플 회사 정보로 데모 실행")
def generate(
    company_info: str | None,
    template: str | None,
    announcement: str | None,
    style: str | None,
    output: str | None,
    prompts_only: bool,
    sample: bool,
) -> None:
    """사업계획서를 생성합니다.

    전체 파이프라인: 양식 분석 → 공고문 분석 → 프롬프트 빌드 → 콘텐츠 생성

    \b
    예시:
      sandoc generate --sample                              # 샘플 데모
      sandoc generate -c company.json -o output/            # 회사 정보로 생성
      sandoc generate -c company.json -t template.hwp -a announcement.pdf
      sandoc generate -c company.json --prompts-only -o prompts/
    """
    from sandoc.generator import PlanGenerator, SECTION_DEFS
    from sandoc.schema import CompanyInfo, create_sample_company

    # 1. 회사 정보 로드
    if sample:
        click.echo("📋 샘플 회사 정보 사용 (데모 모드)")
        company = create_sample_company()
    elif company_info:
        click.echo(f"📋 회사 정보 로드: {company_info}")
        company = CompanyInfo.from_file(company_info)
    else:
        click.echo("❌ --company-info 또는 --sample 옵션이 필요합니다.", err=True)
        click.echo("   sandoc generate --sample                  # 데모 모드", err=True)
        click.echo("   sandoc generate -c company.json           # 회사 정보 JSON", err=True)
        raise SystemExit(1)

    click.echo(f"   기업명: {company.company_name}")
    click.echo(f"   아이템: {company.item_name}")
    click.echo(f"   총사업비: {company.total_budget:,}원")

    # 2. 양식/공고문 분석 (선택)
    template_analysis = {}
    announcement_analysis = {}
    style_profile = {}

    if template:
        click.echo(f"\n📄 양식 분석 중: {Path(template).name}")
        from sandoc.analyzer import analyze_template as _at
        ta = _at(template)
        template_analysis = {
            "sections": [{"title": s.title, "level": s.level} for s in ta.sections],
            "tables_count": ta.tables_count,
            "input_fields": ta.input_fields,
        }
        click.echo(f"   {len(ta.sections)}개 섹션, {ta.tables_count}개 표")

    if announcement:
        click.echo(f"\n📄 공고문 분석 중: {Path(announcement).name}")
        from sandoc.analyzer import analyze_announcement as _aa
        aa = _aa(announcement)
        announcement_analysis = {
            "title": aa.title,
            "scoring_criteria": [{"item": c.item, "score": c.score} for c in aa.scoring_criteria],
            "key_dates": aa.key_dates,
        }
        click.echo(f"   {len(aa.scoring_criteria)}개 평가항목")

    if style:
        click.echo(f"\n🎨 스타일 로드: {Path(style).name}")
        style_profile = json.loads(Path(style).read_text(encoding="utf-8"))

    # 3. 생성기 초기화
    gen = PlanGenerator(
        company_info=company,
        template_analysis=template_analysis,
        announcement_analysis=announcement_analysis,
        style_profile=style_profile,
    )

    # 4. 출력 디렉토리 설정
    output_dir = Path(output) if output else Path("output") / company.company_name.replace(" ", "_")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 5. 프롬프트 생성
    click.echo(f"\n📝 프롬프트 생성 중...")
    prompt_files = gen.save_prompts(output_dir / "prompts")
    click.echo(f"   {len(prompt_files)}개 프롬프트 저장 → {output_dir / 'prompts'}")

    if prompts_only:
        click.echo(f"\n✅ 프롬프트 생성 완료 (--prompts-only 모드)")
        click.echo(f"   저장 위치: {output_dir / 'prompts'}")
        return

    # 6. 콘텐츠 생성
    click.echo(f"\n📝 사업계획서 생성 중...")
    plan = gen.generate_full_plan()

    # 7. 결과 출력
    click.echo(f"\n{'='*60}")
    click.echo(f"📝 생성 결과: {plan.title}")
    click.echo(f"{'='*60}")
    click.echo(f"  섹션 수: {len(plan.sections)}")
    click.echo(f"  총 글자수: {plan.total_word_count:,}")

    if company.has_investment_bonus:
        click.echo(f"  ⭐ 투자유치 가점: 1점 (5억원 이상 투자유치)")

    click.echo(f"\n📋 섹션 목록:")
    for sec in plan.sections:
        eval_tag = f" [{sec.evaluation_category}]" if sec.evaluation_category else ""
        click.echo(f"  {sec.section_index+1}. {sec.title}{eval_tag} ({sec.word_count}자)")

    # 8. 결과 저장
    plan_path = output_dir / "plan.json"
    plan_path.write_text(plan.to_json(), encoding="utf-8")
    click.echo(f"\n💾 사업계획서 JSON: {plan_path}")

    # 회사 정보 저장
    company_path = output_dir / "company_info.json"
    company.save(company_path)
    click.echo(f"💾 회사 정보 JSON: {company_path}")

    # 각 섹션 콘텐츠를 개별 파일로 저장
    sections_dir = output_dir / "sections"
    sections_dir.mkdir(parents=True, exist_ok=True)
    for sec in plan.sections:
        sec_path = sections_dir / f"{sec.section_index+1:02d}_{sec.section_key}.md"
        sec_path.write_text(
            f"# {sec.title}\n\n{sec.content}\n",
            encoding="utf-8",
        )

    click.echo(f"💾 섹션 파일: {sections_dir}/")
    click.echo(f"\n✅ 사업계획서 생성 완료!")
    click.echo(f"   출력 디렉토리: {output_dir}")


# ── build ─────────────────────────────────────────────────────────

@main.command()
@click.option("--company-info", "-c", type=click.Path(exists=True), default=None,
              help="회사 정보 JSON 파일")
@click.option("--plan", "-p", type=click.Path(exists=True), default=None,
              help="기생성된 plan.json 파일 (있으면 콘텐츠 생성 건너뜀)")
@click.option("--style", "-s", type=click.Path(exists=True), default=None,
              help="스타일 프로파일 JSON")
@click.option("--template", "-t", type=click.Path(exists=True), default=None,
              help="HWP 양식 파일")
@click.option("--announcement", "-a", type=click.Path(exists=True), default=None,
              help="PDF 공고문 파일")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="결과 저장 디렉토리")
@click.option("--sample", is_flag=True, default=False,
              help="샘플 회사 정보로 데모 실행")
def build(
    company_info: str | None,
    plan: str | None,
    style: str | None,
    template: str | None,
    announcement: str | None,
    output: str | None,
    sample: bool,
) -> None:
    """사업계획서를 HWPX 파일로 출력합니다 (스타일 미러링).

    generate 와 달리 최종 HWPX 파일까지 생성합니다.
    기존 plan.json 이 있으면 콘텐츠 생성을 건너뛰고 HWPX 만 빌드합니다.

    \b
    예시:
      sandoc build --sample                                 # 샘플 데모 → HWPX
      sandoc build -c company.json -s style-profile.json     # 스타일 미러링 빌드
      sandoc build -p plan.json -s style-profile.json        # 기존 plan → HWPX
      sandoc build --sample -o output/my_plan                # 출력 디렉토리 지정
    """
    from sandoc.output import OutputPipeline
    from sandoc.schema import CompanyInfo, create_sample_company

    # 1. 회사 정보 로드
    if sample:
        click.echo("📋 샘플 회사 정보 사용 (데모 모드)")
        company = create_sample_company()
    elif company_info:
        click.echo(f"📋 회사 정보 로드: {company_info}")
        company = CompanyInfo.from_file(company_info)
    elif plan:
        # plan.json 만 있으면 최소한의 CompanyInfo 생성
        click.echo(f"📋 plan.json 에서 빌드: {plan}")
        plan_data = json.loads(Path(plan).read_text(encoding="utf-8"))
        company = CompanyInfo(company_name=plan_data.get("company_name", "sandoc"))
    else:
        click.echo("❌ --company-info, --plan, 또는 --sample 옵션이 필요합니다.", err=True)
        click.echo("   sandoc build --sample                     # 데모 모드", err=True)
        click.echo("   sandoc build -c company.json              # 회사 정보 JSON", err=True)
        click.echo("   sandoc build -p plan.json                 # 기존 plan.json", err=True)
        raise SystemExit(1)

    click.echo(f"   기업명: {company.company_name}")

    # 2. 양식/공고문 분석 (선택)
    template_analysis = {}
    announcement_analysis = {}

    if template:
        click.echo(f"\n📄 양식 분석 중: {Path(template).name}")
        from sandoc.analyzer import analyze_template as _at
        ta = _at(template)
        template_analysis = {
            "sections": [{"title": s.title, "level": s.level} for s in ta.sections],
            "tables_count": ta.tables_count,
        }
        click.echo(f"   {len(ta.sections)}개 섹션, {ta.tables_count}개 표")

    if announcement:
        click.echo(f"\n📄 공고문 분석 중: {Path(announcement).name}")
        from sandoc.analyzer import analyze_announcement as _aa
        aa = _aa(announcement)
        announcement_analysis = {
            "title": aa.title,
            "scoring_criteria": [{"item": c.item, "score": c.score} for c in aa.scoring_criteria],
        }
        click.echo(f"   {len(aa.scoring_criteria)}개 평가항목")

    # 3. 출력 디렉토리 설정
    output_dir = Path(output) if output else Path("output") / company.company_name.replace(" ", "_")

    # 4. 스타일 정보 표시
    if style:
        click.echo(f"\n🎨 스타일 프로파일: {Path(style).name}")
    else:
        click.echo(f"\n🎨 기본 스타일 사용 (A4, 맑은 고딕 10pt)")

    # 5. 출력 파이프라인 실행
    click.echo(f"\n📦 HWPX 빌드 중...")

    pipeline = OutputPipeline(
        company_info=company,
        output_dir=output_dir,
        style_profile_path=style,
        template_analysis=template_analysis,
        announcement_analysis=announcement_analysis,
        plan_json_path=plan,
    )

    result = pipeline.run()

    # 6. 결과 출력
    click.echo(f"\n{'='*60}")
    click.echo(f"📦 빌드 결과")
    click.echo(f"{'='*60}")
    click.echo(f"  상태: {'✅ 성공' if result.success else '❌ 실패'}")
    click.echo(f"  섹션 수: {result.section_count}")
    click.echo(f"  총 글자수: {result.total_chars:,}")

    if result.hwpx_path:
        click.echo(f"\n📄 HWPX: {result.hwpx_path}")
    if result.plan_json_path:
        click.echo(f"💾 Plan JSON: {result.plan_json_path}")
    if result.sections_dir:
        click.echo(f"💾 섹션 파일: {result.sections_dir}/")
    if result.prompts_dir:
        click.echo(f"💾 프롬프트: {result.prompts_dir}/")

    if result.validation:
        v = result.validation
        click.echo(f"\n🔍 HWPX 검증:")
        click.echo(f"  유효성: {'✅' if v.get('valid') else '❌'}")
        click.echo(f"  파일 수: {v.get('file_count', 0)}")
        click.echo(f"  섹션 수: {v.get('section_count', 0)}")
        if v.get("errors"):
            click.echo(f"  오류: {', '.join(v['errors'])}")

    if result.errors:
        click.echo(f"\n⚠️  오류:")
        for err in result.errors:
            click.echo(f"    {err}")

    if result.success:
        click.echo(f"\n✅ HWPX 빌드 완료!")
        click.echo(f"   출력 디렉토리: {output_dir}")
    else:
        click.echo(f"\n❌ HWPX 빌드 실패.")
        raise SystemExit(1)


# ── 유틸리티 ──────────────────────────────────────────────────────

def _save_json(data: dict, path: str) -> None:
    """결과를 JSON 파일로 저장."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
