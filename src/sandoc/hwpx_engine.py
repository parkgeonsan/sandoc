"""
sandoc.hwpx_engine — HWPX 변환 및 편집 엔진

HWP → HWPX 변환, HWPX XML 편집, 향후 hwpx-mcp-server 연동을 위한 모듈.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)


# ── HWP → HWPX 변환 ──────────────────────────────────────────────

def hwp_to_hwpx(
    hwp_path: str | Path,
    output_path: str | Path | None = None,
) -> Path:
    """
    HWP 파일을 HWPX(ODF-like XML 패키지)로 변환합니다.

    pyhwp 의 hwp5html 도구를 사용합니다.
    향후 직접 변환 엔진으로 교체 예정.

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

    # pyhwp의 hwp5html 사용 시도
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
        logger.info("HWP → HWPX 변환 완료: %s → %s", hwp_path, output_path)
        return output_path

    except FileNotFoundError:
        raise RuntimeError(
            "hwp5html 명령을 찾을 수 없습니다. "
            "pip install pyhwp 로 설치하세요. "
            "또는 pip install sandoc[hwpx] 로 설치하세요."
        )


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


# ── HWPX-MCP 서버 연동 (스텁) ────────────────────────────────────

class HwpxMcpClient:
    """
    향후 hwpx-mcp-server 연동을 위한 클라이언트 스텁.

    MCP (Model Context Protocol) 서버를 통해 HWPX 파일을
    프로그래매틱하게 생성/편집할 수 있는 인터페이스.
    """

    def __init__(self, server_url: str = "http://localhost:3000"):
        self.server_url = server_url
        self._connected = False

    def connect(self) -> bool:
        """MCP 서버에 연결합니다. (스텁)"""
        logger.warning("HwpxMcpClient.connect(): MCP 서버 연동은 아직 구현되지 않았습니다.")
        return False

    def create_document(self, template_path: str | None = None) -> dict[str, Any]:
        """새 HWPX 문서를 생성합니다. (스텁)"""
        raise NotImplementedError("MCP 서버 연동이 아직 구현되지 않았습니다.")

    def insert_text(self, doc_id: str, text: str, position: int = -1) -> bool:
        """문서에 텍스트를 삽입합니다. (스텁)"""
        raise NotImplementedError("MCP 서버 연동이 아직 구현되지 않았습니다.")

    def insert_table(
        self,
        doc_id: str,
        rows: int,
        cols: int,
        data: list[list[str]] | None = None,
    ) -> bool:
        """문서에 표를 삽입합니다. (스텁)"""
        raise NotImplementedError("MCP 서버 연동이 아직 구현되지 않았습니다.")

    def apply_style(self, doc_id: str, style_name: str) -> bool:
        """문서에 스타일을 적용합니다. (스텁)"""
        raise NotImplementedError("MCP 서버 연동이 아직 구현되지 않았습니다.")

    def save(self, doc_id: str, output_path: str) -> str:
        """문서를 저장합니다. (스텁)"""
        raise NotImplementedError("MCP 서버 연동이 아직 구현되지 않았습니다.")
