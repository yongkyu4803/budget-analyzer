# 예산분석기 1.0 → 1.1 업데이트 프롬프트

이미 예산분석기(kordoc · budget-index · budget-search) 1.0을 쓰고 있는 사람이 아래 프롬프트를 Claude Code에 붙여넣는다.
`[zip 경로]`는 받은 `budget-skills-mac-1.1.0.zip`의 실제 경로로 바꾼다.

---

예산분석기 스킬을 1.1로 업데이트해줘. 새 패키지: [zip 경로]

배경: kordoc 4.22.13은 HWP의 본문 구역이 100개를 넘거나 한 구역의 레코드가 50만 개를 넘으면 나머지를 경고 없이 버린다. 그래서 큰 예산 사업설명자료의 뒤쪽 사업이 Markdown에서 빠지고, budget-index 빌드가 `오류: (719, 777)`처럼 사업 수가 맞지 않아 멈춘다. 1.1은 설치 스크립트가 이 상한을 올리도록 고쳤다.

순서대로 해줘.

1. **현재 설치 확인.** `~/.claude/skills/kordoc`, `~/.claude/skills/budget-index`, `~/.claude/skills/budget-search`가 있는지 본다. 다른 곳에 설치돼 있으면 그 경로를 쓴다. 없으면 멈추고 알려준다.
2. **새 패키지 풀기.** zip을 빈 임시 폴더에 푼다. `budget-skills-mac/VERSION`이 `1.1.0`인지, `README.md`의 1.1.0 변경 내역을 읽는다.
3. **백업.** 기존 `kordoc/scripts/ensure-env.sh`와 `kordoc/SKILL.md`를 `.bak-1.0` 이름으로 복사해 둔다. `engine/node_modules`는 건드리지 않는다.
4. **바뀐 파일만 교체.** 새 패키지에서 아래 3개만 기존 kordoc 스킬 폴더에 복사한다.
   - `kordoc/scripts/patch-limits.cjs` (새 파일)
   - `kordoc/scripts/ensure-env.sh`
   - `kordoc/SKILL.md`
   budget-index·budget-search는 1.0과 같으므로 바꾸지 않는다. 다른 파일이 1.0과 다르면 덮어쓰지 말고 차이를 알려준다.
5. **적용.** `bash ~/.claude/skills/kordoc/scripts/ensure-env.sh`를 실행한다(종료 코드 0, 로그에 `kordoc 상한 올림` 확인). 이어서 `--check-only`로 다시 실행해 `kordoc 상한 확인: 구역 2000, 레코드 5e6`과 종료 코드 0을 확인한다. kordoc이 이미 설치돼 있으면 인터넷은 필요 없다.
6. **기존 변환본 다시 만들기.** 1.0으로 변환한 Markdown은 잘렸을 수 있다. 내가 쓰던 예산 작업 폴더(`.budget-index/config.json`이 있는 폴더)를 찾아 목록을 보여주고, 어느 것을 다시 만들지 물어본다. 고른 폴더마다:
   - 기존 폴더는 그대로 두고 옆에 새 작업 폴더를 만든다(예: `원래이름-v1.1`). 설정 파일 `config.json`은 복사한다.
   - 원본 HWP/HWPX를 kordoc 스킬의 `scripts/convert.py`로 모두 다시 변환한다(이미지 없이, 대용량이면 `--max-unzip-mb 1024`).
   - budget-index의 `build`와 `verify --originals`를 실행한다.
   - 사업 수가 설정의 `expected_programs`와 맞는지, 1.0 대비 사업 수가 얼마나 늘었는지 알려준다.
7. **보고.** 바꾼 파일, 백업 위치, 점검 결과, 다시 만든 작업 폴더와 사업 수를 실제 출력에 근거해 한국어로 짧게 알려준다. 실패하면 멈추고 원인과 출력을 보여준다.

지키기: 기존 작업 폴더·색인·원본 파일을 지우거나 덮어쓰지 않는다. npm·pip·git으로 다른 것을 내려받지 않는다(5단계에서 kordoc이 없을 때의 `npm ci`는 예외). 금액이나 사업 수를 추측하지 않는다.

---
