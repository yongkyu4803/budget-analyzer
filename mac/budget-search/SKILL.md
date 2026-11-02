---
name: budget-search
description: 로컬 예산사업 인덱스 전체에서 사업명·코드·정책 목적·참여 경로·금액 조건으로 검색하고 원문 근거를 제시한다. 예산사업 탐색, 예산액 확인, 관련 사업 비교 요청에 사용한다. 일반 문서 검색이나 새 인덱스 구축은 해당 전용 스킬을 사용한다.
---

## 실행 방법

Python 3.10 이상(표준 라이브러리 전용, 네트워크 불필요). 먼저 `kordoc` 스킬의 `scripts/ensure-env.sh`을 실행해 통과(종료 코드 0)를 확인하고, `engine/env.json`의 `python`으로 실행한다. 통과 전에는 진행하지 않는다. 아래 `budget_core.py` 경로는 이 스킬 폴더의 `scripts/budget_core.py` 절대 경로로 치환한다.
한글 문서를 Markdown으로 바꾸는 단계는 `kordoc` 스킬의 `scripts/convert.py`를 쓴다.
설정은 `.budget-index/config.json`을 [설정 예시](references/config-example.json)에서 복사해 직접 만든다.


# 예산사업 검색

기존 `doc-evidence`를 복사해 특화했다. [출처와 변경 범위](references/upstream.md). `index/_INDEX.md`에 없는 사업도 전체 캐시에서 찾는다. 로컬 검색 요청에 필요한 원문을 별도 승인 없이 확인한다.

## 시작

현재 폴더와 사용자가 지정한 폴더에서 `.budget-index/config.json`과 `budget.sqlite`를 확인한다. 임의로 홈 전체를 탐색하지 않는다. 캐시가 없으면 `budget-index`로 구축한다. [데이터 계약](references/schema.md), 새 설정이 필요할 때 [예시](references/config-example.json)를 읽는다.

```bash
python3 /absolute/path/budget-search/scripts/budget_core.py --root /absolute/workspace search 'GPU 임차' --limit 10
python3 /absolute/path/budget-search/scripts/budget_core.py --root /absolute/workspace search --code 4331-310
```

매 검색은 파싱 Markdown·설정·구조화 facts·연결된 상세 노트의 해시를 확인한다. 변경 경고가 나오면 낡은 결과로 답하지 말고 재색인한다. facts가 변경 전 판본을 가리키면 먼저 재대조한다.

## 자연어 질문 → 검색 계획

자연어 문장을 그대로 AND 검색하지 않는다. 현재 대화의 모델이 [검색 계획 규격](references/query-plan.md)에 맞게 목적·핵심 개념·조건을 JSON으로 만든다. 별도 유료 모델 API 호출은 필요 없다. 로컬 검색 엔진은 오프라인으로 동작하지만 대화 모델까지 오프라인이라는 뜻은 아니다.

- 핵심 개념별 AND 그룹을 만들고 같은 의미의 표현만 그룹 내 OR로 둔다. 조사·청유·일반적인 ‘지원 사업’ 문구는 강제 검색어에서 제외한다.
- 의도가 유지되는 범위의 관련 표현을 `should`에 둔다. 예: ‘GPU 자동 배분 소프트웨어’의 `오케스트레이터`는 관련 표현 후보이며, 실제 기능은 원문으로 확인한다.
- 질문에 없던 코드·정답 제목·회계·연도를 몰래 추가하지 않는다. 판본이 중요한 질문에서 정보가 부족하면 현재 코퍼스 범위를 명시하고 필요시 확인한다.
- NIPA/IITP 등 별칭은 `expand`로 확장할 수 있다. GPU/NPU, 임차/구매, 출자/출연은 동의어가 아니다. `GPUaaS` 확장은 탐색용이며 계약 방식의 증거가 아니다.
- 첫 검색 상위 5~10개에서 관련 구간을 확인한다. 실패하면 필수 조건을 하나씩 검토해 재검색하며, 완화한 조건을 밝힌다. 같은 실패를 반복하지 말고 확인한 범위와 미확인 이유를 답한다.

```bash
python3 /absolute/path/budget-search/scripts/budget_core.py --root /absolute/workspace search --plan /absolute/path/query.json --limit 10
```

## 근거 확인과 답변

```bash
python3 /absolute/path/budget-search/scripts/budget_core.py --root /absolute/workspace show '반환된 UID 또는 기존 ID' --section summary
```

`show`는 전체 사업 또는 선택 절의 원문을 반환한다. 검색 발췌문은 탐색용이다. 특히 표의 수치로 답하기 전에 제목·단위·열 머리글·해당 행이 함께 포함된 전체 표를 읽는다. 목차 쪽수는 HWPX 렌더링 페이지와 동일하다고 단정하지 않는다.

금액 필터는 검증된 구조화 값에만 적용한다. `amount_unknown_count`와 해당 사업 목록을 확인하고, 미확인 사업을 조건 불일치나 0원으로 처리하지 않는다. 금액의 연도·단계가 맞는지도 확인한다. 정부안 자료의 `조정안(B)`은 `adjusted_proposal`이고 확정 예산이 아니다.

응답은 결론을 먼저 쓰고 다음을 연결한다: 사업명·코드·소관/회계·연도/판본 → 원문 값과 단위 → 원문 파일/행·절 → 검증 범위와 한계. 실제 로컬 파일은 절대 경로 링크를 사용한다. 검토 노트의 해석보다 최신으로 확인된 해당 판본 원문을 우선한다.

결과 없음은 ‘이 판본·검색 범위에서 확인하지 못함’이다. 전체 정부사업에 없다는 의미로 확대하지 않는다. 회사 적합성·공모 가능성·정무적 함의는 원문 사실과 구분하여 요청 범위에서 분석한다. 검색 결과의 수혜자를 곧바로 신청 가능 기업으로 제시하지 않는다.
