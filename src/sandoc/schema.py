"""
sandoc.schema — 회사 정보 스키마 및 데이터 모델

사업계획서 생성에 필요한 회사 정보를 구조화합니다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class TeamMember:
    """팀 구성원 정보."""
    name: str = ""                   # 이름
    position: str = ""               # 직위
    role: str = ""                   # 담당 업무
    experience: str = ""             # 경력/역량
    employment_type: str = "기고용"   # 기고용 / 채용예정


@dataclass
class InfraItem:
    """보유 인프라 항목."""
    infra_type: str = ""             # 유형 (사무실, 장비, 시설 등)
    description: str = ""            # 활용 계획
    location: str = ""               # 위치


@dataclass
class IPItem:
    """지식재산권 항목."""
    ip_type: str = ""                # 유형 (특허, 상표, 디자인 등)
    name: str = ""                   # 산업재산권명
    registration_no: str = ""        # 등록번호
    registration_date: str = ""      # 등록일


@dataclass
class RevenueRecord:
    """매출 실적 항목."""
    target_market: str = ""          # 목표시장(고객)
    product_service: str = ""        # 제품·서비스
    entry_date: str = ""             # 진입시기
    volume: str = ""                 # 판매량
    price: str = ""                  # 가격
    revenue: str = ""                # 발생매출액


@dataclass
class ProjectedRevenue:
    """추정 매출 항목."""
    target_market: str = ""          # 목표시장(고객)
    product_service: str = ""        # 제품·서비스
    launch_date: str = ""            # 진출시기
    volume: str = ""                 # 판매량
    price: str = ""                  # 가격
    projected_sales: str = ""        # 판매금액


@dataclass
class MilestoneItem:
    """사업 추진 일정 항목."""
    task: str = ""                   # 추진내용
    period: str = ""                 # 추진기간
    details: str = ""                # 세부내용


@dataclass
class BudgetItem:
    """사업비 집행 항목."""
    category: str = ""               # 비목
    description: str = ""            # 산출근거
    amount: int = 0                  # 금액 (원)
    source: str = "정부지원"          # 정부지원 / 자기부담(현금) / 자기부담(현물)


@dataclass
class CompanyInfo:
    """
    사업계획서 생성에 필요한 회사 정보 스키마.

    2025년 창업도약패키지(일반형) 사업계획서 양식에 맞춰 설계.
    """

    # ── 기본 정보 ──────────────────────────────────────────────
    company_name: str = ""                 # 기업명
    ceo_name: str = ""                     # 대표자명
    business_registration_no: str = ""     # 사업자등록번호
    business_type: str = "법인사업자"       # 사업자구분 (개인사업자/법인사업자)
    ceo_type: str = "창업자"               # 대표자유형 (창업자/공동창업자)
    establishment_date: str = ""           # 설립일 (개업연월일)
    employee_count: int = 0                # 직원 수
    address: str = ""                      # 소재지

    # ── 창업아이템 정보 ────────────────────────────────────────
    item_name: str = ""                    # 창업아이템명
    item_category: str = ""                # 아이템 범주/분야
    support_field: str = ""                # 지원분야
    tech_field: str = ""                   # 전문기술분야
    item_summary: str = ""                 # 아이템 개요 (간략)
    product_description: str = ""          # 제품/서비스 상세 설명

    # ── 문제인식 (Problem) ─────────────────────────────────────
    problem_background: str = ""           # 외부/내부 배경
    problem_statement: str = ""            # 문제점 기술
    development_motivation: str = ""       # 개발 동기 (필요성)
    progress_to_date: str = ""             # 추진 경과

    # ── 실현가능성 (Solution) ──────────────────────────────────
    target_market: str = ""                # 목표 시장
    target_customer: str = ""              # 목표 고객
    competitive_advantage: str = ""        # 경쟁 우위 / 차별성
    key_features: str = ""                 # 핵심 기능/성능
    competitor_analysis: str = ""          # 경쟁사 비교 분석
    revenue_records: list[RevenueRecord] = field(default_factory=list)  # 매출 실적

    # ── 성장전략 (Scale-up) ────────────────────────────────────
    business_model: str = ""               # 사업 모델
    growth_strategy: str = ""              # 성장 전략
    marketing_plan: str = ""               # 마케팅/판로 전략
    projected_revenues: list[ProjectedRevenue] = field(default_factory=list)  # 추정 매출
    milestones: list[MilestoneItem] = field(default_factory=list)  # 추진 일정
    mid_term_roadmap: str = ""             # 중장기 사업 로드맵
    short_term_roadmap: str = ""           # 협약기간 내 로드맵
    deliverables: str = ""                 # 산출물 목표

    # ── 자금 계획 ──────────────────────────────────────────────
    funding_amount: int = 0                # 신청 금액 (정부지원금)
    self_funding_cash: int = 0             # 자기부담 (현금)
    self_funding_inkind: int = 0           # 자기부담 (현물)
    budget_items: list[BudgetItem] = field(default_factory=list)  # 사업비 항목
    future_funding_plan: str = ""          # 향후 자금 조달 계획
    success_return_type: bool = False      # 성공환원형 신청 여부

    # ── 팀 구성 (Team) ─────────────────────────────────────────
    ceo_background: str = ""               # 대표자 역량/이력
    team_members: list[TeamMember] = field(default_factory=list)  # 팀 구성원

    # ── 인프라 / 지식재산권 ────────────────────────────────────
    infrastructure: list[InfraItem] = field(default_factory=list)  # 보유 인프라
    ip_portfolio: list[IPItem] = field(default_factory=list)       # 지식재산권

    # ── 투자 실적 (가점용) ─────────────────────────────────────
    investment_amount: int = 0             # 투자유치 금액
    investment_date: str = ""              # 투자계약일
    investor_name: str = ""                # 투자자명

    # ── 기타 ───────────────────────────────────────────────────
    additional_info: dict[str, Any] = field(default_factory=dict)

    # ── 직렬화 ─────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """JSON 문자열로 변환."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompanyInfo:
        """딕셔너리에서 CompanyInfo 생성."""
        # 중첩 dataclass 처리
        nested_mappings = {
            "team_members": TeamMember,
            "infrastructure": InfraItem,
            "ip_portfolio": IPItem,
            "revenue_records": RevenueRecord,
            "projected_revenues": ProjectedRevenue,
            "milestones": MilestoneItem,
            "budget_items": BudgetItem,
        }
        processed = dict(data)
        for field_name, cls_type in nested_mappings.items():
            if field_name in processed and isinstance(processed[field_name], list):
                processed[field_name] = [
                    cls_type(**item) if isinstance(item, dict) else item
                    for item in processed[field_name]
                ]
        # CompanyInfo 필드에 없는 키 제거
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in processed.items() if k in valid_fields}
        return cls(**filtered)

    @classmethod
    def from_json(cls, json_str: str) -> CompanyInfo:
        """JSON 문자열에서 CompanyInfo 생성."""
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def from_file(cls, path: str | Path) -> CompanyInfo:
        """JSON 파일에서 CompanyInfo 로드."""
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def save(self, path: str | Path) -> None:
        """JSON 파일로 저장."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")

    @property
    def total_budget(self) -> int:
        """총 사업비."""
        return self.funding_amount + self.self_funding_cash + self.self_funding_inkind

    @property
    def has_investment_bonus(self) -> bool:
        """5억원 이상 투자유치 가점 대상 여부."""
        return self.investment_amount >= 500_000_000

    def get_section_context(self, section_name: str) -> dict[str, Any]:
        """특정 섹션에 필요한 컨텍스트 정보 추출."""
        contexts = {
            "기업개요": {
                "company_name": self.company_name,
                "ceo_name": self.ceo_name,
                "establishment_date": self.establishment_date,
                "business_type": self.business_type,
                "employee_count": self.employee_count,
                "item_name": self.item_name,
                "support_field": self.support_field,
            },
            "문제인식": {
                "item_name": self.item_name,
                "problem_background": self.problem_background,
                "problem_statement": self.problem_statement,
                "development_motivation": self.development_motivation,
                "progress_to_date": self.progress_to_date,
                "product_description": self.product_description,
            },
            "실현가능성": {
                "item_name": self.item_name,
                "target_market": self.target_market,
                "target_customer": self.target_customer,
                "competitive_advantage": self.competitive_advantage,
                "key_features": self.key_features,
                "competitor_analysis": self.competitor_analysis,
                "revenue_records": [asdict(r) for r in self.revenue_records],
            },
            "성장전략": {
                "item_name": self.item_name,
                "business_model": self.business_model,
                "growth_strategy": self.growth_strategy,
                "marketing_plan": self.marketing_plan,
                "projected_revenues": [asdict(r) for r in self.projected_revenues],
                "milestones": [asdict(m) for m in self.milestones],
                "mid_term_roadmap": self.mid_term_roadmap,
            },
            "팀구성": {
                "ceo_name": self.ceo_name,
                "ceo_background": self.ceo_background,
                "team_members": [asdict(t) for t in self.team_members],
                "infrastructure": [asdict(i) for i in self.infrastructure],
                "ip_portfolio": [asdict(ip) for ip in self.ip_portfolio],
            },
            "재무계획": {
                "funding_amount": self.funding_amount,
                "self_funding_cash": self.self_funding_cash,
                "self_funding_inkind": self.self_funding_inkind,
                "total_budget": self.total_budget,
                "budget_items": [asdict(b) for b in self.budget_items],
                "future_funding_plan": self.future_funding_plan,
            },
        }
        return contexts.get(section_name, self.to_dict())


def create_sample_company() -> CompanyInfo:
    """테스트/데모용 샘플 회사 정보 생성."""
    return CompanyInfo(
        company_name="(주)스마트팜테크",
        ceo_name="김창업",
        business_registration_no="123-45-67890",
        business_type="법인사업자",
        ceo_type="창업자",
        establishment_date="2021-06-15",
        employee_count=12,
        address="서울특별시 강남구 테헤란로 123, 4층",

        item_name="AI 기반 스마트팜 환경 자동제어 시스템",
        item_category="농업 IoT / AI",
        support_field="정보통신",
        tech_field="인공지능(AI)",
        item_summary="딥러닝 기반 작물 생육환경 분석 및 자동 제어 시스템으로, "
                      "온실 내 온도·습도·CO2·조도를 실시간 모니터링하고 최적 환경을 자동 유지합니다.",
        product_description="본 시스템은 IoT 센서 네트워크와 AI 예측 모델을 결합하여 "
                           "시설원예 농가의 생산성을 30% 이상 향상시키는 스마트팜 솔루션입니다. "
                           "기존 수동 제어 대비 에너지 비용 20% 절감, 수확량 30% 증가 효과를 검증하였습니다.",

        problem_background="국내 시설원예 농가의 80%가 여전히 수동 환경제어에 의존하고 있으며, "
                          "고령화로 인한 농업 인력 감소가 심각한 사회 문제로 대두되고 있습니다.",
        problem_statement="기존 스마트팜 솔루션은 고가(1억원 이상)이며 설치와 운영이 복잡하여 "
                         "중소 농가 보급률이 5% 미만에 그치고 있습니다.",
        development_motivation="대표자는 농업공학 석사 출신으로, 3년간 시설원예 현장에서 "
                              "농가의 환경제어 어려움을 직접 목격하고 AI 기반 저비용 솔루션을 개발하게 되었습니다.",
        progress_to_date="2021년 프로토타입 개발 완료 → 2022년 경기도 시범농가 5곳 실증 완료 → "
                        "2023년 제품 양산 시작 → 2024년 40개 농가에 납품 완료.",

        target_market="국내 시설원예 농가 (약 52,000호) 및 동남아 수출시장",
        target_customer="중소규모 시설원예 농가 (1,000~5,000평), 농업법인, 지자체 스마트팜 사업",
        competitive_advantage="① 기존 대비 60% 저렴한 도입비용 (3,000만원대) "
                             "② 설치 1일 완료 (경쟁사 7일) "
                             "③ AI 자동 최적화로 전문지식 불필요 "
                             "④ 모바일 앱 실시간 모니터링",
        key_features="딥러닝 작물 생육 예측, IoT 센서 통합제어, 모바일 대시보드, "
                    "이상징후 자동 알림, 에너지 최적화 알고리즘",
        competitor_analysis="A사(대기업): 고가(1.5억), 대형 농가 전용 / "
                           "B사(스타트업): 센서만 제공, AI 없음 / "
                           "C사(해외): 한국 작물 데이터 부족, AS 어려움",

        revenue_records=[
            RevenueRecord("시설원예 농가", "스마트팜 시스템", "2023-03", "15대", "3,000만원", "4.5억원"),
            RevenueRecord("농업법인", "스마트팜 시스템+유지보수", "2023-06", "10대", "3,500만원", "3.5억원"),
            RevenueRecord("지자체 사업", "스마트팜 패키지", "2024-01", "15대", "2,800만원", "4.2억원"),
        ],

        business_model="하드웨어(IoT 장비) 판매 + SaaS 월정액 구독(모니터링/AI) + 유지보수 서비스",
        growth_strategy="2025년 국내 100농가 추가 확보 → 2026년 베트남/태국 수출 → "
                       "2027년 데이터 기반 농산물 유통 플랫폼 연계",
        marketing_plan="① 지자체 스마트팜 시범사업 수주 ② 농업박람회/전시회 참가 "
                      "③ 성공 농가 레퍼런스 마케팅 ④ 농협·농업기술센터 제휴",

        projected_revenues=[
            ProjectedRevenue("시설원예 농가", "스마트팜 시스템", "2025-06", "30대", "3,000만원", "9억원"),
            ProjectedRevenue("농업법인", "시스템+SaaS", "2025-07", "20대", "3,500만원", "7억원"),
            ProjectedRevenue("해외수출", "수출형 시스템", "2025-09", "10대", "2,500만원", "2.5억원"),
        ],

        milestones=[
            MilestoneItem("AI 모델 v3.0 개발", "2025.06~08", "작물별 특화 AI 모델 고도화"),
            MilestoneItem("양산 체계 구축", "2025.07~09", "생산 단가 20% 절감"),
            MilestoneItem("베트남 실증 테스트", "2025.09~11", "현지 3개 농가 실증"),
            MilestoneItem("마케팅 캠페인", "2025.06~2026.02", "전시회 3회, 레퍼런스 사례집 제작"),
        ],
        mid_term_roadmap="2025: 국내 시장 점유율 5% 달성 → 2026: 동남아 수출 시작 → "
                        "2027: 데이터 플랫폼 론칭 → 2028: 매출 100억원 달성",
        short_term_roadmap="AI v3.0 개발 → 양산 최적화 → 해외 실증 → 신규 고객 100농가 확보",
        deliverables="AI 제어 모듈 v3.0, 수출형 제품 1종, 베트남 실증 보고서",

        funding_amount=200_000_000,
        self_funding_cash=30_000_000,
        self_funding_inkind=55_000_000,
        budget_items=[
            BudgetItem("재료비", "IoT 센서 모듈 부품 구입", 50_000_000, "정부지원"),
            BudgetItem("외주용역비", "AI 모델 검증 및 인증", 40_000_000, "정부지원"),
            BudgetItem("인건비", "개발인력 2인 인건비 (10개월)", 60_000_000, "정부지원"),
            BudgetItem("기자재구입비", "테스트 장비 및 서버", 30_000_000, "정부지원"),
            BudgetItem("마케팅비", "전시회 참가, 홍보물 제작", 20_000_000, "정부지원"),
            BudgetItem("자기부담(현금)", "운영비 및 기타", 30_000_000, "자기부담(현금)"),
            BudgetItem("자기부담(현물)", "기보유 장비, 사무공간", 55_000_000, "자기부담(현물)"),
        ],
        future_funding_plan="시리즈 A 투자유치 (2025 하반기, 목표 30억원) 및 기술보증기금 추가 융자",
        success_return_type=False,

        ceo_background="서울대 농업공학 석사, 전 삼성SDS IoT사업부 5년 근무, "
                      "스마트팜 관련 특허 3건 보유, 농업IoT 학술논문 2편 게재",
        team_members=[
            TeamMember("이개발", "CTO", "AI/ML 모델 개발", "KAIST 전산학 박사, AI 개발 8년", "기고용"),
            TeamMember("박하드", "HW팀장", "IoT 하드웨어 설계", "임베디드 시스템 개발 10년", "기고용"),
            TeamMember("최영업", "영업이사", "영업/마케팅", "농업분야 B2B 영업 7년", "기고용"),
            TeamMember("정데이", "데이터엔지니어", "데이터 파이프라인", "빅데이터 처리 5년", "채용예정"),
        ],

        infrastructure=[
            InfraItem("사무실", "본사 사무공간 및 개발실", "서울 강남구"),
            InfraItem("실험실", "IoT 장비 테스트 랩", "경기도 수원시"),
            InfraItem("실증농장", "시범 운영 농장 (제휴)", "전남 나주시"),
        ],

        ip_portfolio=[
            IPItem("특허", "AI 기반 온실 환경 자동제어 방법", "10-2345678", "2023-05-10"),
            IPItem("특허", "IoT 센서 네트워크 통합 관제 시스템", "10-2345679", "2023-08-15"),
            IPItem("특허", "작물 생육 예측 딥러닝 모델", "10-2345680", "2024-01-20"),
        ],

        investment_amount=0,
        investment_date="",
        investor_name="",
    )
