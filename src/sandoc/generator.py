"""
sandoc.generator — 사업계획서 콘텐츠 생성 파이프라인

공고문 분석 결과, 양식 구조, 회사 정보를 결합하여
사업계획서 각 섹션의 프롬프트를 빌드하고 콘텐츠를 생성합니다.

생성 모드:
  1. prompt — LLM용 프롬프트 빌드 및 저장
  2. fill   — 회사 정보로 템플릿 빈칸 채우기
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from sandoc.schema import CompanyInfo

logger = logging.getLogger(__name__)

# ── 프롬프트 템플릿 디렉토리 ──────────────────────────────────────

PROMPTS_DIR = Path(__file__).parent / "prompts"

# ── 섹션 정의 (창업도약패키지 양식 순서) ───────────────────────────

SECTION_DEFS: list[dict[str, Any]] = [
    {
        "key": "company_overview",
        "title": "기업 개요 및 일반현황",
        "template_file": "01_company_overview.txt",
        "evaluation_category": None,
        "context_key": "기업개요",
    },
    {
        "key": "problem_recognition",
        "title": "1. 문제인식 (Problem)",
        "template_file": "02_problem_recognition.txt",
        "evaluation_category": "문제인식",
        "context_key": "문제인식",
    },
    {
        "key": "solution",
        "title": "2-1. 목표시장(고객) 분석",
        "template_file": "03_solution.txt",
        "evaluation_category": "실현가능성",
        "context_key": "실현가능성",
    },
    {
        "key": "business_model",
        "title": "2-2. 사업화 추진 성과",
        "template_file": "04_business_model.txt",
        "evaluation_category": "실현가능성",
        "context_key": "실현가능성",
    },
    {
        "key": "market_analysis",
        "title": "3-1. 사업화 추진 전략",
        "template_file": "05_market_analysis.txt",
        "evaluation_category": "성장전략",
        "context_key": "성장전략",
    },
    {
        "key": "growth_strategy",
        "title": "3-2. 자금운용 계획",
        "template_file": "06_growth_strategy.txt",
        "evaluation_category": "성장전략",
        "context_key": "재무계획",
    },
    {
        "key": "team",
        "title": "4. 기업 구성 (Team)",
        "template_file": "07_team.txt",
        "evaluation_category": "팀구성",
        "context_key": "팀구성",
    },
    {
        "key": "financial_plan",
        "title": "재무 계획 종합 분석",
        "template_file": "08_financial_plan.txt",
        "evaluation_category": "성장전략",
        "context_key": "재무계획",
    },
    {
        "key": "funding_plan",
        "title": "사업비 집행 계획 (상세)",
        "template_file": "09_funding_plan.txt",
        "evaluation_category": "성장전략",
        "context_key": "재무계획",
    },
]


# ── 데이터 클래스 ─────────────────────────────────────────────────

@dataclass
class GeneratedSection:
    """생성된 섹션."""
    title: str
    content: str
    section_key: str = ""
    section_index: int = 0
    word_count: int = 0
    prompt: str = ""
    evaluation_category: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GeneratedPlan:
    """생성된 사업계획서 전체."""
    title: str = ""
    sections: list[GeneratedSection] = field(default_factory=list)
    total_word_count: int = 0
    company_name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "title": self.title,
            "company_name": self.company_name,
            "total_word_count": self.total_word_count,
            "sections": [
                {
                    "title": s.title,
                    "section_key": s.section_key,
                    "section_index": s.section_index,
                    "evaluation_category": s.evaluation_category,
                    "word_count": s.word_count,
                    "content": s.content,
                    "prompt": s.prompt,
                }
                for s in self.sections
            ],
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        """JSON 문자열로 변환."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# ── 핵심 생성기 클래스 ────────────────────────────────────────────

class PlanGenerator:
    """사업계획서 콘텐츠 생성기."""

    # 4대 평가항목 및 배점 기준 (2025 창업도약패키지)
    EVALUATION_CRITERIA = {
        "문제인식": {
            "description": "창업아이템 개발 동기(필요성) 및 현황 등",
            "min_score": 60,
            "note": "60점 미만 탈락",
        },
        "실현가능성": {
            "description": "창업아이템 목표시장(고객) 분석, 시장진입 현황 등",
            "min_score": 60,
            "note": "60점 미만 탈락",
        },
        "성장전략": {
            "description": "창업아이템 사업화 추진 전략 및 자금 운용 계획 등",
            "min_score": 60,
            "note": "60점 미만 탈락",
        },
        "팀구성": {
            "description": "기업 구성 및 보유 역량, 보유 인프라 활용 계획 등",
            "min_score": 60,
            "note": "60점 미만 탈락",
        },
    }

    # 가점 기준
    BONUS_CRITERIA = {
        "투자유치": {
            "description": "최근 1년 이내 5억원(현금) 이상 투자유치 실적",
            "bonus_points": 1,
            "period": "'24.2.20.~'25.2.19.",
        },
    }

    def __init__(
        self,
        company_info: CompanyInfo,
        template_analysis: dict[str, Any] | None = None,
        announcement_analysis: dict[str, Any] | None = None,
        style_profile: dict[str, Any] | None = None,
    ):
        self.company = company_info
        self.template = template_analysis or {}
        self.announcement = announcement_analysis or {}
        self.style = style_profile or {}

    def build_prompt(self, section_key: str) -> str:
        """
        특정 섹션의 LLM 프롬프트를 빌드합니다.

        Args:
            section_key: 섹션 키 (SECTION_DEFS의 key)

        Returns:
            완성된 프롬프트 문자열
        """
        section_def = self._get_section_def(section_key)
        if section_def is None:
            raise ValueError(f"알 수 없는 섹션: {section_key}")

        # 프롬프트 템플릿 로드
        template_path = PROMPTS_DIR / section_def["template_file"]
        if not template_path.exists():
            raise FileNotFoundError(f"프롬프트 템플릿 없음: {template_path}")

        template_text = template_path.read_text(encoding="utf-8")

        # 변수 치환 맵 생성
        var_map = self._build_variable_map(section_def)

        # 템플릿 변수 치환
        prompt = self._substitute_variables(template_text, var_map)

        return prompt

    def generate_section(self, section_key: str) -> GeneratedSection:
        """
        특정 섹션의 콘텐츠를 생성합니다.

        현재는 fill-in-the-blank 모드:
        프롬프트를 빌드하고 회사 정보로 빈칸을 채운 콘텐츠를 생성합니다.
        향후 LLM API 연동 시 프롬프트를 전송하여 콘텐츠를 생성합니다.

        Args:
            section_key: 섹션 키

        Returns:
            GeneratedSection: 생성된 섹션
        """
        section_def = self._get_section_def(section_key)
        if section_def is None:
            raise ValueError(f"알 수 없는 섹션: {section_key}")

        # 프롬프트 빌드
        prompt = self.build_prompt(section_key)

        # fill-in-the-blank 콘텐츠 생성
        content = self._fill_content(section_def)

        section = GeneratedSection(
            title=section_def["title"],
            content=content,
            section_key=section_key,
            section_index=self._get_section_index(section_key),
            word_count=len(content),
            prompt=prompt,
            evaluation_category=section_def.get("evaluation_category") or "",
            metadata={
                "mode": "fill",
                "evaluation_criteria": self.EVALUATION_CRITERIA.get(
                    section_def.get("evaluation_category") or "", {}
                ),
            },
        )

        logger.info("섹션 생성 완료: %s (%d자)", section.title, section.word_count)
        return section

    def generate_full_plan(self) -> GeneratedPlan:
        """
        사업계획서 전체 초안을 생성합니다.

        Returns:
            GeneratedPlan: 생성된 사업계획서
        """
        plan = GeneratedPlan(
            title=f"{self.company.company_name} 사업계획서",
            company_name=self.company.company_name,
            metadata={
                "evaluation_criteria": self.EVALUATION_CRITERIA,
                "bonus_criteria": self.BONUS_CRITERIA,
                "has_investment_bonus": self.company.has_investment_bonus,
            },
        )

        for section_def in SECTION_DEFS:
            section = self.generate_section(section_def["key"])
            plan.sections.append(section)
            plan.total_word_count += section.word_count

        logger.info(
            "사업계획서 전체 생성 완료: %d개 섹션, %d자",
            len(plan.sections),
            plan.total_word_count,
        )
        return plan

    def save_prompts(self, output_dir: str | Path) -> list[Path]:
        """
        각 섹션의 프롬프트를 파일로 저장합니다.

        Args:
            output_dir: 출력 디렉토리

        Returns:
            저장된 파일 경로 목록
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        saved_files: list[Path] = []

        for section_def in SECTION_DEFS:
            prompt = self.build_prompt(section_def["key"])
            filename = f"prompt_{section_def['key']}.md"
            filepath = output_dir / filename
            filepath.write_text(prompt, encoding="utf-8")
            saved_files.append(filepath)
            logger.info("프롬프트 저장: %s", filepath)

        return saved_files

    def save_plan(self, output_path: str | Path) -> Path:
        """
        생성된 사업계획서를 JSON으로 저장합니다.

        Args:
            output_path: 출력 파일 경로

        Returns:
            저장된 파일 경로
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        plan = self.generate_full_plan()
        output_path.write_text(plan.to_json(), encoding="utf-8")

        logger.info("사업계획서 저장: %s", output_path)
        return output_path

    # ── 내부 메서드 ───────────────────────────────────────────────

    def _get_section_def(self, section_key: str) -> dict[str, Any] | None:
        """섹션 정의를 키로 검색."""
        for sd in SECTION_DEFS:
            if sd["key"] == section_key:
                return sd
        return None

    def _get_section_index(self, section_key: str) -> int:
        """섹션 인덱스 반환."""
        for i, sd in enumerate(SECTION_DEFS):
            if sd["key"] == section_key:
                return i
        return -1

    def _build_variable_map(self, section_def: dict[str, Any]) -> dict[str, str]:
        """프롬프트 변수 치환 맵 생성."""
        c = self.company
        var_map: dict[str, str] = {
            # 기본 정보
            "company_name": c.company_name,
            "ceo_name": c.ceo_name,
            "establishment_date": c.establishment_date,
            "business_type": c.business_type,
            "ceo_type": c.ceo_type,
            "employee_count": str(c.employee_count),
            "address": c.address,
            # 아이템 정보
            "item_name": c.item_name,
            "item_category": c.item_category,
            "support_field": c.support_field,
            "tech_field": c.tech_field,
            "item_summary": c.item_summary,
            "product_description": c.product_description,
            # 문제인식
            "problem_background": c.problem_background,
            "problem_statement": c.problem_statement,
            "development_motivation": c.development_motivation,
            "progress_to_date": c.progress_to_date,
            # 시장/경쟁
            "target_market": c.target_market,
            "target_customer": c.target_customer,
            "competitive_advantage": c.competitive_advantage,
            "key_features": c.key_features,
            "competitor_analysis": c.competitor_analysis,
            # 전략
            "business_model": c.business_model,
            "growth_strategy": c.growth_strategy,
            "marketing_plan": c.marketing_plan,
            "mid_term_roadmap": c.mid_term_roadmap,
            "short_term_roadmap": c.short_term_roadmap,
            "deliverables": c.deliverables,
            # 재무
            "funding_amount": f"{c.funding_amount:,}",
            "self_funding_cash": f"{c.self_funding_cash:,}",
            "self_funding_inkind": f"{c.self_funding_inkind:,}",
            "total_budget": f"{c.total_budget:,}",
            "investment_amount": f"{c.investment_amount:,}",
            "has_investment_bonus": "예" if c.has_investment_bonus else "아니오",
            "future_funding_plan": c.future_funding_plan,
            # 팀
            "ceo_background": c.ceo_background,
            # 리스트 필드 (텍스트 변환)
            "revenue_records_text": self._format_revenue_records(c),
            "projected_revenues_text": self._format_projected_revenues(c),
            "milestones_text": self._format_milestones(c),
            "budget_items_text": self._format_budget_items(c),
            "team_members_text": self._format_team_members(c),
            "infrastructure_text": self._format_infrastructure(c),
            "ip_portfolio_text": self._format_ip_portfolio(c),
        }

        return var_map

    def _substitute_variables(self, template: str, var_map: dict[str, str]) -> str:
        """템플릿 내 {variable} 패턴을 값으로 치환."""
        result = template
        for key, value in var_map.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result

    def _fill_content(self, section_def: dict[str, Any]) -> str:
        """fill-in-the-blank 모드로 콘텐츠 생성."""
        key = section_def["key"]

        generators = {
            "company_overview": self._fill_company_overview,
            "problem_recognition": self._fill_problem_recognition,
            "solution": self._fill_solution,
            "business_model": self._fill_business_model,
            "market_analysis": self._fill_market_analysis,
            "growth_strategy": self._fill_growth_strategy,
            "team": self._fill_team,
            "financial_plan": self._fill_financial_plan,
            "funding_plan": self._fill_funding_plan,
        }

        generator = generators.get(key)
        if generator:
            return generator()

        return f"[{section_def['title']}]\n\n이 섹션은 향후 LLM 연동을 통해 자동 생성될 예정입니다.\n"

    # ── Fill 콘텐츠 생성 메서드들 ──────────────────────────────────

    def _fill_company_overview(self) -> str:
        c = self.company
        lines = [
            "□ 신청 및 일반현황",
            "",
            f"◦ 기업명: {c.company_name}",
            f"◦ 대표자: {c.ceo_name}",
            f"◦ 사업자구분: {c.business_type}",
            f"◦ 대표자유형: {c.ceo_type}",
            f"◦ 개업연월일: {c.establishment_date}",
            f"◦ 소재지: {c.address}",
            f"◦ 직원수: {c.employee_count}명",
            "",
            "□ 창업아이템 개요 및 사업화 계획(요약)",
            "",
            f"◦ 창업아이템명: {c.item_name}",
            f"◦ 범주: {c.item_category}",
            f"◦ 지원분야: {c.support_field}",
            f"◦ 전문기술분야: {c.tech_field}",
            "",
            "◦ 아이템 개요",
            f"  - {c.item_summary}",
            "",
            "◦ 제품/서비스 상세",
            f"  - {c.product_description}",
            "",
            "◦ 중장기 사업 로드맵",
            f"  - {c.mid_term_roadmap}",
            "",
            "◦ 협약기간 내 로드맵",
            f"  - {c.short_term_roadmap}",
            "",
            "◦ 산출물 목표",
            f"  - {c.deliverables}",
            "",
            "◦ 사업비 구성",
            f"  - 총사업비: {c.total_budget:,}원",
            f"  - 정부지원금: {c.funding_amount:,}원",
            f"  - 자기부담(현금): {c.self_funding_cash:,}원",
            f"  - 자기부담(현물): {c.self_funding_inkind:,}원",
        ]
        return "\n".join(lines)

    def _fill_problem_recognition(self) -> str:
        c = self.company
        lines = [
            "1. 창업아이템 개발 동기(필요성) 및 현황",
            "",
            "◦ 외부 환경 분석",
            f"  - {c.problem_background}",
            "",
            "◦ 개발 동기 (필요성)",
            f"  - {c.development_motivation}",
            "",
            "◦ 핵심 문제점",
            f"  - {c.problem_statement}",
            "",
            "◦ 추진 경과",
            f"  - {c.progress_to_date}",
        ]
        return "\n".join(lines)

    def _fill_solution(self) -> str:
        c = self.company
        lines = [
            "2-1. 창업아이템 목표시장(고객) 분석",
            "",
            "◦ 목표 시장",
            f"  - {c.target_market}",
            "",
            "◦ 목표 고객",
            f"  - {c.target_customer}",
            "",
            "◦ 핵심 기능/성능",
            f"  - {c.key_features}",
            "",
            "◦ 경쟁사 분석",
            f"  - {c.competitor_analysis}",
            "",
            "◦ 차별적 경쟁 우위",
            f"  - {c.competitive_advantage}",
        ]
        return "\n".join(lines)

    def _fill_business_model(self) -> str:
        c = self.company
        lines = [
            "2-2. 창업아이템 사업화 추진 성과",
            "",
            "◦ 사업 모델",
            f"  - {c.business_model}",
            "",
            "◦ 목표시장별 매출 실적",
        ]
        if c.revenue_records:
            lines.append("  | 순번 | 목표시장(고객) | 제품·서비스 | 진입시기 | 판매량 | 가격 | 발생매출액 |")
            lines.append("  |------|-------------|-----------|---------|-------|------|---------|")
            for i, r in enumerate(c.revenue_records, 1):
                lines.append(
                    f"  | {i} | {r.target_market} | {r.product_service} | "
                    f"{r.entry_date} | {r.volume} | {r.price} | {r.revenue} |"
                )
        else:
            lines.append("  - 매출 실적 정보를 입력하세요.")
        return "\n".join(lines)

    def _fill_market_analysis(self) -> str:
        c = self.company
        lines = [
            "3-1. 창업아이템 사업화 추진 전략",
            "",
            "◦ 성장 전략",
            f"  - {c.growth_strategy}",
            "",
            "◦ 마케팅/판로 전략",
            f"  - {c.marketing_plan}",
            "",
            "◦ 추정 매출 계획",
        ]
        if c.projected_revenues:
            lines.append("  | 순번 | 목표시장(고객) | 제품·서비스 | 진출시기 | 판매량 | 가격 | 판매금액 |")
            lines.append("  |------|-------------|-----------|---------|-------|------|---------|")
            for i, r in enumerate(c.projected_revenues, 1):
                lines.append(
                    f"  | {i} | {r.target_market} | {r.product_service} | "
                    f"{r.launch_date} | {r.volume} | {r.price} | {r.projected_sales} |"
                )
        lines.append("")
        lines.append("◦ 사업 추진 일정")
        if c.milestones:
            lines.append("  | 순번 | 추진내용 | 추진기간 | 세부내용 |")
            lines.append("  |------|---------|---------|---------|")
            for i, m in enumerate(c.milestones, 1):
                lines.append(f"  | {i} | {m.task} | {m.period} | {m.details} |")
        return "\n".join(lines)

    def _fill_growth_strategy(self) -> str:
        c = self.company
        gov_ratio = (c.funding_amount / c.total_budget * 100) if c.total_budget > 0 else 0
        cash_ratio = (c.self_funding_cash / c.total_budget * 100) if c.total_budget > 0 else 0
        inkind_ratio = (c.self_funding_inkind / c.total_budget * 100) if c.total_budget > 0 else 0

        lines = [
            "3-2. 자금운용 계획",
            "",
            "3-2-1. 사업비 집행계획 및 사업비 구성",
            "",
            "◦ 사업비 총괄",
            f"  - 총사업비: {c.total_budget:,}원 (100%)",
            f"  - 정부지원사업비: {c.funding_amount:,}원 ({gov_ratio:.1f}%)",
            f"  - 자기부담(현금): {c.self_funding_cash:,}원 ({cash_ratio:.1f}%)",
            f"  - 자기부담(현물): {c.self_funding_inkind:,}원 ({inkind_ratio:.1f}%)",
            "",
            "◦ 비율 준수 확인",
            f"  - 정부지원 비율: {gov_ratio:.1f}% {'✓ 적정 (70% 이하)' if gov_ratio <= 70 else '⚠ 초과 (70% 이하 필요)'}",
            f"  - 현금 비율: {cash_ratio:.1f}% {'✓ 적정 (10% 이상)' if cash_ratio >= 10 else '⚠ 부족 (10% 이상 필요)'}",
            f"  - 현물 비율: {inkind_ratio:.1f}% {'✓ 적정 (20% 이하)' if inkind_ratio <= 20 else '⚠ 초과 (20% 이하 필요)'}",
            "",
            "◦ 사업비 구성 상세",
        ]
        if c.budget_items:
            lines.append("  | 순번 | 비목 | 산출근거 | 금액(원) | 재원 |")
            lines.append("  |------|------|---------|---------|------|")
            for i, b in enumerate(c.budget_items, 1):
                lines.append(f"  | {i} | {b.category} | {b.description} | {b.amount:,} | {b.source} |")
        lines.extend([
            "",
            "3-2-2. 향후 자금 조달계획",
            "",
            f"◦ {c.future_funding_plan}",
        ])
        return "\n".join(lines)

    def _fill_team(self) -> str:
        c = self.company
        lines = [
            "4. 기업 구성 (Team)",
            "",
            "4-1-1. 대표자 역량",
            "",
            f"◦ {c.ceo_name} 대표",
            f"  - {c.ceo_background}",
            "",
            "4-1-2. 전문 인력 현황",
        ]
        if c.team_members:
            lines.append("  | 고용여부 | 순번 | 직위 | 담당업무 | 보유역량 |")
            lines.append("  |---------|------|------|---------|---------|")
            for i, t in enumerate(c.team_members, 1):
                lines.append(f"  | {t.employment_type} | {i} | {t.position} | {t.role} | {t.experience} |")
        lines.extend(["", "4-2. 보유 인프라 등 활용 계획"])
        if c.infrastructure:
            lines.append("  | 순번 | 유형 | 활용계획 | 위치 |")
            lines.append("  |------|------|---------|------|")
            for i, inf in enumerate(c.infrastructure, 1):
                lines.append(f"  | {i} | {inf.infra_type} | {inf.description} | {inf.location} |")
        if c.ip_portfolio:
            lines.extend(["", "◦ 산업재산권 현황"])
            lines.append("  | 순번 | 유형 | 산업재산권명 | 등록번호 | 등록일 |")
            lines.append("  |------|------|-----------|---------|--------|")
            for i, ip in enumerate(c.ip_portfolio, 1):
                lines.append(f"  | {i} | {ip.ip_type} | {ip.name} | {ip.registration_no} | {ip.registration_date} |")
        return "\n".join(lines)

    def _fill_financial_plan(self) -> str:
        c = self.company
        budget_ratio = f"{c.funding_amount/c.total_budget*100:.1f}%" if c.total_budget > 0 else "N/A"
        lines = [
            "재무 계획 종합 분석",
            "",
            "◦ 사업비 구성 검증",
            f"  - 총사업비: {c.total_budget:,}원",
            f"  - 정부지원금: {c.funding_amount:,}원 ({budget_ratio})",
            "",
            "◦ 투자유치 가점",
            f"  - 투자유치 금액: {c.investment_amount:,}원",
            f"  - 가점 대상: {'예 (1점 가점)' if c.has_investment_bonus else '아니오 (5억원 미만)'}",
        ]
        return "\n".join(lines)

    def _fill_funding_plan(self) -> str:
        c = self.company
        lines = [
            "사업비 집행 계획 (상세)",
            "",
            "◦ 비목별 집행 계획",
        ]
        if c.budget_items:
            for i, b in enumerate(c.budget_items, 1):
                lines.append(f"  {i}. {b.category}: {b.description}")
                lines.append(f"     금액: {b.amount:,}원 ({b.source})")
        return "\n".join(lines)

    # ── 포맷팅 유틸리티 ───────────────────────────────────────────

    @staticmethod
    def _format_revenue_records(c: CompanyInfo) -> str:
        if not c.revenue_records:
            return "(매출 실적 없음)"
        lines = ["| 순번 | 목표시장(고객) | 제품·서비스 | 진입시기 | 판매량 | 가격 | 발생매출액 |",
                  "|------|-------------|-----------|---------|-------|------|---------|"]
        for i, r in enumerate(c.revenue_records, 1):
            lines.append(f"| {i} | {r.target_market} | {r.product_service} | {r.entry_date} | {r.volume} | {r.price} | {r.revenue} |")
        return "\n".join(lines)

    @staticmethod
    def _format_projected_revenues(c: CompanyInfo) -> str:
        if not c.projected_revenues:
            return "(추정 매출 없음)"
        lines = ["| 순번 | 목표시장(고객) | 제품·서비스 | 진출시기 | 판매량 | 가격 | 판매금액 |",
                  "|------|-------------|-----------|---------|-------|------|---------|"]
        for i, r in enumerate(c.projected_revenues, 1):
            lines.append(f"| {i} | {r.target_market} | {r.product_service} | {r.launch_date} | {r.volume} | {r.price} | {r.projected_sales} |")
        return "\n".join(lines)

    @staticmethod
    def _format_milestones(c: CompanyInfo) -> str:
        if not c.milestones:
            return "(추진 일정 없음)"
        lines = ["| 순번 | 추진내용 | 추진기간 | 세부내용 |",
                  "|------|---------|---------|---------|"]
        for i, m in enumerate(c.milestones, 1):
            lines.append(f"| {i} | {m.task} | {m.period} | {m.details} |")
        return "\n".join(lines)

    @staticmethod
    def _format_budget_items(c: CompanyInfo) -> str:
        if not c.budget_items:
            return "(사업비 항목 없음)"
        lines = ["| 순번 | 비목 | 산출근거 | 금액(원) | 재원 |",
                  "|------|------|---------|---------|------|"]
        for i, b in enumerate(c.budget_items, 1):
            lines.append(f"| {i} | {b.category} | {b.description} | {b.amount:,} | {b.source} |")
        return "\n".join(lines)

    @staticmethod
    def _format_team_members(c: CompanyInfo) -> str:
        if not c.team_members:
            return "(팀원 정보 없음)"
        lines = ["| 고용여부 | 순번 | 이름 | 직위 | 담당업무 | 보유역량 |",
                  "|---------|------|------|------|---------|---------|"]
        for i, t in enumerate(c.team_members, 1):
            lines.append(f"| {t.employment_type} | {i} | {t.name} | {t.position} | {t.role} | {t.experience} |")
        return "\n".join(lines)

    @staticmethod
    def _format_infrastructure(c: CompanyInfo) -> str:
        if not c.infrastructure:
            return "(인프라 정보 없음)"
        lines = ["| 순번 | 유형 | 활용계획 | 위치 |",
                  "|------|------|---------|------|"]
        for i, inf in enumerate(c.infrastructure, 1):
            lines.append(f"| {i} | {inf.infra_type} | {inf.description} | {inf.location} |")
        return "\n".join(lines)

    @staticmethod
    def _format_ip_portfolio(c: CompanyInfo) -> str:
        if not c.ip_portfolio:
            return "(지식재산권 없음)"
        lines = ["| 순번 | 유형 | 산업재산권명 | 등록번호 | 등록일 |",
                  "|------|------|-----------|---------|--------|"]
        for i, ip in enumerate(c.ip_portfolio, 1):
            lines.append(f"| {i} | {ip.ip_type} | {ip.name} | {ip.registration_no} | {ip.registration_date} |")
        return "\n".join(lines)


# ── 하위 호환 함수 (기존 CLI에서 사용) ─────────────────────────────

def generate_section(
    section_title: str,
    context: dict[str, Any] | None = None,
    max_words: int = 500,
) -> GeneratedSection:
    """하위 호환용 섹션 생성 함수."""
    return GeneratedSection(
        title=section_title,
        content=f"[{section_title}]\n\n'sandoc generate' 명령어로 전체 파이프라인을 사용하세요.\n",
        word_count=0,
        metadata={"legacy": True},
    )


def generate_plan(
    template_sections: list[str] | None = None,
    context: dict[str, Any] | None = None,
    max_words_per_section: int = 500,
) -> GeneratedPlan:
    """하위 호환용 전체 생성 함수."""
    if template_sections is None:
        template_sections = [
            "1. 창업아이템 개요",
            "2. 시장 분석",
            "3. 사업화 전략",
            "4. 기술 개발 계획",
            "5. 자금 운용 계획",
            "6. 기대 효과",
        ]

    plan = GeneratedPlan(
        title="사업계획서 초안",
        metadata={"legacy": True},
    )

    for i, title in enumerate(template_sections):
        section = generate_section(title, context, max_words_per_section)
        section.section_index = i
        plan.sections.append(section)
        plan.total_word_count += section.word_count

    return plan
