---
name: budget-index
description: 정부 예산안·확정예산·기금운용계획 사업설명자료의 파싱 Markdown을 사업 단위로 색인하고 판본·금액·원문 좌표를 검증한다. 예산사업 인덱스 생성·갱신·구조화 요청에 사용한다. 상임위원회 예산안 검토보고서(국회 전문위원 검토의견)의 사업·쟁점 색인 요청에도 사용한다. 일반 문서 색인, 한글 파일 변환, 단순 예산 검색은 해당 전용 스킬을 사용한다.
---

## 실행 방법

Python 3.10 이상(표준 라이브러리 전용, 네트워크 불필요). 먼저 `kordoc` 스킬의 `scripts/ensure-env.sh`을 실행해 통과(종료 코드 0)를 확인하고, `engine/env.json`의 `python`으로 실행한다. 통과 전에는 진행하지 않는다. 아래 `budget_core.py` 경로는 이 스킬 폴더의 `scripts/budget_core.py` 절대 경로로 치환한다.
한글 문서를 Markdown으로 바꾸는 단계는 `kordoc` 스킬의 `scripts/convert.py`를 쓴다.
설정은 `.budget-index/config.json`을 [설정 예시](references/config-example.json)에서 복사해 직접 만든다.


# 예산사업 인덱스

기존 `doc-index`를 복사해 특화한 스킬이다. 기존 스킬·상세 검토 노트는 보존하고 별도 `.budget-index/`에 전체 사업 색인을 만든다. [출처와 변경 범위](references/upstream.md).

## 작업 기준

- 워크스페이스를 먼저 확인한다. 기존 `index/_INDEX.md`는 상세 검토 목록이며 전체 사업 목록과 같다고 가정하지 않는다.
- 원문 값·단위·표제·인용은 그대로 보존한다. 검색 정규화와 환산치는 별도 값이다.
- 파일명만으로 확정 예산·발행일을 단정하지 않는다. 연도, 소관, 회계·기금, 판본 단계와 출처를 확인해 설정한다.
- 기존 `glossary.md`를 적용한다. 검색 별칭과 공식 표기 사전은 구분하며 기존 사전을 자동 덮어쓰지 않는다.
- 사용자가 요청한 범위의 로컬 원문·표를 읽어 대조한다. 후보 수에 따른 추가 승인 절차는 두지 않는다.
- `source_location_checked`는 사업명·경계 확인이다. 금액 검증이나 HWPX 대조 완료라는 뜻이 아니다. 기존 `source-reverified-at: null`을 일괄 승격하지 않는다.

## 생성·갱신

[데이터 계약](references/schema.md)을 읽는다. 실행 경로는 이 스킬 폴더의 실제 절대 경로로 치환한다. Python 3.10 이상, 외부 패키지나 서버가 필요 없다.

1. 이미 파싱된 Markdown이 있으면 사용한다. HWP/HWPX를 새로 읽어야 할 때만 설치된 `kordoc`를 사용한다. 이미지 변환은 별도 요청이다.
2. `.budget-index/config.json`이 없으면 [설정 예시](references/config-example.json)를 복사하고 실제 자료에 맞춘다. 예상 권수·사업 수는 목차에서 확인한다. 예시의 2027·과기정통부·777을 다른 자료에 재사용하지 않는다.
3. 본문 헤더와 반복 통합 목차를 교차 검증하고 새 캐시를 만든다.

```bash
python3 /absolute/path/budget-index/scripts/budget_core.py --root /absolute/workspace build
python3 /absolute/path/budget-index/scripts/budget_core.py --root /absolute/workspace verify --originals
```

현재 어댑터는 과기정통부 자료의 `(번호) 사업명 (코드)` + 반복 통합 목차 구조를 지원한다. 다른 부처·편집 형식은 실제 표본으로 어댑터를 먼저 검증한다. 경계 검사가 실패하면 그 판본을 게시하지 않고 기존 캐시를 보존한다. 다른 판본은 별도 워크스페이스에 만든다. 여러 판본을 한 DB에 합치는 기능은 현재 없다.

생성물은 `budget.sqlite`와 `CATALOG.md`다. DB는 재생성 가능한 검색 캐시이며 원문은 파싱 Markdown이다. `show`가 행 범위와 전체 표를 반환하므로 사업별 Markdown 사본을 추가로 만들 필요는 없다.

## 국회 검토보고서 색인 (review)

상임위원회가 낸 「예산안·기금운용계획안 검토보고서」는 사업설명자료와 다른 문서다. 같은 어댑터로 읽지 말고 `review_core.py`로 따로 색인한다. DB(`.budget-index/review.sqlite`)와 설정(`.budget-index/review-config.json`)이 별도라서 사업설명자료 색인에 영향이 없다. 두 색인을 합치지 않고 사업 코드로 연결해 보여 준다. [데이터 계약](references/review-schema.md).

**검증 범위**: 2027년도 과학기술정보통신부 소관 검토보고서(과학기술정보방송통신위원회, 과방위) 1건으로만 검증했다. 다른 상임위·부처·연도의 보고서도 같은 편집 관례를 따를 것으로 보고 시도할 수 있게 했지만 실물로 확인하지 않았다. 처음 쓰는 보고서는 아래 확인 절차를 반드시 거친다.

1. 보고서 HWP/HWPX를 `kordoc`의 `convert.py`로 Markdown으로 바꾼다. 쪽수가 많은 문서는 MCP 파서 출력이 중간에 잘릴 수 있으니 `convert.py`(파일로 저장)를 쓴다. 변환 뒤 Markdown의 끝부분이 문서 마지막 내용인지 확인한다.
2. `.budget-index/review-config.json`을 [설정 예시](references/review-config-example.json)에서 복사해 연도·부처·위원회·판본·`markdown_glob`을 실제 자료에 맞춘다. 예시의 2027·과기정통부·60을 다른 자료에 재사용하지 않는다. `markdown_glob`은 보고서 파일 1개와 일치해야 한다.
3. 색인을 만들고 검증한다.

```bash
python3 /absolute/path/budget-index/scripts/review_core.py --root /absolute/workspace build
python3 /absolute/path/budget-index/scripts/review_core.py --root /absolute/workspace verify
```

4. `build` 결과의 `warnings`와 `.budget-index/review.sqlite` manifest의 `toc_check`, `REVIEW_CATALOG.md`를 읽는다. 소관과·사업이 목차와 어긋나면 게시하지 않고 오류를 낸다(기존 색인 보존). 경고(회계 머리글 누락, 쟁점 제목 차이)는 사람이 보고 판단한다. 새 상임위 보고서에서 오류가 나면 편집 형식이 다른 것이므로 `patterns` 설정이나 어댑터 보완이 필요하다. 억지로 통과시키지 않는다.

사업설명자료 색인도 같은 작업 폴더에 있으면(`budget_core.py build` 완료) `search`·`show` 결과에 `program_link`가 붙는다(코드와 제목이 함께 맞는 사업만 연결). 회계연도가 다르면 연결하지 않는다.

## 상세 구조화

처음에는 사용자가 우선한 사업부터 처리한다. 전 사업의 검색 가능 여부와 상세 필드의 검증 범위를 따로 보고한다.

- `show <id> --section summary`, `show <id> --section purpose`, 필요한 본문 절을 읽는다. 절이 누락되면 `show <id>`로 사업 전체를 확인한다.
- `.budget-index/facts.json`의 레코드에 UID, 판본, 필드별 원문·좌표, 금액 상태를 기록한다. 수혜자·신청자격·시행기관·구매주체를 분리한다. 목적 문구만으로 신청자격을 만들지 않는다.
- 금액의 열 제목·연도·단위·행 문맥을 함께 확인한다. `요구안`과 `조정안(B)`, 본예산과 추경, 당초와 수정계획을 합치지 않는다. `0`, `-`, 빈칸, 미확인, 미보고는 다른 상태다.
- 원문에 없다고 쓰려면 해당 구간을 실제 확인한다. 아직 살펴보지 않은 칸은 `not_checked`로 남긴다.
- JSON 수정 후 `build`와 `verify`를 다시 실행한다. 출처 해시가 바뀐 facts는 자동 이월하지 않으며, 재검토하여 새 UID와 좌표로 갱신한다.

기존 v2 상세 노트는 그대로 읽고 `scripts/validate_index.py`로 검사할 수 있다. 새 상세 노트는 [v3 프로파일](profiles/budget-program-v3.md)의 8절 구조와 필수 머리말을 적용한다. 기존 28편을 모두 다시 검토했다는 표현은 쓰지 않는다. 구조 검사는 원문 사실 대조를 대신하지 않는다.

## 마무리

사업·권수·상세 검토 수, 원문 변경 감지 결과, 금액 구조화 범위, 미확인 항목을 보고한다. 검색 품질은 제목·코드뿐 아니라 목적·참여 경로 질문으로 확인한다. 사용자 회사의 사업 적합성 평가는 근거 필드와 분리하며 요청받았을 때 작성한다.
