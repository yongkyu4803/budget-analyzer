---
name: budget-index
description: 정부 예산안·확정예산·기금운용계획 사업설명자료의 파싱 Markdown을 사업 단위로 색인하고 판본·금액·원문 좌표를 검증한다. 예산사업 인덱스 생성·갱신·구조화 요청에 사용한다. 일반 문서 색인, 한글 파일 변환, 단순 예산 검색은 해당 전용 스킬을 사용한다.
---

## 이 배포본의 오프라인 실행

스킬 폴더에 `portable-kit.json`이 있으면 `kit_root`를 패키지 루트로 쓴다.
없으면 이 스킬의 두 단계 상위(`skills/`의 상위)가 패키지 루트다.
이하 `python3 .../budget_core.py` 예시는 같은 인자를 패키지의 `budget.cmd`에 전달한다.
예: `"C:\kordoc-kit\budget.cmd" --root "C:\예산자료" search "GPU 임차"`.
동봉 Python으로 실행되므로 Python 설치·pip·네트워크가 필요 없다.
변환은 같은 패키지 `convert.cmd`, 설정 생성은 `kit.cmd init --root ... --config ...`를 사용한다.
일반 검증 스크립트가 필요하면 `runtime/python/python.exe`로 해당 스크립트를 실행한다.
패키지 루트의 START-HERE.txt에서 지원 범위와 대용량 옵션을 확인한다.


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
