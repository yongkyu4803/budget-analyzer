# 예산분석기 1.1.0

HWP·HWPX 예산 사업설명자료를 Markdown으로 바꾸고, 사업별 색인을 만들어 검색하는 도구 묶음입니다.
kordoc(4.22.13) + budget-index + budget-search 세 부분으로 되어 있습니다.

## 받기

[Releases](../../releases)에서 운영체제에 맞는 zip을 받습니다.

| 파일 | 대상 | 설명 |
|---|---|---|
| `kordoc-budget-windows-x64-1.1.0.zip` | Windows 10/11 x64 | 오프라인 키트. Node.js·Python 동봉. 풀고 `check.cmd`부터 실행 |
| `budget-skills-mac-1.1.0.zip` | macOS (Claude Code 스킬) | `kordoc/scripts/ensure-env.sh`가 환경을 준비 |

## 1.0 → 1.1 변경

kordoc 4.22.13은 HWP 본문 구역이 100개를 넘거나 한 구역의 레코드가 50만 개를 넘으면 나머지를 경고 없이 버립니다.
그래서 큰 사업설명자료의 뒤쪽 사업이 빠지고 색인 빌드가 `오류: (719, 777)`처럼 멈췄습니다.
1.1은 이 상한을 구역 2,000개·레코드 500만 개로 올립니다(`patch-limits.cjs`).

- 윈도우 키트: 동봉 kordoc에 미리 적용, `check.cmd`가 상한과 `kit_version`을 확인
- 맥 스킬: `ensure-env.sh`가 설치 때 적용, `--check-only`로 확인

과기정통부 2027 사업설명자료 8권으로 시험해 빠졌던 58개를 포함한 777개 사업이 모두 색인됐습니다.
1.0으로 변환한 Markdown은 다시 변환해야 합니다.

## 기존 사용자 업데이트

`prompts/`의 프롬프트를 코딩 에이전트에 붙여넣고 zip 경로만 바꿉니다.

- [맥](prompts/맥_1.0→1.1_업데이트.md)
- [윈도우](prompts/윈도우_1.0→1.1_업데이트.md)

## 폴더

- `mac/` — 맥용 스킬 묶음 원본(릴리스 zip과 같은 내용)
- `windows/` — 윈도우 키트 원본. 용량 때문에 `runtime/`(Node·Python), `app/node_modules/`, kordoc 소스 zip은 빠져 있고 릴리스 zip에만 있습니다. 다시 묶는 방법은 `windows/developer/BUILD.md`.
- `prompts/` — 1.0 → 1.1 업데이트 프롬프트

## 확인하지 못한 것

윈도우 키트는 맥에서 키트 코드를 실행해 시험했고, 실제 윈도우 PC에서 `.cmd`로 실행하는 시험은 하지 않았습니다.
