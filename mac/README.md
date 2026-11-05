# budget-skills-mac

한글 문서 변환·예산사업 색인·검색용 스킬 3개 (macOS). 폴더에는 스킬과 `package-lock.json`만 있다.

| 스킬 | 역할 |
|---|---|
| `kordoc` | HWP/HWPX/DOCX/XLSX → Markdown, HWPX 생성·검증 |
| `budget-index` | 예산사업 단위 색인(SQLite) 생성·검증 |
| `budget-search` | 색인 검색·원문 근거 확인 |

설치: 세 폴더를 `~/.claude/skills/`에 복사한다.
첫 실행 전 `bash kordoc/scripts/ensure-env.sh`가 Node/Python을 자체 시험하고, 없으면 Node는 공식 tar.gz(SHA-256 검증), Python은 Homebrew로 설치하고, kordoc은 `npm ci`로 설치한다. 인터넷(nodejs.org, npm 레지스트리)이 필요하다.
`budget-index`·`budget-search`는 국회 상임위 검토보고서 색인(`scripts/review_core.py`)도 포함한다. 과방위의 2027년도 과기정통부 소관 보고서 1건으로만 검증했고 다른 상임위는 실물로 확인하지 않았다.
기본 인덱서는 과기정통부 `(번호) 사업명 (코드)` + 반복 통합 목차 구조만 지원한다. PDF·OCR은 미포함.

## 변경 내역

### 1.1.1 (2026-11-05, 릴리스 zip 미작성)
- **국회 상임위 검토보고서 색인 추가.** `budget-index/scripts/review_core.py`, `review_adapter.py`(`budget-search`에도 같은 파일). 사업설명자료 색인과 별도의 `.budget-index/review.sqlite`를 만들고 사업 코드와 제목으로 연결한다(코드는 회계가 다르면 중복되므로 코드만으로 붙이지 않는다). 목차와 본문 경계를 대조해 어긋나면 게시하지 않는다.
- 설정은 `.budget-index/review-config.json`([예시](budget-index/references/review-config-example.json)), 데이터 계약은 [review-schema.md](budget-index/references/review-schema.md).
- 검증: 과방위 2027년도 과기정통부 소관 검토보고서(HWP 607쪽)에서 소관과 18곳·사업 60개·쟁점 152개가 목차와 일치. 다른 상임위·부처는 미검증. 기존 `budget_core.py`는 바꾸지 않았다.

### 1.1.0 (2026-11-02)
- **큰 HWP 뒤쪽이 잘리던 문제 수정.** kordoc 4.22.13은 HWP의 본문 구역이 100개를 넘거나 한 구역의 레코드가 50만 개를 넘으면 나머지를 경고 없이 버린다. 과기정통부 2027 사업설명자료에서 1권(사업 5개)·5권(9개)·6권(43개)이 잘려 색인이 `(719, 777)` 오류로 멈췄다.
- `kordoc/scripts/patch-limits.cjs` 추가. 상한을 구역 2,000개·레코드 500만 개로 올린다.
- `ensure-env.sh`가 설치할 때마다 위 수정을 적용하고, `--check-only`는 적용 여부를 확인한다.
- 1.0으로 변환한 Markdown은 잘렸을 수 있으므로, 업데이트 후 원본 HWP를 다시 변환하고 색인을 다시 만든다.
