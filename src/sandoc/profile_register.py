"""
sandoc.profile_register -- 기업 프로필 등록

사업자등록증 PDF, 재무제표 등의 문서에서 기업 정보를 추출하여
재사용 가능한 프로필로 저장합니다.

profiles/{회사명}.json 형식으로 저장하며
여러 프로젝트에서 공유할 수 있습니다.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── 사업자등록증에서 추출하는 필드 ──────────────────────────────

REGISTRATION_FIELDS = [
    ("company_name", r"(?:상\s*호|법인명|기업명)[^\S\n]*[:\s]?\s*(.+?)(?:\n|$)"),
    ("ceo_name", r"(?:대\s*표\s*자|성\s*명|대표이사)[^\S\n]*[:\s]?\s*(.+?)(?:\n|$)"),
    ("business_registration_no", r"(?:사업자\s*등록\s*번호|등록번호)[^\S\n]*[:\s]?\s*([\d\-]+)"),
    ("address", r"(?:사업장\s*소재지|소\s*재\s*지|주\s*소)[^\S\n]*[:\s]?\s*(.+?)(?:\n|$)"),
    ("establishment_date", r"(?:개업\s*연월일|설립일|개업일)[^\S\n]*[:\s]?\s*([\d\.\-\/]+)"),
    ("business_type", r"(?:사업자\s*구분|법인구분)[^\S\n]*[:\s]?\s*(.+?)(?:\n|$)"),
]

# 재무제표에서 추출하는 필드
FINANCIAL_FIELDS = [
    ("revenue", r"(?:매출액|매출)[^\S\n]*[:\s]?\s*([\d,]+)\s*(?:원|천원|백만원)?"),
    ("operating_income", r"(?:영업이익|영업손익)[^\S\n]*[:\s]?\s*([\d,\-]+)"),
    ("net_income", r"(?:당기순이익|순이익)[^\S\n]*[:\s]?\s*([\d,\-]+)"),
    ("total_assets", r"(?:자산총계|총자산)[^\S\n]*[:\s]?\s*([\d,]+)"),
    ("total_equity", r"(?:자본총계|총자본)[^\S\n]*[:\s]?\s*([\d,]+)"),
    ("employee_count", r"(?:직원\s*수|종업원\s*수|상시\s*근로자)[^\S\n]*[:\s]?\s*(\d+)\s*명?"),
]


def _extract_text_from_pdf(pdf_path: Path) -> str:
    """PDF에서 텍스트 추출."""
    try:
        import pdfplumber
        text_parts: list[str] = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages[:10]:  # 최대 10페이지
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts)
    except ImportError:
        logger.warning("pdfplumber가 설치되지 않았습니다.")
        return ""
    except Exception as e:
        logger.error("PDF 읽기 오류 (%s): %s", pdf_path.name, e)
        return ""


def _extract_text_from_txt(file_path: Path) -> str:
    """텍스트/JSON 파일에서 읽기."""
    try:
        return file_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error("파일 읽기 오류 (%s): %s", file_path.name, e)
        return ""


def _extract_fields(text: str, field_patterns: list[tuple[str, str]]) -> dict[str, str]:
    """정규식 패턴으로 필드 추출."""
    result: dict[str, str] = {}
    for field_name, pattern in field_patterns:
        m = re.search(pattern, text)
        if m:
            value = m.group(1).strip()
            if value:
                result[field_name] = value
    return result


def _scan_docs_folder(docs_dir: Path) -> dict[str, list[Path]]:
    """docs 폴더를 스캔하여 문서 유형별로 분류."""
    categories: dict[str, list[Path]] = {
        "사업자등록증": [],
        "재무제표": [],
        "기타": [],
    }

    for f in sorted(docs_dir.iterdir()):
        if not f.is_file():
            continue

        name_lower = f.name.lower()

        if any(kw in name_lower for kw in ["사업자등록", "등록증", "registration"]):
            categories["사업자등록증"].append(f)
        elif any(kw in name_lower for kw in ["재무", "결산", "financial", "손익", "대차"]):
            categories["재무제표"].append(f)
        elif f.suffix.lower() in (".pdf", ".txt", ".json"):
            categories["기타"].append(f)

    return categories


def extract_company_info(docs: list[Path]) -> dict[str, Any]:
    """문서 목록에서 기업 정보를 추출."""
    company_info: dict[str, Any] = {}
    financial_info: dict[str, Any] = {}

    for doc in docs:
        ext = doc.suffix.lower()

        if ext == ".pdf":
            text = _extract_text_from_pdf(doc)
        elif ext in (".txt", ".json", ".md"):
            text = _extract_text_from_txt(doc)
        else:
            continue

        if not text:
            continue

        # 사업자등록증 필드 추출
        reg_fields = _extract_fields(text, REGISTRATION_FIELDS)
        for k, v in reg_fields.items():
            if k not in company_info:
                company_info[k] = v

        # 재무제표 필드 추출
        fin_fields = _extract_fields(text, FINANCIAL_FIELDS)
        for k, v in fin_fields.items():
            if k not in financial_info:
                financial_info[k] = v

    if financial_info:
        company_info["financial_data"] = financial_info

    return company_info


def create_profile_from_info(
    company_info: dict[str, Any],
    profile_name: str | None = None,
) -> dict[str, Any]:
    """추출된 기업 정보에서 프로필 JSON 생성."""
    name = profile_name or company_info.get("company_name", "unknown")

    profile: dict[str, Any] = {
        "profile_name": name,
        "company_name": company_info.get("company_name", ""),
        "ceo_name": company_info.get("ceo_name", ""),
        "business_registration_no": company_info.get("business_registration_no", ""),
        "business_type": company_info.get("business_type", "법인사업자"),
        "ceo_type": "창업자",
        "establishment_date": company_info.get("establishment_date", ""),
        "employee_count": int(company_info.get("employee_count", 0) or 0),
        "address": company_info.get("address", ""),
        "financial_data": company_info.get("financial_data", {}),
        "source_documents": [],
    }

    return profile


def save_profile(
    profile: dict[str, Any],
    profiles_dir: Path,
) -> Path:
    """프로필을 JSON 파일로 저장."""
    profiles_dir.mkdir(parents=True, exist_ok=True)

    # 파일명 안전하게 처리
    name = profile.get("profile_name", "unknown")
    safe_name = re.sub(r'[\\/:*?"<>|]', "_", name)
    profile_path = profiles_dir / f"{safe_name}.json"

    profile_path.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return profile_path


def run_profile_register(
    docs_path: Path | None = None,
    profile_name: str | None = None,
    profiles_dir: Path | None = None,
    company_name: str | None = None,
    ceo_name: str | None = None,
) -> dict[str, Any]:
    """
    기업 프로필을 등록합니다.

    Args:
        docs_path: 문서가 있는 디렉토리 또는 단일 문서 경로
        profile_name: 프로필 이름 (기본: 회사명)
        profiles_dir: 프로필 저장 디렉토리 (기본: ./profiles/)
        company_name: 수동 입력 회사명
        ceo_name: 수동 입력 대표자명

    Returns:
        등록 결과 딕셔너리
    """
    result: dict[str, Any] = {
        "success": False,
        "profile_path": "",
        "extracted_fields": [],
        "errors": [],
    }

    try:
        if profiles_dir is None:
            profiles_dir = Path("profiles")

        # 문서 수집
        docs: list[Path] = []
        if docs_path is not None:
            docs_path = Path(docs_path)
            if docs_path.is_dir():
                for f in sorted(docs_path.iterdir()):
                    if f.is_file() and f.suffix.lower() in (".pdf", ".txt", ".json", ".md"):
                        docs.append(f)
            elif docs_path.is_file():
                docs.append(docs_path)

        # 문서에서 정보 추출
        company_info: dict[str, Any] = {}
        if docs:
            company_info = extract_company_info(docs)
            result["source_documents"] = [str(d) for d in docs]
            logger.info("문서 %d개에서 정보 추출 완료", len(docs))

        # 수동 입력 값 우선 적용
        if company_name:
            company_info["company_name"] = company_name
        if ceo_name:
            company_info["ceo_name"] = ceo_name

        # 프로필명 결정
        if profile_name is None:
            profile_name = company_info.get("company_name", "unknown")

        # 프로필 생성
        profile = create_profile_from_info(company_info, profile_name)
        profile["source_documents"] = [str(d) for d in docs]

        # 저장
        profile_path = save_profile(profile, profiles_dir)

        result["success"] = True
        result["profile_path"] = str(profile_path)
        result["profile"] = profile
        result["extracted_fields"] = list(company_info.keys())

        logger.info("프로필 저장 완료: %s", profile_path)

    except Exception as e:
        result["success"] = False
        result["errors"].append(str(e))
        logger.error("프로필 등록 오류: %s", e)

    return result
