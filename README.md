# sandoc

**"서류 넣고, 대화하고, 완성본 받는다"**

sandoc은 정부 지원사업 사업계획서를 자동 작성하는 AI 시스템입니다.
공고 서류를 폴더에 넣으면 AI가 분석하고, 대화로 부족한 정보를 채우고, 원본 양식 그대로 완성된 사업계획서(HWPX)를 출력합니다.

---

## 주요 기능

- **자동 서류 분류** — 공고문, 양식, 증빙서류를 AI가 자동 판별
- **공고 심층 분석** — 심사기준, 배점표, 자격요건 자동 추출 & 양식 섹션 매핑
- **대화형 정보 수집** — 이미 있는 정보는 묻지 않고, 부족한 것만 질문
- **전략적 초안 작성** — 심사기준 배점 기반 어필 포인트 자동 설계
- **시각 자료 자동 생성** — 차트, 다이어그램, 인포그래픽, 표를 이미지로 생성
- **양식 서식 보존** — 원본 HWP 양식의 서식을 그대로 유지하며 내용만 삽입
- **자가 심사** — 심사기준 기반 자가 평가 리포트 생성
- **지식 축적** — 작성 패턴, 효과적 표현, 교훈을 자동 학습

---

## 기술 스택

### MCP 서버 (4개)

| MCP | 용도 |
|-----|------|
| `hwpx` (hwpx-mcp-server) | HWP/HWPX 읽기, 쓰기, 변환 |
| `chart` (@antv/mcp-server-chart) | 26+ 차트 유형 PNG 생성 |
| `echarts` (mcp-echarts) | 간트차트, 게이지, 지도, 3D 등 고급 차트 |
| `mermaid` (mcp-mermaid) | 플로우차트, 조직도, 마인드맵, 타임라인 |

### Skills (8개)

| 스킬 | 출처 | 용도 |
|------|------|------|
| `docx` | Anthropic 공식 | DOCX 생성/편집 |
| `xlsx` | Anthropic 공식 | 재무 테이블, 수식 계산 |
| `pdf` | Anthropic 공식 | PDF 텍스트 추출 |
| `canvas-design` | Anthropic 공식 | 인포그래픽, 커버 디자인 |
| `pptx` | Anthropic 공식 | 발표 심사용 PPT 생성 |
| `humanizer` | 커뮤니티 | AI 흔적 제거, 자연스러운 문체 |
| `planning` | 커뮤니티 | 파일 기반 계획/진행 관리 |
| `last30days` | 커뮤니티 | 최근 트렌드 조사 |

### AI 에이전트 팀 (4인 구성)

| 팀원 | 역할 |
|------|------|
| 📋 분석관 (analyst) | 서류 분석, 공고 파싱, 심사기준 매핑 |
| ✍️ 작성관 (writer) | 사업계획서 텍스트 초안 작성, 문체 관리 |
| 🎨 비주얼관 (visualist) | 표, 차트, 다이어그램, 인포그래픽 제작 |
| 📐 문서관 (docengine) | HWP 양식 조작, 최종 HWPX 출력 |

---

## 설치 방법

### 사전 요구사항

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (CLI)
- [uv](https://docs.astral.sh/uv/) (Python 패키지 매니저)
- [Node.js](https://nodejs.org/) (npx 사용을 위해)

### 설치

```bash
# 1. 저장소 클론
git clone https://github.com/your-org/sandoc.git
cd sandoc

# 2. 의존성 확인
./scripts/check-deps.sh

# 3. Claude Code에서 프로젝트 열기
claude
```

MCP 서버는 `.mcp.json`에 설정되어 있어 Claude Code가 자동으로 인식합니다.

---

## 사용법 (Quick Start)

```
# 1. 새 사업 프로젝트 생성
> 새 사업: 2026-스마트공장

# 2. docs/ 폴더에 서류 넣기 (공고문, 양식, 증빙 등)
#    → 파일 복사 후 Claude에게 알려주기
> 서류 넣었어

# 3. AI가 자동으로 서류 분류 & 공고 분석
#    → 심사기준, 배점표, 양식 구조 추출

# 4. 대화로 부족한 정보 채우기
> 핵심 기술은 AI 기반 품질 검사 시스템이야

# 5. 초안 작성 요청
> 초안 써줘

# 6. 리뷰 & 수정
> 기술성 부분 좀 더 보강해줘

# 7. 최종 HWPX 출력
> 출력해줘
```

---

## 프로젝트 구조

```
sandoc/
├── CLAUDE.md                        # PM 에이전트 동작 지침
├── README.md                        # 이 파일
├── .mcp.json                        # MCP 서버 설정
├── .gitignore
│
├── .claude/
│   ├── agents/                      # 서브에이전트 정의
│   │   ├── analyst.md               # 📋 분석관
│   │   ├── writer.md                # ✍️ 작성관
│   │   ├── visualist.md             # 🎨 비주얼관
│   │   └── docengine.md             # 📐 문서관
│   └── skills/                      # Claude Code Skills
│
├── config/
│   └── settings.json                # 시스템 설정
│
├── profiles/                        # 회사 프로필 DB
│   └── _template.md                 # 프로필 템플릿
│
├── projects/                        # 사업별 작업 폴더 (런타임 생성)
│   └── {YYYY-사업명}/
│       ├── docs/                    # 입력 서류
│       ├── output/                  # 생성 결과물
│       └── context.md               # 프로젝트 상태/이력
│
├── knowledge/                       # 축적 지식
│   ├── domain/                      # 도메인 지식 (문체, 심사, 실수 등)
│   ├── presets/                     # 문체 프리셋
│   ├── patterns/                    # 공고 유형별 패턴
│   ├── expressions/                 # 효과적 표현 DB
│   ├── scoring/                     # 심사 대응 전략
│   └── lessons.md                   # 작성 후 교훈/피드백
│
├── scripts/                         # 유틸리티 스크립트
├── docs/                            # 기획 문서
│   ├── PLAN.md                      # 기획서
│   └── DEV-SPEC.md                  # 개발 명세서
└── tests/                           # 테스트 데이터
```

---

## 문서

- [PLAN.md](docs/PLAN.md) — 전체 기획서 (비전, 아키텍처, 프로세스 설계)
- [DEV-SPEC.md](docs/DEV-SPEC.md) — 개발 명세서 (기술 스택, MCP/Skills 상세)

---

## 라이선스

Private — 내부 사용 전용
