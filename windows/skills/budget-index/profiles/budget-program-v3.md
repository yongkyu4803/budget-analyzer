---
profile: budget-program-v3
version: 3
label: 예산사업 상세 노트 v3 — 원문 사실·판본·참여 경로 구분
status: |
  기존 budget-program v2의 8절 구조를 계승하고 연도·부처와 회사명 고정을 제거했다.
  판본 UID를 추가한다. 구조 검사이며 표의 값과 열 해석은 원문으로 별도 검증한다.

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
    text: "| 참여 경로 |"
  - kind: required_text
    text: "| 다음 확인 |"
  - kind: required_text
    text: "| 검증 상태 |"

  - kind: required_text
    text: "budget-uid:"
  - kind: required_text
    text: "edition-id:"
  # 머리말 — 내부 식별자와 검증 상태
  - kind: required_text
    text: "index-schema-version: 3"
  - kind: required_text
    text: "index-id:"
  - kind: required_text
    text: "review-scope:"
  - kind: required_text
    text: "source-reverified-at:"
---

# 예산사업 상세 노트 v3

8절 제목·순서는 위 sections 선언을 따른다. 기존 노트처럼 원문 인용과 좌표를 남긴다.
머리말에 doc-index-profile: budget-program-v3, index-schema-version: 3, index-id, budget-uid, edition-id, review-scope, source-reverified-at를 쓴다.
참여 경로는 소관·회계·금액·수혜자·신청자격·구매주체의 사실과 구분한다. 원문이 미확인이면 확인 필요로 남긴다. 이 노트는 원문을 대신하지 않는다.
