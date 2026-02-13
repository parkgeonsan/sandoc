# QUICKSTART — sandoc 사업계획서 생성기

## 사전 요구사항

```bash
# Python 3.10+ 필요
python3 --version

# 설치
git clone https://github.com/your-org/sandoc.git
cd sandoc
uv sync            # 또는: pip install -e .
source .venv/bin/activate
```

## 전체 워크플로우 (8단계)

```
1. 프로젝트 생성     →  scripts/new-project.sh
2. 서류 넣기         →  docs/ 폴더에 PDF, HWP 복사
3. 추출              →  sandoc extract
4. 정보 수집         →  sandoc interview → 답변 작성 → sandoc interview --fill
5. 초안 작성         →  Claude Code가 context.json 읽고 섹션 작성
6. 검토 & 조립       →  sandoc run (visualize → review → assemble)
7. HWP 삽입 준비     →  sandoc inject → 지시서 생성
8. 지식 축적         →  sandoc learn → 표현/패턴 저장
```

### 원커맨드 실행 (한 번에!)

```bash
# 전체 파이프라인 실행 (extract → visualize → review → assemble)
sandoc run projects/2026-창업도약패키지/ -c company.json
```

---

## 1단계: 프로젝트 생성

```bash
bash scripts/new-project.sh "창업도약패키지"
```

생성 결과:
```
projects/2026-창업도약패키지/
├── docs/                    ← 서류를 넣을 폴더
├── output/
│   ├── drafts/current/      ← 섹션 초안이 저장될 위치
│   └── visuals/             ← 시각자료 저장 위치
└── context.md               ← 프로젝트 추적 파일
```

## 2단계: 서류 넣기

공고문, 양식, 증빙서류를 `docs/` 폴더에 넣습니다:

```bash
cp 공고문.pdf projects/2026-창업도약패키지/docs/
cp 사업계획서_양식.hwp projects/2026-창업도약패키지/docs/
cp 증빙서류_양식.hwp projects/2026-창업도약패키지/docs/
```

**지원 파일 형식:**
- `.hwp` — 한글 양식 (자동 분석 + 스타일 추출)
- `.pdf` — 공고문 (평가기준, 일정, 자격요건 자동 추출)

## 3단계: 추출 (extract)

```bash
sandoc extract projects/2026-창업도약패키지/
```

자동으로 수행하는 작업:
- 📁 문서 자동 분류 (공고문/양식/증빙/참고자료)
- 📄 HWP 양식 분석 (섹션, 표, 입력필드)
- 📋 PDF 공고문 분석 (평가기준, 일정, 자격요건)
- 🎨 스타일 프로파일 추출 (폰트, 여백, 줄간격)

생성되는 파일:
```
projects/2026-창업도약패키지/
├── context.json          ← 추출된 모든 정보 (문서분류, 심사기준, 양식구조)
├── style-profile.json    ← 양식의 스타일 정보 (폰트, 크기, 여백)
└── missing_info.json     ← 사용자에게 확인 필요한 누락 항목
```

## 4단계: 정보 수집 (interview)

```bash
# 설문지 + JSON 템플릿 생성
sandoc interview projects/2026-창업도약패키지/
```

생성되는 파일:
- `output/questionnaire.md` — 카테고리별 설문지 (기업정보, 아이템정보, 재무정보, 사업계획)
- `output/company_info_template.json` — 필드별 설명과 예시가 포함된 JSON 템플릿

JSON 템플릿을 채운 후 병합:
```bash
# 작성된 답변을 context.json 에 병합
sandoc interview projects/2026-창업도약패키지/ --fill answers.json
```

## 5단계: 초안 작성 (Claude Code)

Claude Code에서 프로젝트 열기:

```bash
claude   # Claude Code 실행
```

Claude에게 요청:
> "projects/2026-창업도약패키지/ 프로젝트의 context.json을 읽고
> 9개 섹션 초안을 작성해줘"

Claude Code의 4개 에이전트가 자동으로 작업합니다:

| 에이전트 | 역할 |
|----------|------|
| 📋 분석관 (analyst) | 서류 분석, 심사기준 매핑 |
| ✍️ 작성관 (writer) | 섹션별 초안 작성 |
| 🎨 비주얼관 (visualist) | 차트, 표, 다이어그램 생성 |
| 📐 문서관 (docengine) | 최종 HWPX 조립 |

초안은 `output/drafts/current/`에 저장됩니다:
```
output/drafts/current/
├── 01_company_overview.md      # 기업 개요
├── 02_problem_recognition.md   # 문제인식 (25점)
├── 03_solution.md              # 목표시장 분석 (25점)
├── 04_business_model.md        # 사업화 추진 성과
├── 05_market_analysis.md       # 사업화 추진 전략 (25점)
├── 06_growth_strategy.md       # 자금운용 계획
├── 07_team.md                  # 기업 구성 (25점)
├── 08_financial_plan.md        # 재무 계획
└── 09_funding_plan.md          # 사업비 집행 계획
```

## 6단계: 검토 & 조립 (run)

```bash
# 전체 파이프라인 (visualize → review → assemble)
sandoc run projects/2026-창업도약패키지/ --skip-extract

# 또는 개별 실행
sandoc visualize projects/2026-창업도약패키지/
sandoc review projects/2026-창업도약패키지/
sandoc assemble projects/2026-창업도약패키지/
```

수행 작업:
- 📊 시각화 차트 생성 (매출 추이, 사업비 구성, TAM/SAM/SOM)
- 🔍 자가 검토 (섹션별 점수, 누락 항목, 개선 사항)
- 📦 HWPX + HTML 문서 빌드

## 7단계: HWP 삽입 준비 (inject)

```bash
sandoc inject projects/2026-창업도약패키지/
```

생성되는 파일:
- `output/injection_map.json` — 초안↔양식 섹션 매핑 정보
- `output/injection_instructions.md` — hwpx-mcp 로 실제 삽입할 때 참조할 지시서

hwpx-mcp 가 사용 가능할 때, 지시서를 따라 원본 양식에 내용을 삽입합니다.

## 8단계: 지식 축적 (learn)

```bash
sandoc learn projects/2026-창업도약패키지/
```

완성된 초안에서 효과적인 표현/패턴을 추출하여 재활용합니다:
- `knowledge/expressions/` — 성과 수치, 비교 우위 등 효과적 표현
- `knowledge/patterns/` — 표, 불릿, 번호 목록 등 구조 패턴
- `knowledge/lessons.md` — 프로젝트별 교훈 기록

---

## 빠른 데모 (샘플 데이터)

```bash
# 샘플 데모: 내장된 (주)스마트팜테크 데이터로 즉시 테스트
sandoc build --sample -o output/demo
```

## CLI 명령어 요약

| 명령어 | 설명 |
|--------|------|
| `sandoc extract <project>` | 프로젝트 docs/ 스캔 → context.json 생성 |
| `sandoc interview <project>` | 누락 정보 설문지 생성 |
| `sandoc interview <project> --fill <answers.json>` | 답변을 context.json 에 병합 |
| `sandoc visualize <project>` | 초안에서 시각화 차트 생성 |
| `sandoc review <project>` | 사업계획서 자가 검토 |
| `sandoc assemble <project>` | 마크다운 초안 → HWPX + HTML 조립 |
| `sandoc inject <project>` | HWP 양식 삽입 매핑 + 지시서 생성 |
| `sandoc learn <project>` | 초안에서 표현/패턴 지식 축적 |
| `sandoc run <project>` | 전체 파이프라인 순차 실행 |
| `sandoc analyze <file>` | HWP 양식 또는 PDF 공고문 개별 분석 |
| `sandoc classify <folder>` | 폴더 내 문서 자동 분류 |
| `sandoc profile <hwp>` | HWP 스타일 프로파일 추출 |
| `sandoc generate --sample` | 샘플 사업계획서 텍스트 생성 |
| `sandoc build --sample` | 샘플 사업계획서 HWPX 빌드 |
| `sandoc profile-register` | 기업 프로필 등록/관리 |

## MCP 서버 (Claude Code 연동)

`.mcp.json`에 설정된 MCP 서버:

| MCP 서버 | 패키지 | 용도 |
|----------|--------|------|
| hwpx | `hwpx-mcp-server` (uvx) | HWP/HWPX 읽기·쓰기·변환 |
| chart | `@antv/mcp-server-chart` (npx) | 26+ 차트 유형 PNG 생성 |
| echarts | `mcp-echarts` (npx) | 간트차트, 게이지, 지도, 복합 차트 |
| mermaid | `mcp-mermaid` (npx) | 플로우차트, 조직도, 타임라인 |

## 평가기준 (2025 창업도약패키지)

| 평가항목 | 배점 | 통과기준 |
|----------|------|----------|
| 문제인식 (Problem) | 25점 | 60점 이상 |
| 실현가능성 (Solution) | 25점 | 60점 이상 |
| 성장전략 (Scale-up) | 25점 | 60점 이상 |
| 팀구성 (Team) | 25점 | 60점 이상 |

> 각 항목 60점 미만 시 **과락** — 해당 항목에 충분한 분량과 구체성을 할당해야 합니다.
