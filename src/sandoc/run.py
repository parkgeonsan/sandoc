"""
sandoc.run — 전체 파이프라인 실행 (Full Pipeline Command)

순차적으로 모든 단계를 실행합니다:
  1. extract → 문서 분석 + context.json
  2. (선택) company-info 병합
  3. visualize → 시각화 차트
  4. generate sections (기존 초안 사용 또는 새로 생성)
  5. review → 자가 검토
  6. assemble → HWPX + HTML 조립
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def run_pipeline(
    project_dir: Path,
    company_info_path: Path | None = None,
    skip_extract: bool = False,
    skip_visualize: bool = False,
    skip_review: bool = False,
) -> dict[str, Any]:
    """
    전체 파이프라인을 실행합니다.

    Args:
        project_dir: 프로젝트 루트 디렉토리
        company_info_path: 회사 정보 JSON 파일 경로 (선택)
        skip_extract: extract 단계 건너뛰기
        skip_visualize: visualize 단계 건너뛰기
        skip_review: review 단계 건너뛰기

    Returns:
        {
            "success": bool,
            "steps": {
                "extract": { ... },
                "merge": { ... },
                "visualize": { ... },
                "review": { ... },
                "assemble": { ... },
            },
            "summary": {
                "total_steps": int,
                "completed_steps": int,
                "failed_steps": list[str],
                "missing_info_count": int,
                "section_count": int,
                "overall_score": float | None,
                "hwpx_path": str | None,
                "html_path": str | None,
            },
            "errors": list[str],
        }
    """
    result: dict[str, Any] = {
        "success": False,
        "steps": {},
        "summary": {
            "total_steps": 0,
            "completed_steps": 0,
            "failed_steps": [],
            "missing_info_count": 0,
            "section_count": 0,
            "overall_score": None,
            "hwpx_path": None,
            "html_path": None,
        },
        "errors": [],
    }

    # ── Step 1: Extract ──────────────────────────────────────────
    if not skip_extract:
        result["summary"]["total_steps"] += 1
        logger.info("Step 1: extract 실행 중...")

        try:
            from sandoc.extract import run_extract

            extract_result = run_extract(project_dir)

            # context.json 저장
            context_path = project_dir / "context.json"
            context_path.parent.mkdir(parents=True, exist_ok=True)
            context_path.write_text(
                json.dumps(extract_result["context"], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            # missing_info.json 저장
            missing_path = project_dir / "missing_info.json"
            missing_path.write_text(
                json.dumps(extract_result["missing_info"], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            # style-profile.json 저장
            if extract_result.get("style_profile_data"):
                style_path = project_dir / "style-profile.json"
                style_path.write_text(
                    json.dumps(extract_result["style_profile_data"], ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            missing_count = len(extract_result["context"].get("missing_info", []))
            result["steps"]["extract"] = {
                "success": True,
                "documents": len(extract_result["context"].get("documents", [])),
                "missing_info": missing_count,
            }
            result["summary"]["missing_info_count"] = missing_count
            result["summary"]["completed_steps"] += 1
            logger.info("Step 1: extract 완료 — 누락 정보 %d개", missing_count)

        except Exception as e:
            result["steps"]["extract"] = {"success": False, "error": str(e)}
            result["summary"]["failed_steps"].append("extract")
            result["errors"].append(f"extract 실패: {e}")
            logger.error("Step 1: extract 실패 — %s", e)
    else:
        logger.info("Step 1: extract 건너뜀")

    # ── Step 2: Company Info Merge ───────────────────────────────
    if company_info_path:
        result["summary"]["total_steps"] += 1
        logger.info("Step 2: company-info 병합 중...")

        try:
            merge_result = _merge_company_info(project_dir, company_info_path)
            result["steps"]["merge"] = merge_result
            if merge_result["success"]:
                result["summary"]["completed_steps"] += 1
                logger.info("Step 2: %d개 필드 병합됨", merge_result["merged_fields"])
            else:
                result["summary"]["failed_steps"].append("merge")
                result["errors"].extend(merge_result.get("errors", []))
        except Exception as e:
            result["steps"]["merge"] = {"success": False, "error": str(e)}
            result["summary"]["failed_steps"].append("merge")
            result["errors"].append(f"병합 실패: {e}")
    else:
        logger.info("Step 2: company-info 없음, 건너뜀")

    # ── Check drafts exist ───────────────────────────────────────
    drafts_dir = project_dir / "output" / "drafts" / "current"
    has_drafts = drafts_dir.is_dir() and any(drafts_dir.glob("*.md"))

    if not has_drafts:
        # 초안이 없으면 이후 단계 실행 불가
        result["steps"]["note"] = "초안 파일이 없습니다. Claude Code로 섹션을 작성한 후 다시 실행하세요."
        result["summary"]["total_steps"] += 3  # visualize, review, assemble
        result["summary"]["failed_steps"].extend(["visualize", "review", "assemble"])
        result["errors"].append(
            "output/drafts/current/ 에 마크다운 초안 파일이 없습니다. "
            "Claude Code로 섹션 초안을 먼저 작성하세요."
        )
        # extract 결과가 있으면 부분 성공
        if result["summary"]["completed_steps"] > 0:
            result["success"] = True
        return result

    # ── Step 3: Visualize ────────────────────────────────────────
    if not skip_visualize:
        result["summary"]["total_steps"] += 1
        logger.info("Step 3: visualize 실행 중...")

        try:
            from sandoc.visualize import run_visualize

            vis_result = run_visualize(project_dir)
            result["steps"]["visualize"] = {
                "success": vis_result["success"],
                "charts": len(vis_result.get("charts", [])),
            }
            if vis_result["success"]:
                result["summary"]["completed_steps"] += 1
                logger.info("Step 3: %d개 차트 생성", len(vis_result.get("charts", [])))
            else:
                result["summary"]["failed_steps"].append("visualize")
                result["errors"].extend(vis_result.get("errors", []))
        except Exception as e:
            result["steps"]["visualize"] = {"success": False, "error": str(e)}
            result["summary"]["failed_steps"].append("visualize")
            result["errors"].append(f"visualize 실패: {e}")
    else:
        logger.info("Step 3: visualize 건너뜀")

    # ── Step 4: Review ───────────────────────────────────────────
    if not skip_review:
        result["summary"]["total_steps"] += 1
        logger.info("Step 4: review 실행 중...")

        try:
            from sandoc.review import run_review

            rev_result = run_review(project_dir)
            result["steps"]["review"] = {
                "success": rev_result["success"],
                "overall_score": rev_result.get("overall_score"),
                "missing_sections": rev_result.get("missing_sections", []),
            }
            if rev_result["success"]:
                result["summary"]["completed_steps"] += 1
                result["summary"]["overall_score"] = rev_result.get("overall_score")
                logger.info("Step 4: 검토 점수 %.0f/100", rev_result.get("overall_score", 0))
            else:
                result["summary"]["failed_steps"].append("review")
                result["errors"].extend(rev_result.get("errors", []))
        except Exception as e:
            result["steps"]["review"] = {"success": False, "error": str(e)}
            result["summary"]["failed_steps"].append("review")
            result["errors"].append(f"review 실패: {e}")
    else:
        logger.info("Step 4: review 건너뜀")

    # ── Step 5: Assemble ─────────────────────────────────────────
    result["summary"]["total_steps"] += 1
    logger.info("Step 5: assemble 실행 중...")

    try:
        from sandoc.assemble import run_assemble

        style_path = project_dir / "style-profile.json"
        asm_result = run_assemble(
            project_dir,
            style_profile_path=style_path if style_path.exists() else None,
        )
        result["steps"]["assemble"] = {
            "success": asm_result["success"],
            "section_count": asm_result.get("section_count", 0),
            "total_chars": asm_result.get("total_chars", 0),
            "hwpx_path": asm_result.get("hwpx_path"),
            "html_path": asm_result.get("html_path"),
        }
        if asm_result["success"]:
            result["summary"]["completed_steps"] += 1
            result["summary"]["section_count"] = asm_result.get("section_count", 0)
            result["summary"]["hwpx_path"] = asm_result.get("hwpx_path")
            result["summary"]["html_path"] = asm_result.get("html_path")
            logger.info(
                "Step 5: 조립 완료 — %d개 섹션, %d자",
                asm_result.get("section_count", 0),
                asm_result.get("total_chars", 0),
            )
        else:
            result["summary"]["failed_steps"].append("assemble")
            result["errors"].extend(asm_result.get("errors", []))
    except Exception as e:
        result["steps"]["assemble"] = {"success": False, "error": str(e)}
        result["summary"]["failed_steps"].append("assemble")
        result["errors"].append(f"assemble 실패: {e}")

    # ── 최종 결과 ────────────────────────────────────────────────
    result["success"] = len(result["summary"]["failed_steps"]) == 0
    return result


def _merge_company_info(
    project_dir: Path,
    company_info_path: Path,
) -> dict[str, Any]:
    """회사 정보 JSON 을 context.json 에 병합합니다."""
    merge_result: dict[str, Any] = {
        "success": False,
        "merged_fields": 0,
        "errors": [],
    }

    context_path = project_dir / "context.json"
    if not context_path.exists():
        # context.json 이 없으면 기본 구조 생성
        context: dict[str, Any] = {
            "project_name": project_dir.name,
            "documents": [],
            "template_analysis": None,
            "announcement_analysis": None,
            "style_profile": None,
            "company_info_found": {"from_docs": {}},
            "missing_info": [],
        }
    else:
        try:
            context = json.loads(context_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            merge_result["errors"].append(f"context.json 읽기 실패: {e}")
            return merge_result

    try:
        company_data = json.loads(company_info_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        merge_result["errors"].append(f"company info 읽기 실패: {e}")
        return merge_result

    # company_info_found 에 병합
    if "company_info_found" not in context:
        context["company_info_found"] = {"from_docs": {}}
    if "from_docs" not in context["company_info_found"]:
        context["company_info_found"]["from_docs"] = {}

    merged = 0
    for key, value in company_data.items():
        if key.startswith("_"):
            continue  # _comments 등 메타데이터 스킵
        if value is not None and value != "" and value != [] and value != 0:
            context["company_info_found"]["from_docs"][key] = value
            merged += 1

    # missing_info 재계산
    from sandoc.extract import _determine_missing_info

    found_info = context["company_info_found"]["from_docs"]
    context["missing_info"] = _determine_missing_info(found_info)

    # 저장
    context_path.write_text(
        json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # missing_info.json 업데이트
    missing_path = project_dir / "missing_info.json"
    missing_info_output = {
        "project_name": context.get("project_name", project_dir.name),
        "missing_fields": context["missing_info"],
        "total_missing": len(context["missing_info"]),
        "instructions": "아래 항목들은 아직 미입력된 필드입니다.",
    }
    missing_path.write_text(
        json.dumps(missing_info_output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    merge_result["success"] = True
    merge_result["merged_fields"] = merged
    return merge_result
