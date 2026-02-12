# HWP/HWPX 파일 구조 기술 문서

## 개요

한글과컴퓨터의 문서 형식인 HWP(한글 워드 프로세서)와 HWPX(한글 XML)의 내부 구조를 기술한다.
정부 사업계획서의 대부분이 HWP/HWPX 형식으로 제출되므로, 파일 구조를 이해하는 것이 파싱·생성·수정 작업의 기반이 된다.

---

## 1. HWP 파일 구조 (Binary Format)

### 1.1 OLE Compound File Structure

HWP 파일은 Microsoft의 **OLE2 (Object Linking and Embedding) Compound File** 형식을 기반으로 한다. 이는 하나의 파일 안에 여러 "스트림(Stream)"과 "스토리지(Storage)"를 포함하는 가상 파일 시스템이다.

```
HWP File (OLE Compound File)
├── FileHeader              # 파일 인식 정보
├── DocInfo                  # 문서 속성 (글꼴, 스타일, 배경 등)
├── BodyText/               # 본문 텍스트 (스토리지)
│   ├── Section0            # 첫 번째 구역
│   ├── Section1            # 두 번째 구역
│   └── ...
├── ViewText/               # 미리보기용 텍스트 (선택)
│   ├── Section0
│   └── ...
├── \x05HwpSummaryInformation  # OLE 표준 요약 정보
├── BinData/                # 바이너리 데이터 (이미지 등)
│   ├── BIN0001.bmp
│   ├── BIN0002.png
│   └── ...
├── PrvText                 # 미리보기 텍스트 (평문)
├── PrvImage                # 미리보기 이미지 (PNG)
├── DocOptions/             # 문서 옵션 (선택)
│   ├── _LinkDoc
│   └── ...
└── Scripts/                # 매크로 스크립트 (선택)
    ├── DefaultJScript
    └── JScriptVersion
```

### 1.2 FileHeader 스트림

파일의 첫 번째 스트림으로, HWP 파일임을 식별하고 버전·속성 정보를 담는다.

| 오프셋 | 크기 | 필드명 | 설명 |
|--------|------|--------|------|
| 0 | 32 bytes | Signature | "HWP Document File" (고정 문자열) |
| 32 | 4 bytes | Version | 파일 형식 버전 (예: 5.1.0.1) |
| 36 | 4 bytes | Properties | 비트 플래그 (압축, 암호화, 배포용 등) |
| 40 | 216 bytes | Reserved | 예약 영역 |

**Properties 비트 플래그:**

| 비트 | 의미 |
|------|------|
| 0 | 압축 여부 (1=압축) |
| 1 | 암호화 여부 |
| 2 | 배포용 문서 여부 |
| 3 | 스크립트 저장 여부 |
| 4 | DRM 보안 여부 |
| 5 | XMLTemplate 스토리지 존재 여부 |
| 6 | 문서 이력 관리 여부 |
| 7 | 전자 서명 정보 존재 여부 |

### 1.3 DocInfo 스트림 (문서 속성)

문서 전체에 적용되는 속성 정보를 담는 스트림이다. 레코드(Record) 단위로 구성된다.

#### 레코드 구조

각 레코드는 4바이트 헤더 + 가변 길이 데이터로 구성된다:

```
Record Header (4 bytes):
├── Tag ID    (10 bits): 레코드 유형 식별자
├── Level     (10 bits): 레코드의 중첩 레벨
└── Size      (12 bits): 데이터 크기 (4095 이하)
                          4095이면 뒤에 4바이트 실제 크기 추가
```

#### 주요 DocInfo 레코드 유형

| Tag ID | 이름 | 설명 |
|--------|------|------|
| 0 | DOCUMENT_PROPERTIES | 문서 속성 (섹션 수, 시작 페이지 등) |
| 1 | ID_MAPPINGS | ID 매핑 헤더 (글꼴/스타일 개수 등) |
| 2 | BIN_DATA | 바이너리 데이터 참조 정보 |
| 3 | FACE_NAME | 글꼴 이름 정보 |
| 4 | BORDER_FILL | 테두리/배경 속성 |
| 5 | CHAR_SHAPE | 글자 모양 (폰트, 크기, 색상, 굵기 등) |
| 6 | TAB_DEF | 탭 정의 |
| 7 | NUMBERING | 번호 매기기 정의 |
| 8 | BULLET | 글머리표 정의 |
| 9 | PARA_SHAPE | 문단 모양 (정렬, 줄간격, 여백 등) |
| 10 | STYLE | 스타일 정의 |
| 11 | DOC_DATA | 문서 데이터 |
| 12 | DISTRIBUTE_DOC_DATA | 배포용 문서 데이터 |
| 14 | COMPATIBLE_DOCUMENT | 호환 문서 정보 |
| 15 | LAYOUT_COMPATIBILITY | 레이아웃 호환성 |

### 1.4 CharShape (글자 모양) 레코드 상세

사업계획서 양식에서 가장 중요한 레코드 중 하나이다. 글꼴, 크기, 색상, 굵기 등 텍스트의 시각적 속성을 정의한다.

```
CharShape Record:
├── FaceNameID[7]      # 7개 언어별 글꼴 ID (한글, 영문, 한자, 일본어, 기타, 기호, 사용자)
├── Ratio[7]           # 글꼴 장평 비율 (%)
├── Spacing[7]         # 글자 간격 (%)
├── RelSize[7]         # 상대 크기 (%)
├── CharOffset[7]      # 글자 위치 오프셋 (%)
├── Height             # 글자 크기 (단위: 1/7200 인치, 100 = 10pt)
├── Properties         # 속성 플래그 (굵게, 기울임, 밑줄, 취소선 등)
├── ShadeColor          # 음영 색상
├── UseFontSpace       # 글꼴 간격 사용 여부
├── BaseLineColor      # 밑줄/취소선 색상
├── UnderLineColor     # 밑줄 색상 (별도)
├── TextColor          # 글자 색상 (RGB + Alpha)
└── ShadowInfo         # 그림자 정보
```

**글자 크기 변환:**
- HWP 내부 단위: 1/7200 인치
- 포인트(pt) 변환: `pt = height / 100 * 10` (대략)
- 예: Height=1000 → 10pt, Height=1200 → 12pt

### 1.5 ParaShape (문단 모양) 레코드 상세

```
ParaShape Record:
├── Properties         # 정렬(좌/우/가운데/배분), 줄바꿈 등
├── LeftMargin         # 왼쪽 여백 (단위: HWP Unit)
├── RightMargin        # 오른쪽 여백
├── Indent             # 들여쓰기
├── TopParaSpace       # 문단 위 간격
├── BottomParaSpace    # 문단 아래 간격
├── LineSpacingType     # 줄간격 유형 (%, 고정, 여백만)
├── LineSpacing         # 줄간격 값
├── TabDefID           # 탭 정의 ID
├── NumberingID        # 번호 매기기 ID
├── BorderFillID       # 테두리/배경 ID
└── ...
```

**줄간격 유형:**
- 0: 비율 (%) — 글자 크기 대비 비율
- 1: 고정값 (pt)
- 2: 여백만 지정 (pt)

### 1.6 BodyText 섹션 스트림

본문 텍스트는 `BodyText/Section0`, `BodyText/Section1` 등의 스트림에 저장된다. 각 섹션은 레코드들의 연속이다.

#### 주요 BodyText 레코드

| Tag ID | 이름 | 설명 |
|--------|------|------|
| 66 | PARA_HEADER | 문단 헤더 (텍스트 길이, 제어 문자 수 등) |
| 67 | PARA_TEXT | 문단 텍스트 (UTF-16LE 인코딩) |
| 68 | PARA_CHAR_SHAPE | 문단 내 글자 모양 참조 |
| 69 | PARA_LINE_SEG | 줄 세그먼트 정보 |
| 70 | PARA_RANGE_TAG | 범위 태그 |
| 71 | CTRL_HEADER | 컨트롤(개체) 헤더 |
| 72 | LIST_HEADER | 리스트 헤더 (표, 텍스트 상자 등) |
| 73 | PAGE_DEF | 페이지 정의 (용지 크기, 방향) |
| 74 | FOOTNOTE_SHAPE | 각주 모양 |
| 75 | PAGE_BORDER_FILL | 쪽 테두리/배경 |
| 76 | SHAPE_COMPONENT | 그리기 개체 구성요소 |
| 77 | TABLE | 표 정의 |
| 78 | CELL | 셀 정의 |

#### 텍스트 인코딩과 제어 문자

PARA_TEXT 레코드의 텍스트는 UTF-16LE로 인코딩된다. 일부 코드 포인트는 제어 문자로 사용된다:

| 코드 | 크기 | 의미 |
|------|------|------|
| 0x00 | 1 char | 사용 안 함 |
| 0x01 | 8 chars | 확장 제어 문자 시작 (예: 표, 그림) |
| 0x02 | 8 chars | 구역/단 정의 |
| 0x03 | 8 chars | 필드 시작 |
| 0x04 | 1 char | 필드 끝 |
| 0x09 | 1 char | 탭 |
| 0x0A | 1 char | 줄 바꿈 (강제) |
| 0x0D | 1 char | 문단 나눔 |
| 0x18 | 8 chars | 합계/캡션 등 |
| 0x1E | 1 char | 묶음 빈칸 |
| 0x1F | 1 char | 고정폭 빈칸 |

### 1.7 데이터 압축

FileHeader의 Properties 비트 0이 1이면, DocInfo와 BodyText 스트림의 데이터가 zlib (deflate) 알고리즘으로 압축되어 있다. 읽기 전에 압축을 해제해야 한다.

```python
import zlib

# 압축된 스트림 데이터를 읽은 후
decompressed = zlib.decompress(compressed_data, -15)
```

**참고**: `-15` 파라미터는 raw deflate (zlib 헤더 없음)를 의미한다.

---

## 2. HWPX 파일 구조 (XML Format)

### 2.1 개요

HWPX는 한글과컴퓨터의 개방형 문서 포맷으로, **OASIS ODF(Open Document Format)** 표준을 기반으로 한다. 파일 구조는 ZIP 아카이브 안에 XML 파일들을 담는 형태이다.

### 2.2 ZIP 구조

```
document.hwpx (ZIP Archive)
├── mimetype                    # MIME 타입 ("application/hwp+zip")
├── META-INF/
│   ├── manifest.xml            # 파일 목록 (ODF 표준)
│   └── container.xml           # 컨테이너 정보
├── Contents/
│   ├── content.hpf             # 콘텐츠 목록 (마스터 파일)
│   ├── header.xml              # 문서 헤더 정보
│   ├── section0.xml            # 본문 섹션 0
│   ├── section1.xml            # 본문 섹션 1 (있는 경우)
│   └── ...
├── settings.xml                # 문서 설정
├── BinData/                    # 바이너리 데이터 (이미지 등)
│   ├── image1.png
│   ├── image2.jpg
│   └── ...
└── Preview/
    ├── PrvText.txt             # 미리보기 텍스트
    └── PrvImage.png            # 미리보기 이미지
```

### 2.3 mimetype 파일

ZIP 아카이브의 첫 번째 항목으로, 압축하지 않고 저장한다.

```
application/hwp+zip
```

이 파일은 HWPX 파일을 다른 ZIP 파일과 구별하는 데 사용된다.

### 2.4 META-INF/manifest.xml

ODF 표준에 따른 파일 목록이다.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">
  <manifest:file-entry manifest:media-type="application/hwp+zip" manifest:full-path="/"/>
  <manifest:file-entry manifest:media-type="text/xml" manifest:full-path="Contents/content.hpf"/>
  <manifest:file-entry manifest:media-type="text/xml" manifest:full-path="Contents/header.xml"/>
  <manifest:file-entry manifest:media-type="text/xml" manifest:full-path="Contents/section0.xml"/>
  <!-- ... -->
</manifest:manifest>
```

### 2.5 Contents/content.hpf (마스터 파일)

문서의 전체 구조를 정의하는 마스터 파일이다.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<hpf:hwpPackageFile xmlns:hpf="urn:hancom:hwp:packagefile"
                     version="1.0">
  <hpf:compatibledocument target="hwp7"/>
  <hpf:header href="Contents/header.xml"/>
  <hpf:body>
    <hpf:section href="Contents/section0.xml"/>
  </hpf:body>
</hpf:hwpPackageFile>
```

### 2.6 Contents/header.xml (문서 헤더)

HWP의 DocInfo에 해당하는 정보를 XML로 표현한다. 글꼴, 스타일, 번호 매기기 등 문서 전역 설정을 포함한다.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<ha:head xmlns:ha="urn:hancom:hwp:annotation"
         xmlns:hp="urn:hancom:hwp:paragraph"
         xmlns:hs="urn:hancom:hwp:style">
  <!-- 글꼴 정보 -->
  <ha:fontfaces>
    <ha:fontface lang="hangul">
      <ha:font id="0" face="맑은 고딕" type="ttf"/>
      <ha:font id="1" face="함초롬돋움" type="ttf"/>
    </ha:fontface>
    <ha:fontface lang="latin">
      <ha:font id="0" face="맑은 고딕" type="ttf"/>
    </ha:fontface>
  </ha:fontfaces>

  <!-- 글자 모양 -->
  <ha:charProperties>
    <ha:charPr id="0" height="1000" textColor="#000000" bold="false" italic="false">
      <ha:fontRef hangul="0" latin="0"/>
    </ha:charPr>
    <ha:charPr id="1" height="1400" textColor="#000000" bold="true" italic="false">
      <ha:fontRef hangul="0" latin="0"/>
    </ha:charPr>
  </ha:charProperties>

  <!-- 문단 모양 -->
  <ha:paraProperties>
    <ha:paraPr id="0" align="justify">
      <ha:lineSpacing type="percent" value="160"/>
      <ha:margin left="0" right="0" indent="0"/>
      <ha:spacing before="0" after="0"/>
    </ha:paraPr>
  </ha:paraProperties>

  <!-- 스타일 -->
  <ha:styles>
    <ha:style id="0" type="para" name="바탕글" paraPrID="0" charPrID="0"/>
    <ha:style id="1" type="para" name="본문" paraPrID="1" charPrID="1" nextStyleID="1"/>
  </ha:styles>
</ha:head>
```

### 2.7 Contents/section0.xml (본문 섹션)

본문 텍스트를 XML로 표현한다. 문단(p), 텍스트(t), 표(tbl), 이미지(pic) 등의 요소로 구성된다.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hs="urn:hancom:hwp:section"
        xmlns:hp="urn:hancom:hwp:paragraph"
        xmlns:ht="urn:hancom:hwp:table"
        xmlns:hr="urn:hancom:hwp:run">
  <!-- 구역 정의 (페이지 설정) -->
  <hs:pageDef width="59528" height="84188"
              landscape="false">
    <hs:margin left="8504" right="8504"
               top="5668" bottom="4252"
               header="4252" footer="4252"/>
  </hs:pageDef>

  <!-- 문단 -->
  <hp:p paraPrID="0" styleID="0">
    <hp:run charPrID="0">
      <hp:t>일반 텍스트 내용</hp:t>
    </hp:run>
    <hp:run charPrID="1">
      <hp:t>굵은 텍스트</hp:t>
    </hp:run>
  </hp:p>

  <!-- 표 -->
  <hp:p paraPrID="0" styleID="0">
    <hp:run charPrID="0">
      <ht:tbl cols="3" rows="2" borderFillID="1">
        <ht:tr>
          <ht:tc>
            <hp:p paraPrID="0" styleID="0">
              <hp:run charPrID="0"><hp:t>셀 1</hp:t></hp:run>
            </hp:p>
          </ht:tc>
          <ht:tc>
            <hp:p paraPrID="0" styleID="0">
              <hp:run charPrID="0"><hp:t>셀 2</hp:t></hp:run>
            </hp:p>
          </ht:tc>
          <ht:tc>
            <hp:p paraPrID="0" styleID="0">
              <hp:run charPrID="0"><hp:t>셀 3</hp:t></hp:run>
            </hp:p>
          </ht:tc>
        </ht:tr>
      </ht:tbl>
    </hp:run>
  </hp:p>
</hs:sec>
```

### 2.8 HWPX 네임스페이스

| 접두사 | URI | 용도 |
|--------|-----|------|
| hpf | urn:hancom:hwp:packagefile | 패키지 파일 구조 |
| ha | urn:hancom:hwp:annotation | 문서 헤더/메타데이터 |
| hp | urn:hancom:hwp:paragraph | 문단 요소 |
| ht | urn:hancom:hwp:table | 표 요소 |
| hs | urn:hancom:hwp:section | 섹션 요소 |
| hr | urn:hancom:hwp:run | 텍스트 런 요소 |
| hc | urn:hancom:hwp:core | 코어 속성 |
| manifest | urn:oasis:names:tc:opendocument:xmlns:manifest:1.0 | ODF 매니페스트 |

### 2.9 단위 체계

HWPX에서 사용하는 단위는 HWP Unit(HU)이다:

- 1 HU = 1/7200 인치
- 1 cm = 약 2835 HU
- 1 pt = 100 HU
- A4 용지: 59528 HU × 84188 HU (210mm × 297mm)

---

## 3. HWP vs HWPX 비교

| 항목 | HWP (Binary) | HWPX (XML) |
|------|-------------|------------|
| 기반 형식 | OLE2 Compound File | ZIP + XML |
| 데이터 구조 | 바이너리 레코드 | XML 요소 |
| 텍스트 인코딩 | UTF-16LE | UTF-8 |
| 압축 | zlib (선택) | ZIP 내장 |
| 읽기/쓰기 난이도 | 높음 (바이너리 파싱) | 중간 (XML 파싱) |
| 파일 크기 | 일반적으로 작음 | 일반적으로 큼 |
| 호환성 | 한글 전 버전 | 한글 2014+ |
| 외부 도구 지원 | olefile (Python) | zipfile + xml.etree (Python) |
| 개방성 | 비공개 (리버스 엔지니어링) | 반공개 (XML 스키마 참조 가능) |

---

## 4. 프로그래밍 참고

### 4.1 HWP 파일 읽기 (Python)

```python
import olefile
import zlib
import struct

def read_hwp(filepath):
    ole = olefile.OleFileIO(filepath)

    # FileHeader 읽기
    header = ole.openstream('FileHeader').read()
    signature = header[:32].decode('utf-8', errors='ignore').strip('\x00')
    version = struct.unpack('<I', header[32:36])[0]
    properties = struct.unpack('<I', header[36:40])[0]
    is_compressed = bool(properties & 0x01)

    # BodyText 섹션 읽기
    for entry in ole.listdir():
        if entry[0] == 'BodyText':
            stream = ole.openstream(entry)
            data = stream.read()
            if is_compressed:
                data = zlib.decompress(data, -15)
            # 레코드 파싱 ...

    ole.close()
```

### 4.2 HWPX 파일 읽기 (Python)

```python
import zipfile
import xml.etree.ElementTree as ET

def read_hwpx(filepath):
    with zipfile.ZipFile(filepath, 'r') as zf:
        # mimetype 확인
        mimetype = zf.read('mimetype').decode('utf-8').strip()
        assert mimetype == 'application/hwp+zip'

        # 마스터 파일 읽기
        content_hpf = ET.fromstring(zf.read('Contents/content.hpf'))

        # 섹션 파일 읽기
        section_xml = ET.fromstring(zf.read('Contents/section0.xml'))

        # 텍스트 추출
        ns = {'hp': 'urn:hancom:hwp:paragraph'}
        for t_elem in section_xml.iter('{urn:hancom:hwp:paragraph}t'):
            print(t_elem.text)
```

### 4.3 HWPX 파일 수정 (Python)

```python
import zipfile
import xml.etree.ElementTree as ET
import io

def modify_hwpx(input_path, output_path, replacements):
    """
    replacements: dict of {old_text: new_text}
    """
    with zipfile.ZipFile(input_path, 'r') as zin:
        with zipfile.ZipFile(output_path, 'w') as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)

                if item.filename.startswith('Contents/section'):
                    # XML 파싱 후 텍스트 치환
                    root = ET.fromstring(data)
                    ns = {'hp': 'urn:hancom:hwp:paragraph'}
                    for t_elem in root.iter('{urn:hancom:hwp:paragraph}t'):
                        if t_elem.text:
                            for old, new in replacements.items():
                                t_elem.text = t_elem.text.replace(old, new)
                    data = ET.tostring(root, encoding='unicode').encode('utf-8')

                zout.writestr(item, data)
```

---

## 5. 사업계획서 양식에서 자주 사용되는 구조

### 5.1 일반적인 양식 패턴

정부 사업계획서 양식은 다음과 같은 HWP/HWPX 구조를 자주 사용한다:

1. **표 기반 입력 영역**: 대부분의 입력 칸이 표(Table) 안에 위치
2. **셀 병합**: 헤더 셀과 입력 셀의 구분을 위해 셀 병합 활용
3. **배경색 구분**: 헤더 영역은 회색/파란색 배경, 입력 영역은 흰색
4. **글자 모양 차이**: 제목은 굵게+큰 폰트, 입력란은 보통+작은 폰트
5. **구역(Section) 구분**: 표지, 본문, 첨부 등이 별도 구역으로 분리

### 5.2 텍스트 식별 전략

양식에서 사용자 입력 영역을 식별하는 방법:

1. **빈 셀 탐색**: 표 안에서 텍스트가 없거나 안내 문구만 있는 셀
2. **안내 문구 패턴**: "※ 작성 안내:", "(예시)", "직접 입력", "OOO" 등
3. **글자 모양 차이**: 안내 문구는 회색/작은 폰트, 입력 내용은 검정/보통 폰트
4. **셀 크기**: 입력 영역은 상대적으로 넓은 높이를 가짐
