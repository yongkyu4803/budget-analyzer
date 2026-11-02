# 구조화 검색 계획

`search --plan 파일.json`은 아래 객체를 받는다. 모델이 사용자의 질문만으로 만든 계획을 저장한다. 엔진 자체가 자연어를 의미 분석하는 기능은 없다.

```json
{
  "question": "민간 GPU를 빌려 산학연에 제공하는 사업",
  "must": [["GPU"], ["임차", "임대"], ["산학연"]],
  "should": [["연구자", "수요자"]],
  "exclude": [],
  "filters": {"year": 2027, "stage": "government_proposal"},
  "expand": false
}
```

외부 배열은 AND, 내부 배열은 OR. `should`는 순위 가점이고 필수조건이 아니다. must가 없으면 should 중 하나 이상 관련된 결과를 찾는다. `exclude`는 해당 문자열을 포함하는 사업 전체를 제외하므로 문서가 ‘구매와 임차’를 함께 설명할 가능성이 있으면 쓰지 않는다. 조건은 글의 의미가 아니라 정규화된 문자열에 적용된다.

filters: code, id(기존 ID 또는 UID), volume(정수), account(회계/기금 부분문자열), year(정수), stage(문서 판본), ministry(정식 명칭 또는 코드), scope(programs/context/all). 묵시적 최신 판본 선택은 없다.

금액 검색 예시:

```json
{
  "must": [["AI"]],
  "amount": {"year":2027, "stage":"adjusted_proposal", "unit":"억원", "min":"1000", "label":"program_total"}
}
```

min/max는 포함 경계다. 결과의 `amount_unknown`은 원문 재확인이 필요한 사업이며 ‘조건 미충족’이 아니다. 부분 구조화 상태에서 전체 모집단의 예산액 상위 순위나 조건 충족 총수를 확정하지 않는다.

정확한 사업명은 `search '전체 사업명' --phrase`, 코드는 `search --code 4331-310`. 코드는 중복될 수 있어 결과를 모두 확인한다. `--limit 0`은 전체 반환. 단순 키워드 CLI는 공백 기준 AND, `--expand`는 NIPA/IITP/HPC 등의 등록 별칭을 OR로 확장한다.

순위는 정확한 제목 우선, 목적·산출근거·사업개요 가중치, 희소 검색어 가중치, 같은 본문 블록에서 조건을 함께 만족하는 정도를 사용한다. 통계적 관련성 점수이며 사업 적합성/참여 자격 점수가 아니다.
