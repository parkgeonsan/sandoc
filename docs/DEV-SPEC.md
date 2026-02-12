# sandoc 개발 명세서

## 개요
Claude Code로 개발하는 사업계획서 자동 작성 시스템.
PLAN.md의 기획을 구현하기 위한 개발 명세.

---

## 기술 스택

| 구분 | 기술 | 이유 |
|------|------|------|
| 런타임 | Claude Code CLI | 메인 개발 환경 |
| 문서엔진 | hwpx-mcp-server (Python) | HWP/HWPX 읽기/쓰기 |
| MCP 런타임 | uv (uvx) | hwpx-mcp 실행 |
| 에이전트 | Claude Code Subagents | 4인 팀 구성 |
| 설정 | JSON | config/settings.json |
| 데이터 | Markdown + JSON | 프로필, 지식, 컨텍스트 |
| 버전관리 | Git | 프로젝트 코드 |
| 차트/시각화 | mcp-server-chart + mcp-echarts + mcp-mermaid | 아래 상세 |

---

## 🎨 시각 자료 MCP 스택

사업계획서에 들어가는 시각 자료(차트, 다이어그램, 인포그래픽)를 
실제 이미지로 생성하기 위한 MCP 도구 조합.

### 추천 구성 (3 MCP 조합)

#### 1. 📊 mcp-server-chart (AntVis) — 메인 차트 엔진
```
repo: https://github.com/antvis/mcp-server-chart
설치: npx @anthropic-ai/create-mcp mcp-server-chart
기능: 26+ 차트 유형 지원
용도: 사업계획서의 핵심 데이터 차트

지원 차트:
├── 막대/컬럼 차트 (bar/column) — 매출 비교, 시장 규모
├── 라인 차트 (line) — 성장 추세, 매출 추이
├── 영역 차트 (area) — 누적 데이터, 시장 점유율 변화
├── 원형/도넛 차트 (pie/donut) — 예산 비율, 시장 점유율
├── 산점도 (scatter) — 경쟁사 포지셔닝
├── 박스 플롯 (boxplot) — 데이터 분포
├── 히트맵 (heatmap) — 시간대별 분석
├── 워터폴 차트 (waterfall) — 매출 증감 분석
├── 레이더 차트 (radar) — 경쟁력 비교 (기술/가격/서비스)
├── 트리맵 (treemap) — 비용 구조, 사업 영역 비중
├── 워드 클라우드 — 핵심 키워드 시각화
├── 이중축 차트 (dual-axes) — 매출+이익률 동시 표시
├── 퍼널 (funnel) — 전환율, 고객 여정
└── 기타: 버블, 히스토그램, sankey, gauge 등

장점:
- 가장 많은 차트 유형 (26+)
- PNG 이미지로 직접 출력 → HWP 삽입 가능
- 한국어 레이블 지원
- 커스터마이징 옵션 풍부

설정:
{
  "mcpServers": {
    "chart": {
      "command": "npx",
      "args": ["-y", "@antv/mcp-server-chart"]
    }
  }
}
```

#### 2. 📈 mcp-echarts — 고급 차트 (ECharts 기반)
```
repo: https://github.com/hustcc/mcp-echarts
설치: npx mcp-echarts
기능: Apache ECharts 기반 차트 생성
용도: 복잡한 데이터 시각화, 인터랙티브 차트

AntVis 대비 장점:
├── 간트 차트 (사업 추진일정표에 핵심!)
├── 3D 차트
├── 지도 차트 (지역별 분석)
├── 커스텀 인포그래픽
├── 게이지 차트 (목표 달성률)
└── 복합 차트 (여러 유형 겹치기)

사업계획서 활용:
- 추진일정표 (간트) ← 가장 중요
- 목표 달성률 게이지
- 지역별 사업 범위 지도
- 복합 데이터 분석

설정:
{
  "mcpServers": {
    "echarts": {
      "command": "npx",
      "args": ["-y", "mcp-echarts"]
    }
  }
}
```

#### 3. 🔀 mcp-mermaid — 다이어그램 & 플로우차트
```
repo: https://github.com/hustcc/mcp-mermaid
설치: npx mcp-mermaid
기능: Mermaid 문법 → 이미지 변환
용도: 구조도, 플로우차트, 마인드맵

지원 다이어그램:
├── 플로우차트 — 서비스 프로세스, 기술 흐름
├── 시퀀스 다이어그램 — API 흐름, 사용자 여정
├── 클래스 다이어그램 — 시스템 구조
├── 간트 차트 — 추진일정 (간단한 것)
├── 마인드맵 — 사업 구조, 핵심 역량
├── 파이 차트 — 간단한 비율
├── 조직도 (org chart) — 팀 구성
├── 상태 다이어그램 — 제품 상태 흐름
├── ER 다이어그램 — 데이터 구조
└── 타임라인 — 연혁, 로드맵

장점:
- 텍스트 기반 → 버전 관리 용이
- 출력: SVG, PNG, base64, URL
- file 모드로 디스크에 직접 저장
- 오류 검증 + 자동 수정

설정:
{
  "mcpServers": {
    "mermaid": {
      "command": "npx",
      "args": ["-y", "mcp-mermaid"]
    }
  }
}
```

### 보조 도구 (선택)

#### 4. 📐 mcp-diagram-server — 다이어그램 라이브러리
```
repo: https://github.com/angrysky56/mcp-diagram-server
용도: 다이어그램 영구 저장/재활용 라이브러리
특징:
- 자동 저장 + 메타데이터 추적
- JSON/CSV/마크다운 → 다이어그램 변환
- 마인드맵 특화
활용: knowledge/에 다이어그램 패턴 축적
```

### 3 MCP 역할 분담

```
시각 자료 유형              │ 담당 MCP              │ 이유
───────────────────────────┼──────────────────────┼──────────
매출 추이 라인차트          │ 📊 mcp-server-chart  │ 가장 깔끔
시장 규모 막대차트          │ 📊 mcp-server-chart  │ 다양한 옵션
예산 비율 원형차트          │ 📊 mcp-server-chart  │ 커스터마이징
경쟁사 비교 레이더          │ 📊 mcp-server-chart  │ 레이더 특화
매출+이익 이중축            │ 📊 mcp-server-chart  │ 이중축 지원
추진일정 간트차트           │ 📈 mcp-echarts       │ 간트 특화
목표 달성 게이지            │ 📈 mcp-echarts       │ 게이지 특화
지역 분포 지도              │ 📈 mcp-echarts       │ 지도 지원
기술 아키텍처도             │ 🔀 mcp-mermaid       │ 구조도 특화
서비스 프로세스             │ 🔀 mcp-mermaid       │ 플로우 특화
조직도                     │ 🔀 mcp-mermaid       │ org chart
사업 구조 마인드맵          │ 🔀 mcp-mermaid       │ 마인드맵
회사 연혁 타임라인          │ 🔀 mcp-mermaid       │ 타임라인
```

---

## 🛠️ Claude Code Skills 활용

sandoc에서 활용할 공식/커뮤니티 Claude Code Skills.
`.claude/skills/`에 설치하여 subagent들이 사용.

### 공식 스킬 (Anthropic)

#### 📄 docx — Word 문서 생성/편집
```
repo: https://github.com/anthropics/skills/tree/main/skills/docx
용도: HWP 출력 실패 시 DOCX 폴백, DOCX → HWP 변환 파이프라인
활용: 문서관(docengine)이 DOCX 중간 포맷으로 활용
```

#### 📊 xlsx — Excel 스프레드시트
```
repo: https://github.com/anthropics/skills/tree/main/skills/xlsx
용도: 재무 테이블(매출추정표, 예산서) 생성, 수식 기반 자동 계산
활용: 비주얼관(visualist)이 재무 데이터 정밀 계산
  - 예산 합계 자동 검증
  - 매출 추정 시나리오 (보수적/기본/낙관)
  - 손익분기점 자동 계산
  - CSV/표 데이터 가공
```

#### 📑 pdf — PDF 추출/생성
```
repo: https://github.com/anthropics/skills/tree/main/skills/pdf
용도: PDF 서류 텍스트 추출, 최종본 PDF 출력
활용: 분석관(analyst)이 PDF 서류 파싱
  - 사업자등록증 PDF 텍스트 추출
  - 회사소개서 PDF 파싱
  - 재무제표 PDF 파싱
```

#### 📝 doc-coauthoring — 협업 문서 편집
```
repo: https://github.com/anthropics/skills/tree/main/skills/doc-coauthoring
용도: 사업계획서 섹션별 분담 작성 시 협업 관리
활용: PM이 작성관/비주얼관 작업 통합 시 활용
```

#### 🎨 canvas-design — 시각 디자인
```
repo: https://github.com/anthropics/skills/tree/main/skills/canvas-design
용도: 인포그래픽, 커버 페이지, 시각적 강조 요소 디자인
활용: 비주얼관(visualist)이 인포그래픽 이미지 생성
  - 핵심 수치 하이라이트 이미지
  - Before/After 비교 인포그래픽
  - 아이콘 + 텍스트 조합
  - 커버 페이지 디자인
  → PNG 출력 → HWP에 이미지로 삽입
```

#### 🎯 pptx — PowerPoint 생성
```
repo: https://github.com/anthropics/skills/tree/main/skills/pptx
용도: 발표 심사용 PPT 자동 생성 (서면 심사 통과 후)
활용: 사업계획서 → 발표자료 자동 변환
  - 핵심 내용 추출 → 슬라이드 구성
  - 차트/표 재활용
  - 발표 대본 생성
```

### 커뮤니티 스킬

#### 📋 planning-with-files — 파일 기반 계획 관리
```
repo: https://github.com/OthmanAdi/planning-with-files
용도: Manus 스타일 마크다운 계획 관리
활용: PM이 프로젝트 상태/진행 관리
  - context.md 체계적 관리
  - 단계별 체크리스트 추적
  - 작업 상태 실시간 반영
```

#### ✍️ humanizer — AI 흔적 제거
```
repo: https://github.com/blader/humanizer
용도: AI가 생성한 사업계획서 텍스트에서 AI 느낌 제거
활용: 작성관(writer)의 최종 단계
  - AI 특유의 패턴 제거
  - 자연스러운 문체로 후처리
  - 심사위원이 AI 작성 의심 방지
⚠️ 한국어 버전: https://github.com/op7418/Humanizer-zh (중국어지만 참고)
```

#### 🧠 Claudeception — 자율 학습
```
repo: https://github.com/blader/Claudeception
용도: 작업하면서 자동으로 스킬 추출 & 학습
활용: knowledge/ 자동 축적
  - 사업계획서 작성 패턴 자동 추출
  - 효과적 표현 자동 수집
  - 반복 작업 자동화
```

#### 🔍 last30days — 최신 트렌드 조사
```
repo: https://github.com/mvanhorn/last30days-skill
용도: Reddit, X에서 최근 30일 트렌드 조사
활용: 분석관(analyst)의 시장조사 보조
  - 사업 관련 최신 트렌드 파악
  - 시장 동향 데이터 수집
  - 기술 트렌드 근거 자료
```

#### ✏️ oh-my-writing — 콘텐츠 작성 보조
```
repo: https://github.com/z0gSh1u/oh-my-writing-skill
용도: 깊이 있는 콘텐츠 작성 + 리서치 + AI 흔적 최적화
활용: 작성관(writer) 보조
  - 사용자 요구 명확화
  - 심층 리서치 기반 작성
  - AI 흔적 최적화
```

### Skills 설치 구조

```
~/001_Projects/H1-sandoc/
├── .claude/
│   ├── agents/                 # Subagents (팀원)
│   │   ├── analyst.md
│   │   ├── writer.md
│   │   ├── visualist.md
│   │   └── docengine.md
│   └── skills/                 # Skills (도구)
│       ├── docx/               # 공식: DOCX 생성/편집
│       ├── xlsx/               # 공식: Excel 스프레드시트
│       ├── pdf/                # 공식: PDF 추출/생성
│       ├── canvas-design/      # 공식: 시각 디자인/인포그래픽
│       ├── pptx/               # 공식: PPT 생성 (발표 심사용)
│       ├── planning/           # 커뮤니티: 파일 기반 계획
│       ├── humanizer/          # 커뮤니티: AI 흔적 제거
│       └── research/           # 커뮤니티: 트렌드 조사
```

### Subagent ↔ Skill 매핑

```
팀원              │ 사용하는 Skills         │ 사용하는 MCP
──────────────────┼────────────────────────┼──────────────────
📋 분석관(analyst) │ pdf, research          │ hwpx
✍️ 작성관(writer)  │ humanizer              │ -
🎨 비주얼관(visual)│ xlsx, canvas-design    │ chart, echarts, mermaid
📐 문서관(doceng)  │ docx, pptx             │ hwpx
🤖 PM             │ planning               │ -
```

### .mcp.json (통합 설정)

```json
{
  "mcpServers": {
    "hwpx": {
      "command": "uvx",
      "args": ["hwpx-mcp-server"],
      "env": {
        "HWPX_MCP_PAGING_PARA_LIMIT": "500",
        "HWPX_MCP_AUTOBACKUP": "1",
        "HWPX_MCP_HARDENING": "1"
      }
    },
    "chart": {
      "command": "npx",
      "args": ["-y", "@antv/mcp-server-chart"]
    },
    "echarts": {
      "command": "npx",
      "args": ["-y", "mcp-echarts"]
    },
    "mermaid": {
      "command": "npx",
      "args": ["-y", "mcp-mermaid"]
    }
  }
}
```

### 시각 자료 파이프라인

```
[VISUAL: 매출 추이 라인차트]
    │
    ▼
비주얼관 판단: "라인차트 → mcp-server-chart 사용"
    │
    ▼
mcp__chart__generate_line_chart({
  data: [...],
  xField: "연도",
  yField: "매출액",
  title: "연도별 매출 추이",
  unit: "(백만원)"
})
    │
    ▼
PNG 이미지 생성 → output/visuals/charts/매출추이.png
    │
    ▼
문서관: hwpx-mcp로 해당 위치에 이미지 삽입
```

---

## 📁 디렉토리 구조 (최종)

```
~/001_Projects/H1-sandoc/
├── CLAUDE.md                        # PM 동작 지침
├── README.md                        # 프로젝트 소개
├── .gitignore                       # 민감 데이터 제외
│
├── .claude/
│   └── agents/                      # Subagent 정의
│       ├── analyst.md               # 📋 분석관
│       ├── writer.md                # ✍️ 작성관
│       ├── visualist.md             # 🎨 비주얼관
│       └── docengine.md             # 📐 문서관
│
├── config/
│   └── settings.json                # 시스템 설정
│
├── profiles/                        # 회사 프로필 DB
│   ├── _template.md                 # 프로필 템플릿
│   └── (회사명.md)                  # 등록된 프로필
│
├── projects/                        # 사업별 작업 폴더
│   └── (YYYY-사업명)/
│       ├── docs/                    # 입력 서류
│       ├── output/
│       │   ├── drafts/
│       │   │   ├── v1/
│       │   │   ├── v2/
│       │   │   └── current/
│       │   ├── visuals/
│       │   │   ├── tables/
│       │   │   ├── charts/
│       │   │   ├── diagrams/
│       │   │   ├── sources/
│       │   │   └── infographics/
│       │   ├── 사업계획서.hwpx
│       │   └── review.md
│       ├── context.md               # 프로젝트 상태/분석 결과
│       └── style-profile.json       # 양식 서식 프로파일
│
├── knowledge/                       # 축적 지식
│   ├── domain/
│   │   ├── government-writing-style.md
│   │   ├── scoring-system.md
│   │   ├── budget-rules.md
│   │   ├── document-types.md
│   │   └── common-mistakes.md
│   ├── tech/
│   │   ├── hwp-structure.md
│   │   ├── ocr-patterns.md
│   │   └── market-research.md
│   ├── presets/
│   │   ├── classic.md
│   │   ├── engineer.md
│   │   ├── analyst.md
│   │   ├── visionary.md
│   │   ├── proven.md
│   │   ├── disruptor.md
│   │   ├── impact.md
│   │   ├── builder.md
│   │   ├── scaler.md
│   │   ├── global.md
│   │   └── custom/
│   ├── patterns/
│   ├── expressions/
│   ├── scoring/
│   └── lessons.md
│
├── scripts/                         # 유틸리티 스크립트
│   ├── new-project.sh               # 프로젝트 생성
│   ├── scan-docs.sh                 # docs/ 파일 목록
│   └── check-deps.sh               # 의존성 체크
│
├── docs/
│   ├── PLAN.md                      # 기획서
│   └── DEV-SPEC.md                  # 이 파일
│
└── tests/                           # 테스트 데이터
    ├── sample-공고문.hwp
    ├── sample-양식.hwp
    └── sample-사업자등록증.jpg
```

---

## 🔧 기능 명세서

### F-000: 환경 설정 & 초기화

#### F-001: 의존성 설치 확인
```
설명: sandoc 실행에 필요한 도구가 설치되었는지 확인
입력: 없음
처리:
  1. uv 설치 여부 확인 (which uv)
  2. hwpx-mcp-server 실행 가능 여부 (uvx hwpx-mcp-server --help)
  3. Claude Code 설치 여부 (which claude)
  4. 누락된 도구 설치 안내
출력: 의존성 상태 리포트
스크립트: scripts/check-deps.sh
우선순위: P0 (필수)
```

#### F-002: 시스템 설정 초기화
```
설명: config/settings.json 생성 및 기본값 설정
입력: 없음
처리:
  1. config/ 디렉토리 생성
  2. settings.json 기본값 생성
  3. MCP 서버 설정 포함
출력: config/settings.json
우선순위: P0
```

#### F-003: MCP 서버 등록
```
설명: hwpx-mcp-server를 Claude Code MCP에 등록
입력: 없음
처리:
  1. .claude/agents/ 에서 MCP 도구 참조 가능 확인
  2. 프로젝트 레벨 MCP 설정 (.mcp.json)
출력: .mcp.json
우선순위: P0

.mcp.json:
{
  "mcpServers": {
    "hwpx": {
      "command": "uvx",
      "args": ["hwpx-mcp-server"],
      "env": {
        "HWPX_MCP_PAGING_PARA_LIMIT": "500",
        "HWPX_MCP_AUTOBACKUP": "1",
        "HWPX_MCP_HARDENING": "1"
      }
    }
  }
}
```

---

### F-100: 프로필 관리

#### F-101: 프로필 생성 (수동)
```
설명: 사용자 입력으로 회사 프로필 생성
입력: 사용자 대화 (회사명, 대표자, 사업자번호 등)
처리:
  1. _template.md 복사
  2. 순차 질문으로 정보 수집
  3. 필수 필드: 회사명, 대표자, 사업자번호, 업종, 설립일
  4. 선택 필드: 연혁, 재무, 인증, 수행실적
출력: profiles/{회사명}.md
우선순위: P0
```

#### F-102: 프로필 생성 (사업자등록증 OCR)
```
설명: 사업자등록증 이미지에서 자동 추출
입력: 이미지 파일 (JPG/PNG/PDF)
처리:
  1. 이미지 → vision OCR
  2. 필드 자동 매핑:
     - 상호(법인명) → 회사명
     - 대표자 → 대표자
     - 등록번호 → 사업자등록번호
     - 개업년월일 → 설립일
     - 업태/종목 → 업종
     - 사업장소재지 → 주소
  3. 추출 결과 확인 → 사용자 교정
출력: profiles/{회사명}.md
의존성: vision/OCR 기능
우선순위: P1
```

#### F-103: 프로필 생성 (회사소개서 파싱)
```
설명: 회사소개서 PDF/HWP에서 자동 추출
입력: 회사소개서 파일
처리:
  1. 텍스트 추출 (HWP → hwpx-mcp, PDF → 텍스트)
  2. AI로 정보 매핑 (연혁, 조직, 사업내용 등)
  3. 추출 결과 확인 → 사용자 교정
출력: profiles/{회사명}.md
우선순위: P2
```

#### F-104: 프로필 수정
```
설명: 기존 프로필 업데이트
입력: 사용자 요청 + 수정 내용
처리:
  1. 기존 프로필 로드
  2. 수정 사항 반영
  3. 저장
출력: profiles/{회사명}.md (업데이트)
우선순위: P1
```

#### F-105: 프로필 목록/선택
```
설명: 등록된 프로필 목록 보기 및 선택
입력: "프로필 목록" 명령
처리:
  1. profiles/ 스캔 (_template.md 제외)
  2. 번호 매겨 목록 출력
  3. 선택 시 해당 프로필 로드
출력: 프로필 목록 + 선택된 프로필
우선순위: P1
```

---

### F-200: 프로젝트 관리

#### F-201: 프로젝트 생성
```
설명: 새 사업 프로젝트 폴더 생성
입력: "새 사업: {사업명}"
처리:
  1. 사업명 정규화 (공백→하이픈, 특수문자 제거)
  2. projects/{YYYY-사업명}/ 디렉토리 생성
  3. 하위 폴더 생성 (docs/, output/drafts/, output/visuals/ 등)
  4. context.md 초기화 (status: created, phase: 0)
  5. 프로필 선택 (단일 프로필이면 자동, 복수면 선택)
  6. 마감일 입력 받기 (선택)
출력: 프로젝트 폴더 + context.md
스크립트: scripts/new-project.sh
우선순위: P0
```

#### F-202: 프로젝트 목록
```
설명: 전체 프로젝트 상태 보기
입력: "프로젝트 목록" / "상태"
처리:
  1. projects/ 스캔
  2. 각 context.md의 status, phase, deadline 읽기
  3. 테이블 형태로 출력
출력: 프로젝트 목록 테이블
우선순위: P1
```

#### F-203: 프로젝트 전환
```
설명: 다른 프로젝트로 전환
입력: "1번 프로젝트" / "{사업명} 이어서"
처리:
  1. 해당 context.md 로드
  2. 현재 Phase/상태 보고
  3. 마지막 작업 내용 보고
출력: 프로젝트 상태 + 이어서 진행
우선순위: P1
```

#### F-204: 프로젝트 아카이브
```
설명: 완료/탈락 프로젝트 아카이브
입력: "선정됐어" / "탈락했어"
처리:
  1. 결과 기록 (선정/탈락)
  2. 탈락 시 사유 입력 받기
  3. knowledge/에 학습 데이터 저장 (F-801)
  4. status → completed
출력: context.md 업데이트 + knowledge/ 업데이트
우선순위: P2
```

#### F-205: 마감일 알림
```
설명: 프로젝트 마감일 기반 리마인더
입력: context.md의 deadline 필드
처리:
  1. Claude Code 진입 시 마감일 체크
  2. D-30, D-14, D-7, D-3, D-1, D-0 알림
  3. 권장 진행 상태 안내
출력: 알림 메시지
우선순위: P2
```

---

### F-300: 서류 스캔 & 분류 (Phase 1)

#### F-301: docs/ 파일 스캔
```
설명: 프로젝트 docs/ 폴더의 모든 파일 목록화
입력: docs/ 폴더 경로
처리:
  1. 파일 목록 수집
  2. 파일 형식 판별 (확장자 + MIME)
  3. 파일별 크기, 수정일 기록
출력: 파일 목록 (context.md에 저장)
담당: analyst
우선순위: P0
```

#### F-302: HWP/HWPX 텍스트 추출
```
설명: HWP/HWPX 파일에서 텍스트 + 구조 추출
입력: HWP/HWPX 파일 경로
처리:
  1. HWP인 경우 → HWPX 변환 (mcp__hwpx__convert_hwp_to_hwpx)
  2. mcp__hwpx__read_text로 텍스트 추출
  3. mcp__hwpx__list_pages로 페이지 구조 파악
  4. 표 구조 추출
출력: 추출된 텍스트 + 구조 정보
담당: analyst + docengine
의존성: hwpx-mcp-server
우선순위: P0
```

#### F-303: PDF 텍스트 추출
```
설명: PDF에서 텍스트 추출 (텍스트형/이미지형 자동 판별)
입력: PDF 파일 경로
처리:
  1. 텍스트 추출 시도 (pdftotext 등)
  2. 텍스트 없으면 → 이미지형 판별 → OCR
  3. 페이지별 처리
출력: 추출된 텍스트
담당: analyst
우선순위: P1
```

#### F-304: 이미지 OCR
```
설명: 이미지 파일에서 텍스트 추출
입력: 이미지 파일 경로 (JPG/PNG)
처리:
  1. Claude vision으로 OCR
  2. 구조화된 정보 추출 (사업자등록증 등)
출력: 추출된 텍스트 + 구조화 데이터
담당: analyst
우선순위: P1
```

#### F-305: 서류 자동 분류
```
설명: 추출된 텍스트 기반 서류 역할 자동 판별
입력: 파일별 추출 텍스트
처리:
  1. 키워드 기반 분류:
     - 공고문: "심사기준", "지원자격", "접수기간", "선정", "배점"
     - 양식: 빈 칸, "작성요령", 반복 구조, "기재", "기입"
     - 사업자등록증: "사업자등록번호", "대표자", "개업년월일"
     - 회사소개서: "연혁", "조직도", "비전", "미션"
     - 재무제표: "매출액", "영업이익", "대차대조표"
     - 이력서: "경력사항", "학력", "자격증"
  2. AI 판별 보조 (키워드만으로 불충분 시)
  3. 분류 결과 사용자 확인
  4. 틀리면 재분류
출력: 파일별 분류 결과 (context.md에 저장)
담당: analyst
우선순위: P0
```

#### F-306: 양식 서식 프로파일링
```
설명: 양식 파일의 서식 정보를 추출하여 프로파일 생성
입력: 양식 HWPX 파일
처리:
  1. hwpx-mcp로 문서 열기
  2. 스타일 정보 추출 (폰트, 크기, 줄간격, 정렬 등)
  3. 제목/소제목/본문/표 스타일 구분
  4. 번호 체계 분석
  5. style-profile.json 생성
출력: style-profile.json
담당: docengine
우선순위: P0
```

#### F-307: 양식 섹션 구조 분석
```
설명: 양식의 섹션/하위항목/표 구조를 트리로 분석
입력: 양식 텍스트 + 서식 정보
처리:
  1. 제목 스타일 기반 섹션 분리
  2. 번호 체계로 계층 구조 파악
  3. 각 섹션의 하위 항목 목록화
  4. 빈 칸/작성란 위치 매핑
  5. 표 위치 및 구조 (행/열/셀병합) 기록
출력: 섹션 구조 트리 (context.md에 저장)
담당: analyst
우선순위: P0

구조 예시:
sections:
  - id: 1
    title: "사업 개요"
    subsections:
      - "1-1. 사업명"
      - "1-2. 사업 목적"
      - "1-3. 사업 기간 및 규모"
    tables: [표1-소요예산총괄]
    fillable: ["사업명 입력란", "사업목적 텍스트 영역"]
```

---

### F-400: 공고 분석 (Phase 2)

#### F-401: 심사기준 추출
```
설명: 공고문에서 심사기준 및 배점표 추출
입력: 공고문 텍스트
처리:
  1. "심사기준", "평가기준", "배점" 키워드 탐색
  2. 배점표 구조 파싱 (항목, 세부항목, 배점)
  3. 합계 검증 (총점 = 100점 등)
  4. 심사기준 ↔ 양식 섹션 자동 매핑
출력: 심사기준 테이블 + 섹션 매핑 (context.md)
담당: analyst
우선순위: P0
```

#### F-402: 자격요건 추출
```
설명: 공고문에서 지원 자격/제외 대상 추출
입력: 공고문 텍스트
처리:
  1. "지원 자격", "신청 자격", "지원 대상" 섹션 탐색
  2. "제외 대상", "지원 제한" 섹션 탐색
  3. 항목별 리스트화
  4. 프로필 대비 자격 충족 여부 자동 판별
출력: 자격요건 리스트 + 충족 여부 (context.md)
담당: analyst
우선순위: P1
```

#### F-403: 사업 정보 추출
```
설명: 공고문에서 사업 개요 정보 추출
입력: 공고문 텍스트
처리:
  1. 사업명, 사업 목적, 지원 규모
  2. 사업 기간, 접수 기간, 접수 방법
  3. 지원 금액/비율 (정부출연 vs 자부담)
  4. 필수 제출서류 목록
  5. 주의사항/특이사항
출력: 사업 정보 요약 (context.md)
담당: analyst
우선순위: P0
```

#### F-404: 유사 공고 패턴 검색
```
설명: knowledge/에서 유사한 과거 공고 패턴 검색
입력: 공고 유형, 주관기관, 키워드
처리:
  1. knowledge/patterns/ 스캔
  2. 유사 공고 매칭
  3. 과거 전략/성공 패턴 로드
출력: 유사 패턴 + 참고 전략
담당: analyst
우선순위: P2
```

---

### F-500: 콘텐츠 작성 (Phase 3-4)

#### F-501: 작성 전략 수립
```
설명: 심사기준 기반 작성 전략 수립
입력: 심사기준 + 프로필 + 사업 아이디어
처리:
  1. 심사기준별 어필 포인트 설정
  2. 강점/약점 분석 (프로필 기반)
  3. 문체 프리셋 추천 (공고 유형 기반)
  4. 섹션별 분량 배분 (배점 비례)
  5. 전략 요약 → 사용자 확인
출력: 작성 전략서 (context.md)
담당: writer
우선순위: P0
```

#### F-502: 문체 프리셋 적용
```
설명: 선택된 문체 프리셋 로드 및 적용
입력: 프리셋 이름 (단일/혼합/섹션별)
처리:
  1. knowledge/presets/{이름}.md 로드
  2. 혼합 모드: 메인 + 서브 프리셋 병합
  3. 섹션별 모드: 섹션-프리셋 매핑 저장
  4. context.md에 적용된 프리셋 기록
출력: 활성 프리셋 설정
담당: writer
우선순위: P1
```

#### F-503: 추가 정보 수집
```
설명: 프로필/서류에서 못 찾은 정보를 사용자에게 질문
입력: 양식 필수 항목 - 이미 보유한 정보
처리:
  1. 양식 항목별 필요 정보 목록화
  2. 프로필 + docs/에서 이미 있는 정보 체크
  3. 부족한 정보만 질문 (최소 질문 원칙)
  4. 답변 → context.md에 저장
출력: 수집된 추가 정보
담당: PM (직접)
우선순위: P0
```

#### F-504: 섹션별 텍스트 초안 작성
```
설명: 각 섹션의 텍스트 콘텐츠 작성
입력: context.md (분석 결과 + 전략 + 프로필 + 추가 정보)
처리:
  1. 심사기준 배점 높은 섹션부터 작성
  2. 프리셋 문체 적용
  3. 각 섹션을 output/drafts/current/{번호}-{섹션명}.md로 저장
  4. 시각 자료 필요한 곳에 [VISUAL] 태그 삽입
  5. 출처 없는 수치는 [확인 필요] 태그
  6. 분량 체크 (섹션별 목표 대비)
출력: output/drafts/current/*.md
담당: writer
우선순위: P0
```

#### F-505: 시장조사 데이터 수집
```
설명: 사업 관련 시장 데이터 자동 수집
입력: 사업 키워드, 업종, 타겟 시장
처리:
  1. 웹 검색으로 시장 규모/성장률 수집
  2. 경쟁사/유사 서비스 조사
  3. 관련 정책/트렌드 수집
  4. 출처 URL + 접근일 기록
  5. 신뢰도 낮은 데이터 표기 [검증 필요]
출력: 시장조사 데이터 (context.md + visuals/sources/)
담당: analyst
우선순위: P2
```

---

### F-600: 시각 자료 (Phase 4)

#### F-601: [VISUAL] 태그 파싱
```
설명: 작성관 초안에서 [VISUAL] 태그 수집 및 파싱
입력: output/drafts/current/*.md
처리:
  1. 모든 [VISUAL: ...] 태그 수집
  2. 유형 분류 (표/차트/다이어그램/인포그래픽)
  3. 필요 데이터 식별
  4. 제작 순서 결정
출력: 시각 자료 제작 목록
담당: visualist
우선순위: P0
```

#### F-602: 데이터 테이블 생성
```
설명: 재무표, 인력표, 비교표 등 데이터 테이블 생성
입력: context.md의 데이터 + [VISUAL] 명세
처리:
  1. 표 구조 설계 (행/열/헤더)
  2. 데이터 채우기
  3. 합계 자동 계산 + 검증
  4. 단위 통일
  5. Markdown 표로 저장
출력: output/visuals/tables/*.md
담당: visualist
우선순위: P0
```

#### F-603: 차트 설계
```
설명: Mermaid 기반 차트 설계
입력: 데이터 테이블 + [VISUAL] 명세
처리:
  1. 차트 유형 선택 (막대/원형/라인/간트)
  2. Mermaid 코드 생성
  3. 데이터 레이블 포함
  4. 출처 표기
출력: output/visuals/charts/*.mmd + data/*.csv
담당: visualist
우선순위: P1
```

#### F-604: 다이어그램 설계
```
설명: 기술 아키텍처, 비즈니스 모델, 프로세스 플로우 등
입력: context.md + [VISUAL] 명세
처리:
  1. Mermaid 또는 텍스트 기반 설계
  2. 구성 요소/관계 정의
  3. 가독성 최적화
출력: output/visuals/diagrams/*.mmd
담당: visualist
우선순위: P1
```

#### F-605: 출처 자료 수집
```
설명: 통계 데이터/이미지를 공신력 있는 출처에서 수집
입력: [VISUAL] 태그의 출처 요구사항
처리:
  1. 데이터 소스 탐색 (통계청, KIPRIS 등)
  2. 데이터 수집 + 원본 URL 기록
  3. 가공 시 "자체 재구성" 명시
  4. sources.md에 출처 목록 관리
출력: output/visuals/sources/
담당: visualist
우선순위: P2
```

#### F-606: 수치 정합성 검증
```
설명: 본문 수치와 시각 자료 수치의 일관성 검증
입력: drafts/*.md + visuals/tables/*.md
처리:
  1. 본문에서 수치 추출
  2. 표/차트에서 수치 추출
  3. 교차 검증 (일치/불일치)
  4. 표 내부 합계 검증
  5. 불일치 항목 리포트
출력: 검증 리포트 (불일치 목록)
담당: visualist
우선순위: P1
```

---

### F-700: 문서 출력 (Phase 6)

#### F-701: 양식 백업
```
설명: 원본 양식 파일 백업
입력: 양식 HWPX 파일
처리:
  1. 원본 파일 복사 → {파일명}.bak
  2. 작업용 복사본 생성
출력: 백업 파일 + 작업용 파일
담당: docengine
우선순위: P0
```

#### F-702: 텍스트 삽입
```
설명: 초안 텍스트를 양식의 해당 위치에 삽입
입력: drafts/current/*.md + style-profile.json + 양식 HWPX
처리:
  1. 섹션별 삽입 위치 매핑 (F-307의 구조 분석 결과)
  2. style-profile.json에서 해당 위치 서식 로드
  3. mcp__hwpx__edit_text로 텍스트 삽입
  4. 서식 적용 (폰트, 크기, 줄간격 등)
  5. 삽입 후 read_text로 검증
출력: 텍스트가 삽입된 HWPX
담당: docengine
우선순위: P0
```

#### F-703: 표 데이터 삽입
```
설명: 시각 자료의 표 데이터를 양식 표에 삽입
입력: visuals/tables/*.md + 양식 HWPX
처리:
  1. 양식의 표 위치/구조 파악 (셀병합 포함)
  2. 데이터를 셀 단위로 삽입
  3. 표 서식 유지 (style-profile.json)
  4. 합계 재검증
출력: 표가 채워진 HWPX
담당: docengine
우선순위: P0
```

#### F-704: 이미지/차트 삽입
```
설명: 차트, 다이어그램, 이미지를 양식에 삽입
입력: visuals/ 이미지 파일 + 양식 HWPX
처리:
  1. Mermaid → 이미지 변환 (필요 시)
  2. 삽입 위치 결정
  3. hwpx-mcp로 이미지 삽입
  4. 크기 조정 (페이지 여백 내)
  5. 캡션 추가
출력: 이미지가 삽입된 HWPX
담당: docengine
우선순위: P1
```

#### F-705: 최종 검증
```
설명: 완성된 문서의 전체 품질 검증
입력: 완성된 HWPX
처리:
  1. 빈 칸/누락 항목 체크
  2. 서식 일관성 검증 (style-profile.json 대비)
  3. 페이지 수/분량 확인
  4. 오탈자 체크
  5. 수치 정합성 최종 확인
  6. 검증 리포트 생성
출력: 검증 리포트
담당: docengine
우선순위: P0
```

#### F-706: 최종 출력
```
설명: 최종 HWPX 파일 저장
입력: 검증 완료된 HWPX
처리:
  1. mcp__hwpx__save_document
  2. output/사업계획서.hwpx로 저장
  3. 이전 버전 있으면 사업계획서_v{N}.hwpx로 백업
출력: output/사업계획서.hwpx
담당: docengine
우선순위: P0
```

---

### F-800: 품질 관리 & 학습

#### F-801: 자가 심사
```
설명: 심사기준 대비 자가 평가
입력: 완성된 초안/최종본 + 심사기준
처리:
  1. 심사기준 항목별 평가
  2. 항목별 점수 부여 (예상)
  3. 부족한 부분 지적
  4. 개선 제안
  5. 총점 및 등급 (제출추천/보완필요/재작성)
출력: output/review.md
담당: analyst
우선순위: P1
```

#### F-802: 피드백 반영
```
설명: 사용자 피드백을 초안에 반영
입력: 사용자 피드백 텍스트
처리:
  1. 피드백 대상 섹션 식별
  2. 수정 내용 생성
  3. drafts/current/ 업데이트
  4. 연관 섹션 일관성 체크
  5. 버전 번호 증가 (current → v{N+1})
  6. 변경 이력 context.md에 기록
출력: 업데이트된 초안 + 변경 이력
담당: writer (텍스트) / visualist (시각 자료)
우선순위: P0
```

#### F-803: 지식 축적
```
설명: 프로젝트 완료 후 학습 데이터 저장
입력: 완성된 프로젝트 + 결과 (선정/탈락)
처리:
  1. 공고 유형 패턴 → knowledge/patterns/
  2. 효과적 표현 → knowledge/expressions/
  3. 심사 대응 전략 → knowledge/scoring/
  4. 교훈/피드백 → knowledge/lessons.md
출력: knowledge/ 업데이트
담당: analyst
우선순위: P2
```

#### F-804: 버전 관리
```
설명: 초안 버전 추적 및 관리
입력: 버전 관련 명령 ("버전 비교", "롤백" 등)
처리:
  - 새 버전: current/ → v{N}/ 복사 후 current/ 수정
  - 비교: 두 버전 간 diff 보여주기
  - 롤백: 지정 버전 → current/로 복원
출력: 버전 조작 결과
담당: PM (직접)
우선순위: P2
```

---

## 📋 개발 Phase & 마일스톤

### Phase 1: 기반 구축 (MVP-Core)
```
목표: sandoc에 들어가서 기본 동작이 되는 상태
예상: 1-2일

작업:
  [x] 디렉토리 구조 생성
  [ ] CLAUDE.md 작성
  [ ] .claude/agents/ 서브에이전트 4개 생성
  [ ] .mcp.json 설정 (hwpx-mcp-server)
  [ ] config/settings.json 초기값
  [ ] profiles/_template.md
  [ ] scripts/check-deps.sh
  [ ] scripts/new-project.sh
  [ ] .gitignore
  [ ] F-001 의존성 확인
  [ ] F-002 설정 초기화
  [ ] F-003 MCP 등록

검증:
  - cd ~/001_Projects/H1-sandoc && cc
  - "상태" → 정상 응답
  - "새 사업: 테스트" → 폴더 생성
```

### Phase 2: 서류 분석 (MVP-Analyze)
```
목표: 서류를 넣으면 분석하고 분류하는 상태
예상: 2-3일

작업:
  [ ] F-301 파일 스캔
  [ ] F-302 HWP 텍스트 추출
  [ ] F-305 서류 자동 분류
  [ ] F-306 서식 프로파일링
  [ ] F-307 양식 섹션 구조 분석
  [ ] F-401 심사기준 추출
  [ ] F-403 사업 정보 추출

검증:
  - tests/ 샘플 파일로 테스트
  - 공고문/양식 자동 분류 확인
  - 심사기준 정확히 추출되는지 확인
  - style-profile.json 정상 생성
```

### Phase 3: 콘텐츠 생성 (MVP-Write)
```
목표: 분석 결과 기반으로 초안을 작성하는 상태
예상: 2-3일

작업:
  [ ] F-101 프로필 생성 (수동)
  [ ] F-501 작성 전략 수립
  [ ] F-503 추가 정보 수집
  [ ] F-504 섹션별 초안 작성
  [ ] F-601 [VISUAL] 태그 파싱
  [ ] F-602 데이터 테이블 생성
  [ ] F-802 피드백 반영

검증:
  - 프로필 등록 → 초안 작성 전체 플로우
  - 8개 섹션 초안 생성
  - 표 데이터 포함
  - 피드백 → 수정 동작
```

### Phase 4: HWP 출력 (MVP-Output)
```
목표: 초안을 양식에 삽입하여 완성본 HWPX 출력
예상: 3-4일

작업:
  [ ] F-701 양식 백업
  [ ] F-702 텍스트 삽입 (서식 미러링)
  [ ] F-703 표 데이터 삽입
  [ ] F-705 최종 검증
  [ ] F-706 최종 출력

검증:
  - 생성된 HWPX를 한글에서 열어 확인
  - 서식이 원본 양식과 동일한지 검증
  - 표 데이터 정확한지 확인
  - 빈 칸 없는지 확인

★ MVP 완성 ★
```

### Phase 5: 고도화
```
목표: 품질 향상 + 부가 기능
예상: 지속적

작업:
  [ ] F-102 사업자등록증 OCR
  [ ] F-303 PDF 추출
  [ ] F-304 이미지 OCR
  [ ] F-402 자격요건 추출
  [ ] F-502 문체 프리셋 (10개)
  [ ] F-603 차트 설계
  [ ] F-604 다이어그램
  [ ] F-605 출처 수집
  [ ] F-606 수치 정합성 검증
  [ ] F-704 이미지 삽입
  [ ] F-801 자가 심사
  [ ] F-803 지식 축적
  [ ] F-804 버전 관리
  [ ] knowledge/ 도메인 지식 채우기
```

---

## 🧪 테스트 전략

### 테스트 데이터
```
tests/
├── sample-공고문.hwp           # 실제 정부 공고문 (또는 유사 작성)
├── sample-양식.hwp             # 실제 사업계획서 양식
├── sample-사업자등록증.jpg     # 테스트용 사업자등록증
├── sample-회사소개서.pdf       # 테스트용 회사소개서
└── expected/                   # 기대 결과
    ├── context-분류결과.md
    ├── style-profile.json
    └── 초안-섹션1.md
```

### 테스트 시나리오

```
시나리오 1: Happy Path (전체 플로우)
  입력: 공고문 + 양식 + 사업자등록증
  기대: 분류 → 분석 → 프로필 → 초안 → 출력

시나리오 2: 최소 입력
  입력: 양식만
  기대: 양식 분석 → 심사기준 없이 일반 초안 → 출력

시나리오 3: HWP 파싱 실패
  입력: 암호화된 HWP
  기대: 에러 안내 + 대안 제시

시나리오 4: 서류 재분류
  입력: 잘못 분류된 파일
  기대: 사용자 교정 → 재분류 → 정상 진행

시나리오 5: 피드백 루프
  입력: 초안 + 수정 요청 3회
  기대: 각 수정 반영 + 버전 관리 + 일관성 유지
```

---

## 📊 기능 우선순위 요약

| 우선순위 | 기능 | 개수 |
|----------|------|------|
| **P0 (필수)** | F-001~003, F-201, F-301~302, F-305~307, F-401, F-403, F-501, F-503~504, F-601~602, F-701~703, F-705~706, F-802 | 21개 |
| **P1 (중요)** | F-101, F-104~105, F-202~203, F-303~304, F-402, F-502, F-603~604, F-606, F-704, F-801 | 13개 |
| **P2 (확장)** | F-102~103, F-204~205, F-404, F-505, F-605, F-803~804 | 9개 |
| **합계** | | **43개** |
