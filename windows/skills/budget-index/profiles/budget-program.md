---
profile: budget-program
version: 2
label: 정부 예산안·기금운용계획안 사업설명자료 — 사업 1개당 인덱스 1편, 참여 경로·검증 관리 포함
status: |
  generic v1에서 갈라 나옴(2026-09-23). 버전 2는 이 워크스페이스의 관리서식 v2(index/_GUIDE.md)에 맞춘 것.
  8절은 _OPENED.md 2026-09-03 기록(사업 수혜자 행 부재, 9편 동시 발생)을 승격한 것이다.
  8절 행 이름·머리말 필드는 required_text로 검사하므로 문서 전체에서 찾는다 — 절 위치까지는 보지 못한다.

unreported_tokens: ["원문 미보고", "확인 필요", "해당없음", "원문 표기"]

sections:
  - {n: 1, title: 식별}
  - {n: 2, title: 한 줄 결론}
  - {n: 3, title: 핵심 값}
  - {n: 4, title: 신뢰도}
  - {n: 5, title: 인용}
  - {n: 6, title: 원문 재확인}
  - {n: 7, title: 용어}
  - {n: 8, title: 참여 경로·검증 관리}

length:
  narrative: [400, 6000]
  total: [1000, 15000]

checks:
  # 핵심 값은 반드시 원문 위치와 짝을 이룬다
  - kind: table_columns
    section: 3
    columns:
      - match: "^값$|수치|내용"
        require: nonempty
      - match: "원문 위치|위치|출처"
        require: nonempty

  - kind: min_rows
    section: 6
    min: 3
    label: 원문 위치 포인터

  # 한글 원문이므로 한글 인용을 허용한다
  - kind: verbatim_quotes
    section: 5
    min: 2
    min_chars: 20
    forbid_hangul: false

  # '미확인'은 외부자료 환산 등에도 쓰이므로, 원문 부분 확보 표지는 '본문 미확인'으로 좁힌다
  - kind: badge_consistency
    badge: "부분 확보"
    marker: "본문 미확인"

  - kind: required_text
    text: "원문을 대신하지 않는다"

  # 8절 — 참여 경로·검증 관리 표
  - kind: min_rows
    section: 8
    min: 13
    label: 관리 항목
  - kind: table_columns
    section: 8
    columns:
      - match: "^기록$"
        require: nonempty

  - kind: required_text
    text: "| 내부 고유 식별자 |"
  - kind: required_text
    text: "| 원문 파일 |"
  - kind: required_text
    text: "| 원문 최종 대조일 |"
  - kind: required_text
    text: "| 전년 비교 기준 |"
  - kind: required_text
    text: "| 최종 수혜자 |"
  - kind: required_text
    text: "| 신청·수행 자격 |"
  - kind: required_text
    text: "| 구매·계약 주체 |"
  - kind: required_text
    text: "| VESSL AI 참여 경로 |"
  - kind: required_text
    text: "| 다음 확인 |"
  - kind: required_text
    text: "| 검증 상태 |"

  # 머리말 — 내부 식별자와 검증 상태
  - kind: required_text
    text: "index-schema-version: 2"
  - kind: required_text
    text: "index-id: 2027-msit-"
  - kind: required_text
    text: "review-scope:"
  - kind: required_text
    text: "source-reverified-at:"
---

# 예산 사업설명자료 프로파일 (budget-program)

「예산안 및 기금운용계획안 사업설명자료」의 **개별 사업 항목 1개**를 인덱스 1편으로 만든다.
관리 규칙의 원본은 `index/_GUIDE.md`다. 이 프로파일은 그중 **기계가 볼 수 있는 부분**만 선언한다.

| 강제 | 어느 절 | 없으면 |
|---|---|---|
| 원문 위치 | 3절 짝 열 · 6절 지도 | 연결된 사업 본문과 표·절을 찾기 어렵다 |
| 핵심 값 그대로 | 3절 | 신규·대시·공란이 0으로 바뀌어 증감률이 틀린다 |
| 신뢰도와 한계 | 4절 | 계획안을 확정 예산처럼 인용한다 |
| 참여 경로·검증 관리 | 8절 | 수혜자·신청 자격·계약 주체가 섞여 참여 가능성을 과대평가한다 |

## 원문 확보 경로

- 로컬 검색은 `scripts/doc_search.py`와 `index/_ALL_PROGRAMS.md`를 사용한다. `index/source`의 사업별 본문에서 표·절을 열고, 필요하면 `kordoc-test`의 보존 Markdown 8권 및 원본 HWPX로 돌아간다.
- 보존 파싱본은 kordoc 4.22.13 결과다. 본문 식별자·권·회계/기금·사업번호·표/절·원본 행 범위와 SHA-256을 함께 관리한다. 행번호만 출처로 쓰지 않는다. 목차 기재 쪽은 실제 쪽별 렌더 대조와 구분한다.
- 파싱 오류·원본 서식 확인이 필요하면 HWPX(zip 안의 XML)의 해당 섹션을 확인한다. 큰 파일이므로 무조건 전체를 다시 풀지 않는다.
- 연결 확인일 `source-linked-at`와 전체 내용 대조일 `source-reverified-at`를 구분한다. 단순 본문 연결이나 문자열 검색은 금액·자격·해석의 검증 완료가 아니다. 상세 절차는 `index/_LOCAL_SEARCH.md`와 `index/_SOURCE_CHECK.md`를 따른다.

## 문서 유형 판별

| 유형 | 전년 비교 기준 칸 | 3절 필수 행 |
|---|---|---|
| 일반·특별회계 | 2026년 본예산(A), 추경이 있으면 병기 | 본예산·요구안·조정안(B)·증감·증감률 |
| 기금 | 2026년 당초계획(A), 변경계획이 있으면 병기 | 당초·요구안·조정안(B)·증감·증감률 |
| 신규 | 원문 표기 그대로("-", "000" 등). 0으로 바꾸지 않음 | 증감은 `순증` |

## 서식

1~7절은 generic과 같다. 머리말과 8절이 추가된다.

```markdown
---
doc-index-profile: budget-program
index-schema-version: 2
index-id: {{연도-msit-회계/기금-v권-n사업번호}}
reviewed-at: {{내부 검토일}}
review-scope: {{internal-consistency-only | source-reverified}}
source-reverified-at: {{원문 대조일 또는 null}}
title: {{사업명}}
date: {{2027년도 예산안 / 기금운용계획안 (제출 연월)}}
author: {{소관부처 (사업시행주체: …)}}
conclusion: {{2절과 같은 한 줄}}
---

… 1~7절 (generic과 동일) …

## 8. 참여 경로·검증 관리

| 항목 | 기록 |
|---|---|
| 내부 고유 식별자 | `{{index-id}}` — 공식 사업코드와 별도 관리 |
| 원문 파일 | {{상대링크}} |
| 원문 위치 | {{권·사업번호; 쪽수·추출문 앵커 또는 확인 필요}} |
| 문서 기준 | {{예산안·계획안; 확정액 아님}} |
| 내부 검토일·범위 | {{날짜 / 범위}} |
| 원문 최종 대조일 | {{날짜 또는 확인 필요}} |
| 전년 비교 기준 | {{본예산·당초·추경 중 무엇 / 금액}} |
| 최종 수혜자 | {{원문 「사업 수혜자」 또는 확인 필요}} |
| 신청·수행 자격 | {{공고·RFP 근거 또는 확인 필요}} |
| 구매·계약 주체 | {{공고·협약 근거 또는 확인 필요}} |
| VESSL AI 참여 경로 | [분석] {{경로}}; 참여 가능 확정 아님 |
| 다음 확인 | {{구체적 확인 과제}} |
| 검증 상태 | {{원문 기록 / 분석 / 확인 필요 구분}} |
| 적용 규칙 | [인덱스 관리 기준](_GUIDE.md), [확인 과제](_OPENED.md) |
```

## 검사기가 보지 못하는 것 — 사람이 확인

- 3절 금액이 원문 총괄표와 같은지, 증감률 재계산이 맞는지
- 마스터 목록(`_INDEX.md`) 금액·증감이 각 문서 3절과 같은지
- 머리말 `index-id`와 8절 식별자가 같은지, 식별자가 워크스페이스 안에서 유일한지
- 8절 행이 **8절 안에** 있는지(required_text는 문서 전체에서 찾는다)
- [원문 기록]·[외부자료]·[분석]·[확인 필요] 등급이 실제 근거와 맞는지
