# budget-skills-mac

한글 문서 변환·예산사업 색인·검색용 스킬 3개 (macOS). 폴더에는 스킬과 `package-lock.json`만 있다.

| 스킬 | 역할 |
|---|---|
| `kordoc` | HWP/HWPX/DOCX/XLSX → Markdown, HWPX 생성·검증 |
| `budget-index` | 예산사업 단위 색인(SQLite) 생성·검증 |
| `budget-search` | 색인 검색·원문 근거 확인 |

설치: 세 폴더를 `~/.claude/skills/`에 복사한다.
첫 실행 전 `bash kordoc/scripts/ensure-env.sh`가 Node/Python을 자체 시험하고, 없으면 Node는 공식 tar.gz(SHA-256 검증), Python은 Homebrew로 설치하고, kordoc은 `npm ci`로 설치한다. 인터넷(nodejs.org, npm 레지스트리)이 필요하다.
기본 인덱서는 과기정통부 `(번호) 사업명 (코드)` + 반복 통합 목차 구조만 지원한다. PDF·OCR은 미포함.

## 변경 내역

### 1.1.0 (2026-11-02)
- **큰 HWP 뒤쪽이 잘리던 문제 수정.** kordoc 4.22.13은 HWP의 본문 구역이 100개를 넘거나 한 구역의 레코드가 50만 개를 넘으면 나머지를 경고 없이 버린다. 과기정통부 2027 사업설명자료에서 1권(사업 5개)·5권(9개)·6권(43개)이 잘려 색인이 `(719, 777)` 오류로 멈췄다.
- `kordoc/scripts/patch-limits.cjs` 추가. 상한을 구역 2,000개·레코드 500만 개로 올린다.
- `ensure-env.sh`가 설치할 때마다 위 수정을 적용하고, `--check-only`는 적용 여부를 확인한다.
- 1.0으로 변환한 Markdown은 잘렸을 수 있으므로, 업데이트 후 원본 HWP를 다시 변환하고 색인을 다시 만든다.
