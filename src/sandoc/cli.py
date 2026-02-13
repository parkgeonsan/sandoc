"""
sandoc.cli — 명령행 인터페이스

Usage:
    sandoc analyze <file>      양식 또는 공고문 분석
    sandoc classify <folder>   폴더 내 문서 분류
    sandoc profile <hwp_file>  HWP 스타일 프로파일 추출
    sandoc generate [options]  사업계획서 생성 파이프라인
    sandoc build [options]     사업계획서 HWPX 출력 (스타일 미러링)
    sandoc extract <project>   프로젝트 폴더에서 모든 정보 추출 (analyze+classify+profile)
    sandoc assemble <project>  작성된 섹션 마크다운을 HWPX로 조립
    sandoc visualize <project> 초안에서 시각화 차트 생성
    sandoc review <project>    사업계획서 자가 검토
    sandoc profile-register    기업 프로필 등록
    sandoc interview <project> 누락 정보 설문지 생성 / 답변 병합
    sandoc learn <project>     완성된 초안에서 지식 축적
    sandoc inject <project>    HWP 템플릿 삽입 매핑 생성
    sandoc run <project>       전체 파이프라인 실행
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


# ── extract ──────────────────────────────────────────────────────

@main.command()
@click.argument("project_dir", type=click.Path(exists=True, file_okay=False))
@click.option("-o", "--output", type=click.Path(), default=None,
              help="context.json 저장 경로 (기본: project_dir/context.json)")
def extract(project_dir: str, output: str | None) -> None:
    """프로젝트 폴더에서 모든 정보를 추출합니다 (analyze + classify + profile).

    docs/ 하위 폴더의 모든 문서를 스캔하여:
      - 문서 분류 (공고문/양식/참고/증빙)
      - HWP 양식 분석 (섹션, 표, 입력필드)
      - PDF 공고문 분석 (평가기준, 주요일정)
      - HWP 스타일 프로파일 추출

    결과를 context.json 과 missing_info.json 으로 저장합니다.

    \b
    예시:
      sandoc extract projects/2026-창업도약패키지/
    """
    from sandoc.extract import run_extract

    project_path = Path(project_dir)
    click.echo(f"📦 프로젝트 추출 시작: {project_path.name}")

    result = run_extract(project_path)

    # context.json 저장
    output_path = Path(output) if output else project_path / "context.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result["context"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    click.echo(f"\n💾 context.json → {output_path}")

    # missing_info.json 저장
    missing_path = output_path.parent / "missing_info.json"
    missing_path.write_text(
        json.dumps(result["missing_info"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    click.echo(f"💾 missing_info.json → {missing_path}")

    # style-profile.json 저장 (추출된 경우)
    if result.get("style_profile_data"):
        style_path = output_path.parent / "style-profile.json"
        style_path.write_text(
            json.dumps(result["style_profile_data"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        click.echo(f"💾 style-profile.json → {style_path}")

    # 요약 출력
    ctx = result["context"]
    click.echo(f"\n{'='*60}")
    click.echo(f"📊 추출 결과 요약")
    click.echo(f"{'='*60}")
    click.echo(f"  프로젝트: {ctx.get('project_name', 'N/A')}")
    click.echo(f"  문서 수: {len(ctx.get('documents', []))}")

    ta = ctx.get("template_analysis")
    if ta:
        click.echo(f"  양식 섹션: {len(ta.get('sections', []))}개")
        click.echo(f"  양식 표: {ta.get('tables_count', 0)}개")
        click.echo(f"  입력 필드: {len(ta.get('input_fields', []))}개")

    aa = ctx.get("announcement_analysis")
    if aa:
        click.echo(f"  공고문 제목: {aa.get('title', 'N/A')[:40]}")
        click.echo(f"  평가 항목: {len(aa.get('scoring_criteria', []))}개")
        click.echo(f"  주요 일정: {len(aa.get('key_dates', []))}개")

    missing = ctx.get("missing_info", [])
    if missing:
        click.echo(f"\n⚠️  누락 정보 ({len(missing)}개):")
        for item in missing[:10]:
            click.echo(f"    - {item}")
        if len(missing) > 10:
            click.echo(f"    ... 외 {len(missing) - 10}개")

    click.echo(f"\n✅ 추출 완료!")


# ── assemble ─────────────────────────────────────────────────────

@main.command()
@click.argument("project_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--drafts-dir", "-d", type=click.Path(exists=True, file_okay=False), default=None,
              help="섹션 마크다운 파일 디렉토리 (기본: project_dir/output/drafts/current/)")
@click.option("--style", "-s", type=click.Path(exists=True), default=None,
              help="스타일 프로파일 JSON (기본: project_dir/style-profile.json)")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="HWPX 출력 경로")
def assemble(
    project_dir: str,
    drafts_dir: str | None,
    style: str | None,
    output: str | None,
) -> None:
    """작성된 섹션 마크다운 파일을 HWPX 문서로 조립합니다.

    output/drafts/current/ 의 *.md 파일을 읽어:
      - plan.json 형식으로 변환
      - 스타일 프로파일 적용
      - HWPX 문서 빌드
      - 결과 검증

    \b
    예시:
      sandoc assemble projects/2026-창업도약패키지/
      sandoc assemble projects/my-project/ -s style-profile.json -o output.hwpx
    """
    from sandoc.assemble import run_assemble

    project_path = Path(project_dir)
    click.echo(f"🔨 HWPX 조립 시작: {project_path.name}")

    result = run_assemble(
        project_dir=project_path,
        drafts_dir=Path(drafts_dir) if drafts_dir else None,
        style_profile_path=Path(style) if style else None,
        output_path=Path(output) if output else None,
    )

    click.echo(f"\n{'='*60}")
    click.echo(f"📦 조립 결과")
    click.echo(f"{'='*60}")
    click.echo(f"  상태: {'✅ 성공' if result['success'] else '❌ 실패'}")
    click.echo(f"  섹션 수: {result['section_count']}")
    click.echo(f"  총 글자수: {result['total_chars']:,}")

    if result.get("hwpx_path"):
        click.echo(f"\n📄 HWPX: {result['hwpx_path']}")

    if result.get("html_path"):
        click.echo(f"🌐 HTML: {result['html_path']}")

    if result.get("plan_json_path"):
        click.echo(f"💾 Plan JSON: {result['plan_json_path']}")

    if result.get("validation"):
        v = result["validation"]
        click.echo(f"\n🔍 HWPX 검증:")
        click.echo(f"  유효성: {'✅' if v.get('valid') else '❌'}")
        click.echo(f"  파일 수: {v.get('file_count', 0)}")

    if result.get("errors"):
        click.echo(f"\n⚠️  오류:")
        for err in result["errors"]:
            click.echo(f"    {err}")

    if result["success"]:
        click.echo(f"\n✅ HWPX 조립 완료!")
    else:
        click.echo(f"\n❌ HWPX 조립 실패.")
        raise SystemExit(1)


# ── visualize ─────────────────────────────────────────────────

@main.command()
@click.argument("project_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--drafts-dir", "-d", type=click.Path(exists=True, file_okay=False), default=None,
              help="섹션 마크다운 파일 디렉토리")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="시각화 출력 디렉토리")
def visualize(project_dir: str, drafts_dir: str | None, output: str | None) -> None:
    """초안 섹션에서 시각화 차트를 생성합니다.

    매출 추이, 사업비 구성, 시장 규모 분석 등의
    SVG 차트를 자동 생성하여 output/visuals/ 에 저장합니다.

    \b
    예시:
      sandoc visualize projects/2026-창업도약패키지/
    """
    from sandoc.visualize import run_visualize

    project_path = Path(project_dir)
    click.echo(f"📊 시각화 생성 시작: {project_path.name}")

    result = run_visualize(
        project_dir=project_path,
        drafts_dir=Path(drafts_dir) if drafts_dir else None,
        output_dir=Path(output) if output else None,
    )

    click.echo(f"\n{'='*60}")
    click.echo(f"📊 시각화 결과")
    click.echo(f"{'='*60}")
    click.echo(f"  상태: {'✅ 성공' if result['success'] else '❌ 실패'}")
    click.echo(f"  생성된 차트: {len(result['charts'])}개")

    if result["charts"]:
        click.echo(f"\n📈 생성된 차트:")
        for chart in result["charts"]:
            click.echo(f"    {chart['type']:10s} — {chart['title']}")

    if result.get("output_dir"):
        click.echo(f"\n📁 출력 디렉토리: {result['output_dir']}")

    if result.get("errors"):
        click.echo(f"\n⚠️  오류:")
        for err in result["errors"]:
            click.echo(f"    {err}")

    if result["success"]:
        click.echo(f"\n✅ 시각화 생성 완료!")
    else:
        click.echo(f"\n❌ 시각화 생성 실패.")
        raise SystemExit(1)


# ── review ────────────────────────────────────────────────────

@main.command()
@click.argument("project_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--drafts-dir", "-d", type=click.Path(exists=True, file_okay=False), default=None,
              help="섹션 마크다운 파일 디렉토리")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="리뷰 결과 저장 경로 (기본: output/review.md)")
def review(project_dir: str, drafts_dir: str | None, output: str | None) -> None:
    """사업계획서 자가 검토를 실행합니다.

    초안 섹션을 분석하여 섹션별 점수, 누락 항목,
    개선 사항, 종합 준비도 점수를 산출합니다.

    \b
    예시:
      sandoc review projects/2026-창업도약패키지/
    """
    from sandoc.review import run_review

    project_path = Path(project_dir)
    click.echo(f"🔍 자가 검토 시작: {project_path.name}")

    result = run_review(
        project_dir=project_path,
        drafts_dir=Path(drafts_dir) if drafts_dir else None,
        output_path=Path(output) if output else None,
    )

    click.echo(f"\n{'='*60}")
    click.echo(f"🔍 검토 결과")
    click.echo(f"{'='*60}")
    click.echo(f"  상태: {'✅ 완료' if result['success'] else '❌ 실패'}")

    if result["success"]:
        score = result["overall_score"]
        if score >= 80:
            grade = "A (우수) 🟢"
        elif score >= 60:
            grade = "B (보통) 🟡"
        elif score >= 40:
            grade = "C (미흡) 🟠"
        else:
            grade = "D (부족) 🔴"

        click.echo(f"  종합 점수: {score:.0f}/100점 — {grade}")
        click.echo(f"  작성 섹션: {len(result.get('present_sections', []))}/{len(result.get('present_sections', [])) + len(result.get('missing_sections', []))}")

        if result.get("missing_sections"):
            click.echo(f"\n⚠️  누락 섹션:")
            for s in result["missing_sections"]:
                click.echo(f"    - {s}")

        if result.get("issues"):
            click.echo(f"\n📋 주요 이슈 ({len(result['issues'])}건):")
            for issue in result["issues"][:5]:
                click.echo(f"    • {issue}")
            if len(result["issues"]) > 5:
                click.echo(f"    ... 외 {len(result['issues']) - 5}건")

        click.echo(f"\n📄 상세 리뷰: {result['output_path']}")
    else:
        if result.get("errors"):
            for err in result["errors"]:
                click.echo(f"    {err}")
        raise SystemExit(1)


# ── profile-register ─────────────────────────────────────────

@main.command("profile-register")
@click.option("--docs", "-d", type=click.Path(exists=True), default=None,
              help="기업 문서 경로 (폴더 또는 파일)")
@click.option("--name", "-n", type=str, default=None,
              help="프로필 이름 (기본: 추출된 회사명)")
@click.option("--company", "-c", type=str, default=None,
              help="회사명 직접 입력")
@click.option("--ceo", type=str, default=None,
              help="대표자명 직접 입력")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="프로필 저장 디렉토리 (기본: ./profiles/)")
def profile_register(
    docs: str | None,
    name: str | None,
    company: str | None,
    ceo: str | None,
    output: str | None,
) -> None:
    """기업 프로필을 등록합니다.

    사업자등록증 PDF, 재무제표 등에서 기업 정보를 추출하거나
    직접 입력하여 재사용 가능한 프로필을 생성합니다.

    \b
    예시:
      sandoc profile-register -d docs/ -n "(주)스마트테크"
      sandoc profile-register --company "(주)테스트" --ceo "홍길동"
      sandoc profile-register -d 사업자등록증.pdf
    """
    from sandoc.profile_register import run_profile_register

    click.echo(f"📝 기업 프로필 등록")

    result = run_profile_register(
        docs_path=Path(docs) if docs else None,
        profile_name=name,
        profiles_dir=Path(output) if output else None,
        company_name=company,
        ceo_name=ceo,
    )

    click.echo(f"\n{'='*60}")
    click.echo(f"📝 등록 결과")
    click.echo(f"{'='*60}")
    click.echo(f"  상태: {'✅ 성공' if result['success'] else '❌ 실패'}")

    if result["success"]:
        profile = result.get("profile", {})
        click.echo(f"  회사명: {profile.get('company_name', 'N/A')}")
        click.echo(f"  대표자: {profile.get('ceo_name', 'N/A')}")
        click.echo(f"  사업자번호: {profile.get('business_registration_no', 'N/A')}")
        click.echo(f"  추출 필드: {len(result.get('extracted_fields', []))}개")

        if result.get("source_documents"):
            click.echo(f"\n📄 소스 문서:")
            for doc in result["source_documents"]:
                click.echo(f"    {Path(doc).name}")

        click.echo(f"\n💾 프로필 저장: {result['profile_path']}")
    else:
        if result.get("errors"):
            for err in result["errors"]:
                click.echo(f"    {err}")
        raise SystemExit(1)


# ── interview ─────────────────────────────────────────────────

@main.command()
@click.argument("project_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--fill", "-f", type=click.Path(exists=True), default=None,
              help="answers.json 파일로 누락 정보 병합")
def interview(project_dir: str, fill: str | None) -> None:
    """누락 정보 설문지를 생성하거나, 답변을 병합합니다.

    missing_info.json 을 읽어 카테고리별 설문지(questionnaire.md)와
    작성 가능한 JSON 템플릿(company_info_template.json)을 생성합니다.

    --fill 옵션으로 작성된 답변을 context.json 에 병합할 수 있습니다.

    \b
    예시:
      sandoc interview projects/2026-창업도약패키지/
      sandoc interview projects/2026-창업도약패키지/ --fill answers.json
    """
    from sandoc.interview import run_interview

    project_path = Path(project_dir)

    if fill:
        click.echo(f"📝 답변 병합 모드: {Path(fill).name}")
    else:
        click.echo(f"📋 설문지 생성 중: {project_path.name}")

    result = run_interview(
        project_path,
        fill_path=Path(fill) if fill else None,
    )

    if result["mode"] == "fill":
        click.echo(f"\n{'='*60}")
        click.echo(f"📝 병합 결과")
        click.echo(f"{'='*60}")
        click.echo(f"  상태: {'✅ 성공' if result['success'] else '❌ 실패'}")
        click.echo(f"  병합된 필드: {result['merged_fields']}개")
    else:
        click.echo(f"\n{'='*60}")
        click.echo(f"📋 설문지 생성 결과")
        click.echo(f"{'='*60}")
        click.echo(f"  상태: {'✅ 성공' if result['success'] else '❌ 실패'}")
        if result.get("questionnaire_path"):
            click.echo(f"\n📄 설문지: {result['questionnaire_path']}")
        if result.get("template_path"):
            click.echo(f"📄 JSON 템플릿: {result['template_path']}")

    if result.get("errors"):
        for err in result["errors"]:
            click.echo(f"⚠️  {err}")
        raise SystemExit(1)

    if result["success"]:
        if result["mode"] == "fill":
            click.echo(f"\n✅ 답변 병합 완료!")
        else:
            click.echo(f"\n✅ 설문지 생성 완료!")
            click.echo(f"   JSON 템플릿을 채워서 --fill 옵션으로 병합하세요.")


# ── learn ────────────────────────────────────────────────────

@main.command()
@click.argument("project_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--knowledge-dir", "-k", type=click.Path(), default=None,
              help="지식 저장 디렉토리 (기본: knowledge/)")
def learn(project_dir: str, knowledge_dir: str | None) -> None:
    """완성된 초안에서 효과적 표현/패턴을 추출하여 지식을 축적합니다.

    output/drafts/current/ 의 마크다운 파일을 분석하여:
      - 효과적 표현을 knowledge/expressions/ 에 저장
      - 구조적 패턴을 knowledge/patterns/ 에 저장
      - 교훈을 knowledge/lessons.md 에 기록

    \b
    예시:
      sandoc learn projects/2026-창업도약패키지/
      sandoc learn projects/my-project/ -k ./my_knowledge/
    """
    from sandoc.learn import run_learn

    project_path = Path(project_dir)
    click.echo(f"📚 지식 축적 시작: {project_path.name}")

    result = run_learn(
        project_path,
        knowledge_dir=Path(knowledge_dir) if knowledge_dir else None,
    )

    click.echo(f"\n{'='*60}")
    click.echo(f"📚 학습 결과")
    click.echo(f"{'='*60}")
    click.echo(f"  상태: {'✅ 성공' if result['success'] else '❌ 실패'}")
    click.echo(f"  처리 섹션: {len(result['processed_sections'])}개")
    click.echo(f"  추출 표현: {result['expressions_count']}개")
    click.echo(f"  추출 패턴: {result['patterns_count']}개")

    if result.get("lessons_path"):
        click.echo(f"\n📄 교훈 기록: {result['lessons_path']}")

    if result.get("errors"):
        for err in result["errors"]:
            click.echo(f"⚠️  {err}")
        raise SystemExit(1)

    if result["success"]:
        click.echo(f"\n✅ 지식 축적 완료!")


# ── inject ───────────────────────────────────────────────────

@main.command()
@click.argument("project_dir", type=click.Path(exists=True, file_okay=False))
def inject(project_dir: str) -> None:
    """HWP 템플릿 삽입 매핑 파일을 생성합니다.

    초안 섹션과 원본 HWP 양식의 매핑 정보를 생성합니다:
      - injection_map.json: 섹션↔양식 매핑
      - injection_instructions.md: hwpx-mcp 사용 지시서

    hwpx-mcp 가 사용 가능할 때, 지시서를 따라 실제 삽입을 수행합니다.

    \b
    예시:
      sandoc inject projects/2026-창업도약패키지/
    """
    from sandoc.inject import run_inject

    project_path = Path(project_dir)
    click.echo(f"💉 삽입 매핑 생성 중: {project_path.name}")

    result = run_inject(project_path)

    click.echo(f"\n{'='*60}")
    click.echo(f"💉 매핑 결과")
    click.echo(f"{'='*60}")
    click.echo(f"  상태: {'✅ 성공' if result['success'] else '❌ 실패'}")
    click.echo(f"  매핑 수: {result['mappings_count']}개")

    if result.get("map_path"):
        click.echo(f"\n📄 매핑 파일: {result['map_path']}")
    if result.get("instructions_path"):
        click.echo(f"📄 삽입 지시서: {result['instructions_path']}")

    if result.get("errors"):
        for err in result["errors"]:
            click.echo(f"⚠️  {err}")
        raise SystemExit(1)

    if result["success"]:
        click.echo(f"\n✅ 삽입 매핑 생성 완료!")
        click.echo(f"   hwpx-mcp 사용 시 injection_instructions.md 를 참조하세요.")


# ── run (full pipeline) ──────────────────────────────────────

@main.command("run")
@click.argument("project_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--company-info", "-c", type=click.Path(exists=True), default=None,
              help="회사 정보 JSON 파일 (context.json 에 병합)")
@click.option("--skip-extract", is_flag=True, default=False,
              help="extract 단계 건너뛰기")
@click.option("--skip-visualize", is_flag=True, default=False,
              help="visualize 단계 건너뛰기")
@click.option("--skip-review", is_flag=True, default=False,
              help="review 단계 건너뛰기")
def run_cmd(
    project_dir: str,
    company_info: str | None,
    skip_extract: bool,
    skip_visualize: bool,
    skip_review: bool,
) -> None:
    """전체 파이프라인을 순차 실행합니다.

    extract → (company-info 병합) → visualize → review → assemble

    \b
    예시:
      sandoc run projects/2026-창업도약패키지/
      sandoc run projects/my-project/ -c company.json
      sandoc run projects/my-project/ --skip-extract --skip-review
    """
    from sandoc.run import run_pipeline

    project_path = Path(project_dir)
    click.echo(f"🚀 전체 파이프라인 시작: {project_path.name}")
    click.echo(f"{'='*60}")

    result = run_pipeline(
        project_path,
        company_info_path=Path(company_info) if company_info else None,
        skip_extract=skip_extract,
        skip_visualize=skip_visualize,
        skip_review=skip_review,
    )

    # 단계별 결과 출력
    click.echo(f"\n{'='*60}")
    click.echo(f"📊 파이프라인 결과")
    click.echo(f"{'='*60}")

    steps = result.get("steps", {})
    for step_name, step_data in steps.items():
        if isinstance(step_data, dict):
            status = "✅" if step_data.get("success") else "❌"
            click.echo(f"  {status} {step_name}")
        elif isinstance(step_data, str):
            click.echo(f"  ℹ️  {step_data}")

    summary = result["summary"]
    click.echo(f"\n📋 요약:")
    click.echo(f"  완료 단계: {summary['completed_steps']}/{summary['total_steps']}")

    if summary.get("missing_info_count"):
        click.echo(f"  누락 정보: {summary['missing_info_count']}개")

    if summary.get("overall_score") is not None:
        score = summary["overall_score"]
        click.echo(f"  검토 점수: {score:.0f}/100점")

    if summary.get("section_count"):
        click.echo(f"  작성 섹션: {summary['section_count']}개")

    if summary.get("hwpx_path"):
        click.echo(f"\n📄 HWPX: {summary['hwpx_path']}")
    if summary.get("html_path"):
        click.echo(f"🌐 HTML: {summary['html_path']}")

    if summary.get("failed_steps"):
        click.echo(f"\n⚠️  실패 단계: {', '.join(summary['failed_steps'])}")

    if result.get("errors"):
        click.echo(f"\n⚠️  오류:")
        for err in result["errors"]:
            click.echo(f"    {err}")

    if result["success"]:
        click.echo(f"\n✅ 파이프라인 완료!")
    else:
        if summary["completed_steps"] > 0:
            click.echo(f"\n⚠️  파이프라인 부분 완료 ({summary['completed_steps']}/{summary['total_steps']})")
        else:
            click.echo(f"\n❌ 파이프라인 실패.")
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
