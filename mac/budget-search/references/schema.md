# 예산사업 데이터 계약 v3 / runtime 1.0.0

## 저장과 정체성

`.budget-index/config.json`: 소관 ministry/ministry_id, fiscal_year, edition(id, stage, published_at), adapter, markdown_glob, expected_volumes/expected_programs, 권별 기본 회계(default_accounts).

`.budget-index/budget.sqlite`: 한 판본의 사업·본문 블록·좌표·해시·facts를 담는 재생성 가능 캐시. 임시 DB 작성 후 단일 파일 교체. 원문 변경/구조 검사 실패 시 게시하지 않는다. 검색 문자열만 Unicode NFKC/공백/문장부호 정규화하며 원문은 수정하지 않는다. SQLite 서버·확장 패키지 불필요.

`id`: 기존 연도-부처-회계-권-번호 식별자(호환 별칭).
`uid`: `id@edition.id@parsed_sha256의 앞16자리`. 코드가 같아도 다른 회계·권·사업이면 별개다. 같은 코드의 다른 연도·판본을 합치지 않는다. 전체 SHA-256도 별도 보존한다.

레코드: ministry, ministry_id, fiscal_year, account/account_id(회계 또는 기금의 원문 명칭), title, code, volume, number, edition, source, source_sha256, source_start_line/end_line, sections, original(path/sha256 또는 null), curated_index, curated_source_reverified_at, review_status, facts.

`published_at:null`은 발행일 확인 필요다. 파일명 날짜를 발행일로 복제하지 않는다. 현재 구현은 한 워크스페이스당 한 판본. 다른 판본은 별도 폴더로 관리하고 비교는 각각 조회해 근거를 대조한다. 새 형식의 어댑터는 실물 자료로 검증하기 전 지원한다고 말하지 않는다.

## 구조화 facts

`.budget-index/facts.json`은 다음 객체들의 배열이다. UID를 `show` 결과에서 가져오고 기록할 사실을 원문으로 확인한다.

```json
{
  "schema_version": 3,
  "uid": "기존ID@판본ID@파싱해시앞16자리",
  "edition": "판본ID",
  "checked_at": "2026-10-19",
  "review_scope": "파싱 Markdown 표의 값·단위·열 제목 대조; HWPX 시각 대조 제외",
  "fields": {
    "purpose": {"state":"not_checked", "raw":null},
    "beneficiaries": {"state":"not_checked", "raw":null},
    "eligibility": {"state":"not_checked", "raw":null},
    "implementer": {"state":"not_checked", "raw":null},
    "buyer": {"state":"not_checked", "raw":null},
    "funding_method": {"state":"not_checked", "raw":null},
    "subprograms": {"state":"not_checked", "raw":null}
  },
  "amounts": []
}
```

값이 있으면 `state:value`, `raw`에 원문을 넣고 `evidence`를 추가한다. `evidence`는 path, sha256, start_line, end_line, quote(그 행 범위 안의 연속된 원문 문자열)이다. 각 필드마다 증거를 둔다. 하위사업은 우선 원문 항목 목록을 보존한다. 독립 하위사업 테이블과 기관 역할 자동 추출은 아직 없다.

금액 객체:

- label: `program_total` 또는 하위사업 등 명확한 항목명.
- raw: 원문 숫자 표기 그대로; value: 쉼표만 제거한 십진수 **문자열**, 계산에 float 사용 금지.
- state: `value`, `zero`, `dash`, `blank`, `not_checked`, `not_reported`, `not_applicable`.
- year: 정수. stage: `approved`, `government_proposal`, `adjusted_proposal`, `request`, `supplementary`, `settlement`, `unknown`.
- unit: `원`, `천원`, `백만원`, `억원`. unit_raw: 원문 단위 표제. column_label: 원문 열 제목.
- verification: `not_checked` 또는 `source_checked`; verification_scope에는 실제 확인 대상을 쓴다.
- evidence: **단위 표제·연도·열 머리글·해당 행을 포함하는 전체 표**의 원문과 좌표.

`zero`는 숫자 0이고 `dash`/`blank` 등은 value:null이다. 원문 대시가 ‘미편성’인지 ‘해당없음’인지 자동 추정하지 않는다. `not_reported`는 관련 본문 확인 뒤 부재를 기록한 경우에만 사용한다. 상태가 없는 금액을 숫자로 필터링하지 않는다.

단위 환산은 필터 내부에서 Decimal로 수행한다. 출력 원문 값은 그대로 유지한다. 본예산(A)·당초(A)는 전년 비교 기준을 보존하고 추경·수정계획과 혼합하지 않는다. 현재 코퍼스의 정부안 총괄표는 2027년 요구안/조정안을 별도 열로 가진다.

## 검증 범위

`build`/`verify`: 자료 해시, 사업 경계, 반복 목차 일치, UID·판본, 원문 인용 일치, 행 범위, 수치 raw/value 일치, 0/대시 구분, 금액 연도/단위/열 표제 존재를 검사한다. **표에 있는 다른 숫자나 다른 열을 사람이 선택한 의미적 오류까지 자동 증명하지는 않는다.** 열·행 해석은 작성자가 대조한다.

`verify --originals`는 기록된 HWPX의 해시도 검사한다. 일반 검색은 Markdown·설정·facts·상세 노트의 해시를 검사한다. 원본 HWPX 재파싱 여부, 이미지 시각 대조는 별도이며 확인 범위를 보고한다. 이미지는 검색 DB에 포함하지 않는다.

기존 v2 상세 노트의 null 재검증 상태를 보존한다. 기존 노트의 설명만 보고 새 facts를 source_checked로 승격하지 않는다. 사용자 해석·VESSL AI 적합성은 facts와 다른 상세 노트 영역에 둔다.
