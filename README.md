# 예산분석기 1.1.1

정부 예산 사업설명자료(HWP·HWPX)를 AI가 읽을 수 있는 글(Markdown)로 바꾸고, 사업별로 색인해서 검색하는 도구입니다.
Claude Code·Codex 같은 코딩 에이전트에 붙여서 씁니다.

| 구성 | 하는 일 |
|---|---|
| kordoc | HWP·HWPX·DOCX·XLSX 문서를 Markdown으로 변환 |
| budget-index | 변환한 문서를 사업 단위로 쪼개 색인 생성 |
| budget-search | 색인에서 사업 검색, 원문 표 확인 |
| budget-index / budget-search의 **review** | 국회 상임위 예산안 검토보고서(전문위원 검토의견)를 사업·쟁점 단위로 색인하고, 사업 코드·제목으로 사업설명자료와 연결 (신규) |
| budget-written-question | 정리한 증액·감액 내용을 예결위 서면질의서(HWPX) 양식에 채움 (맥 전용) |

**가장 쉬운 설치**: Claude Code·Codex 같은 코딩 에이전트에 이렇게 부탁하세요.

```
https://github.com/yongkyu4803/budget-analyzer 의 README를 읽고 예산분석기를 설치해줘.
```

직접 설치하려면 [1번](#1-내-컴퓨터에-맞는-파일-받기)부터 따라 하세요.

---

## 코딩 에이전트에게 (설치 지침)

사용자가 이 저장소로 설치를 부탁하면 이 절을 따른다. 아래 명령은 그대로 실행할 수 있게 썼다.

**지킬 것**

1. 운영체제를 먼저 확인한다. Windows x64는 [A](#a-windows-x64), macOS는 [B](#b-macos)를 따른다. 그 밖의 운영체제(Linux 등)는 지원하지 않으므로 멈추고 알린다.
2. 설치 파일은 **릴리스 zip**에서 받는다. 저장소를 clone해서 `windows/`·`mac/` 폴더를 설치에 쓰지 않는다. `windows/`에는 Node·Python 런타임과 kordoc 의존성이 빠져 있다.
3. 기존 파일을 덮어쓰지 않는다. 설치 위치나 같은 이름의 스킬이 이미 있으면 멈추고 사용자에게 알린다. 1.0 또는 1.1.0을 쓰던 사용자라면 `prompts/`의 업데이트 프롬프트를 따른다.
4. 스킬 폴더는 지금 쓰는 에이전트에 맞춘다. Claude Code는 `~/.claude/skills`, Codex는 `~/.codex/skills`다. 서면질의서 스킬은 Claude Code(macOS)에서만 쓴다.
5. 관리자 권한, 전역 설치, PATH 변경을 하지 않는다. 예외로, macOS에 Python 3.10 이상이 없으면 설치 전에 사용자에게 묻는다.
6. 윈도우 `START.cmd`는 사람용 메뉴라 입력을 기다린다. 에이전트는 `check.cmd`와 `kit.cmd`만 쓴다.
7. 끝나면 설치 경로, 점검 결과(실제 출력), 그리고 새 세션을 열어야 스킬이 보인다는 점을 사용자에게 알린다.

### A. Windows x64

아래를 `install-budget.ps1`로 저장해 실행한다. bash 환경이라면 `powershell -NoProfile -ExecutionPolicy Bypass -File install-budget.ps1`로 실행한다. 설치 위치 `C:\kordoc-budget-windows-x64`를 만들 수 없으면 `$kit`과 압축 풀 위치를 `$env:USERPROFILE` 아래로 바꾼다. 경로는 짧게 둔다.

```powershell
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$kit = 'C:\kordoc-budget-windows-x64'
if (Test-Path $kit) { throw "STOP: $kit already exists" }
$zip = Join-Path $env:TEMP 'kordoc-budget-windows-x64-1.1.1.zip'
Invoke-WebRequest -UseBasicParsing -OutFile $zip -Uri 'https://github.com/yongkyu4803/budget-analyzer/releases/download/v1.1.1/kordoc-budget-windows-x64-1.1.1.zip'
$hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
if ($hash -ne 'fc86744182257d3d6783f1a0504e7c5957efe4151056888b09262147c9d2ac46') { throw "SHA-256 mismatch: $hash" }
Unblock-File $zip
Expand-Archive -Path $zip -DestinationPath (Split-Path $kit)
& "$kit\check.cmd"
if ($LASTEXITCODE -ne 0) { throw "check.cmd failed: exit $LASTEXITCODE" }
```

성공 기준: 종료 코드 0, 그리고 출력에 `"ok": true`, `"kit_version": "1.1.1"`, `"test_mode": "windows-bundled-runtime"`이 있어야 한다.
실패하면 출력을 그대로 보여주고 멈춘다. 회사 PC에서 exe 실행이 막혔다면 사용자가 전산 담당자에게 문의해야 한다.

이어서 스킬을 연결한다. Codex라면 `.claude`를 `.codex`로 바꾼다. 같은 이름의 스킬이 있으면 `kit.cmd`가 알아서 설치를 멈춘다.

```powershell
& 'C:\kordoc-budget-windows-x64\kit.cmd' install-skills --target "$env:USERPROFILE\.claude\skills"
```

설치 뒤에는 키트 폴더를 옮기거나 지우면 안 된다고 사용자에게 알린다. 각 스킬의 `portable-kit.json`이 이 폴더를 가리킨다.

### B. macOS

먼저 `python3 --version`으로 Python이 3.10 이상인지 확인한다. 3.10보다 낮거나 Python이 없으면 사용자에게 알린다. 그다음 [python.org 설치 파일](https://www.python.org/downloads/macos/)로 직접 설치할지, Homebrew로 `brew install python`을 실행해도 될지 묻는다. Node.js는 아래 스크립트가 공식 파일을 SHA-256으로 확인한 뒤 스킬 폴더 안에만 설치한다. 처음 한 번은 인터넷이 필요하다.

```bash
bash <<'EOF'
set -e
SK="$HOME/.claude/skills"   # Codex면 "$HOME/.codex/skills"
for s in kordoc budget-index budget-search; do
  if [ -e "$SK/$s" ]; then echo "STOP: $SK/$s already exists"; exit 1; fi
done
TMP="$(mktemp -d)"
curl -fsSL -o "$TMP/mac.zip" https://github.com/yongkyu4803/budget-analyzer/releases/download/v1.1.1/budget-skills-mac-1.1.1.zip
unzip -q "$TMP/mac.zip" -d "$TMP"
mkdir -p "$SK"
cp -R "$TMP/budget-skills-mac/kordoc" "$TMP/budget-skills-mac/budget-index" "$TMP/budget-skills-mac/budget-search" "$SK/"
bash "$SK/kordoc/scripts/ensure-env.sh"
EOF
```

성공 기준: 종료 코드 0, 그리고 마지막 출력의 JSON에 `"ok": true`와 `"kordoc_version": "4.22.13"`이 있어야 한다. 이어서 아래 명령으로 다시 점검한다. 종료 코드 0이면 된다.

```bash
bash ~/.claude/skills/kordoc/scripts/ensure-env.sh --check-only
```

**서면질의서 스킬** (사용자가 원할 때, Claude Code만):

```bash
bash <<'EOF'
set -e
SK="$HOME/.claude/skills"
if [ -e "$SK/budget-written-question" ]; then echo "STOP: $SK/budget-written-question already exists"; exit 1; fi
if [ ! -f "$SK/kordoc/engine/env.json" ]; then echo "STOP: install the macOS kordoc skill first (section B)"; exit 1; fi
TMP="$(mktemp -d)"
curl -fsSL -o "$TMP/wq.zip" https://github.com/yongkyu4803/budget-analyzer/releases/download/v1.1.1/budget-written-question-skill.zip
unzip -q "$TMP/wq.zip" -d "$TMP"
cp -R "$TMP/budget-written-question" "$SK/"
echo "installed: $SK/budget-written-question"
EOF
```

---

## 1. 내 컴퓨터에 맞는 파일 받기

[Releases](../../releases/latest) 페이지 아래쪽 **Assets**에서 받습니다. 저장소의 초록색 `Code` 버튼으로 받는 파일은 프로그램이 빠진 원본이라 설치용이 아닙니다.

| 내 컴퓨터 | 받을 파일 |
|---|---|
| 윈도우 | `kordoc-budget-windows-x64-1.1.1.zip` (약 71MB) |
| 맥 | `budget-skills-mac-1.1.1.zip` |
| 맥 + 서면질의서도 쓸 때 | 위 파일과 `budget-written-question-skill.zip` |

이미 1.0 또는 1.1.0을 쓰고 있다면 아래 [이전 버전 사용자](#이전-버전-사용자) 항목으로 가세요.

---

## 2. 윈도우 설치

인터넷 연결, 관리자 권한, 별도 프로그램 설치 없이 동작합니다. Node.js와 Python이 zip 안에 들어 있습니다.

### 2-1. 압축 풀기

1. 받은 zip 파일을 마우스 오른쪽 버튼으로 누르고 **속성**을 엽니다. 아래에 **차단 해제** 체크 상자가 있으면 체크하고 확인을 누릅니다. 이렇게 하면 실행할 때 나오는 경고가 줄어듭니다.
2. zip 파일을 다시 오른쪽 버튼으로 누르고 **압축 풀기**를 고릅니다. 대상 폴더 칸에 `C:\` 만 적고 **압축 풀기**를 누릅니다.
3. `C:\kordoc-budget-windows-x64` 폴더가 생겼는지 확인합니다.

바탕화면이나 다운로드 폴더처럼 경로가 긴 곳에 풀면 "경로가 너무 길다"는 오류가 날 수 있습니다. C 드라이브 바로 아래처럼 짧은 경로에 두세요.

### 2-2. 잘 설치됐는지 확인

1. `C:\kordoc-budget-windows-x64` 폴더 안의 **START.cmd**를 더블클릭합니다.
   "Windows의 PC 보호" 창이 뜨면 **추가 정보 → 실행**을 누릅니다.
2. 검은 창에 메뉴가 나오면 `1`을 입력하고 Enter를 누릅니다.
3. 결과에 아래 두 줄이 보이면 성공입니다.
   ```
   "ok": true,
   "kit_version": "1.1.1",
   ```
4. 아무 키나 눌러 창을 닫습니다.

`"ok": false`가 나오면 [문제가 생겼을 때](#문제가-생겼을-때)를 보세요.

### 2-3. 코딩 에이전트에 연결

**방법 A. 스킬로 설치 (Claude Code를 쓴다면 이 방법을 권합니다)**

시작 메뉴에서 `cmd`를 검색해 **명령 프롬프트**를 열고, 아래 두 줄을 한 줄씩 붙여넣고 Enter를 누릅니다.

```bat
cd /d C:\kordoc-budget-windows-x64
```

```bat
kit.cmd install-skills --target "%USERPROFILE%\.claude\skills"
```

Codex를 쓴다면 둘째 줄의 `.claude`를 `.codex`로 바꿉니다.
설치가 끝나면 Claude Code를 새로 열어야 스킬이 보입니다. 설치한 뒤에는 `C:\kordoc-budget-windows-x64` 폴더를 옮기거나 지우지 마세요. 스킬이 이 폴더의 프로그램을 씁니다.

**방법 B. 프롬프트로 바로 쓰기**

폴더 안 `AI-START.txt`의 프롬프트를 복사해 코딩 에이전트에 붙여넣습니다. `[패키지 경로]`는 `C:\kordoc-budget-windows-x64`로, `[문서 폴더]`는 HWP 파일이 있는 폴더로 바꿉니다.

### 2-4. 써 보기

1. HWP 예산 자료를 한 폴더에 모읍니다(예: `C:\예산자료`). 파일 이름에 `(1권)`, `(2권)`처럼 권 번호가 있어야 합니다.
2. 코딩 에이전트에 이렇게 부탁합니다.
   ```
   C:\예산자료 폴더의 HWP를 예산분석기로 변환하고 색인을 만든 다음, GPU 관련 사업을 찾아줘.
   ```

에이전트 없이 직접 실행하는 명령은 폴더 안 `START-HERE.txt`에 있습니다.

---

## 3. 맥 설치

Claude Code가 설치돼 있어야 합니다. 처음 한 번은 인터넷이 필요합니다. 이때 Node.js와 kordoc을 자동으로 내려받습니다.

### 3-1. 압축 풀기

다운로드 폴더에서 `budget-skills-mac-1.1.1.zip`을 더블클릭하면 `budget-skills-mac` 폴더가 생깁니다.

### 3-2. 스킬 복사

**터미널**(Spotlight에서 `터미널` 검색)을 열고 아래 두 줄을 한 줄씩 붙여넣고 Enter를 누릅니다.

```bash
mkdir -p ~/.claude/skills
```

```bash
cp -R ~/Downloads/budget-skills-mac/kordoc ~/Downloads/budget-skills-mac/budget-index ~/Downloads/budget-skills-mac/budget-search ~/.claude/skills/
```

`~/.claude/skills`에 같은 이름의 폴더가 이미 있으면 위 명령이 덮어씁니다. 1.0 또는 1.1.0을 쓰던 중이라면 이 명령 대신 [이전 버전 사용자](#이전-버전-사용자) 방법을 쓰세요.

### 3-3. 실행 환경 준비

```bash
bash ~/.claude/skills/kordoc/scripts/ensure-env.sh
```

1~2분쯤 걸립니다. 마지막에 `"ok": true`가 나오면 성공입니다.

- **Python 3.10 이상이 없다는 오류가 날 때**: [python.org 맥용 설치 파일](https://www.python.org/downloads/macos/)을 받아 설치한 뒤, 터미널을 새로 열고 위 명령을 다시 실행합니다. Homebrew가 있으면 스크립트가 알아서 설치합니다.
- **Node.js**는 없어도 됩니다. 스크립트가 공식 파일을 받아 스킬 폴더 안에만 설치합니다.

### 3-4. 써 보기

Claude Code를 새로 열고 이렇게 부탁합니다.

```
~/Documents/예산자료 폴더의 HWP를 예산분석기로 변환하고 색인을 만든 다음, GPU 관련 사업을 찾아줘.
```

---

## 4. 서면질의서 스킬 설치 (맥)

예산분석기로 찾은 사업의 증액·감액 요구, 부대의견, 정책질의를 예결위 서면질의 양식(2027년도 예산안 HWPX)에 서식 그대로 채웁니다. 사업을 찾거나 금액을 계산하지는 않습니다. 문서 작성만 합니다.

1. 3번의 맥 설치를 먼저 끝냅니다. 이 스킬도 kordoc을 씁니다.
2. `budget-written-question-skill.zip`을 더블클릭해 풉니다. 다운로드 폴더에 `budget-written-question-skill` 폴더가 생깁니다.
3. 터미널에서 실행합니다.
   ```bash
   cp -R ~/Downloads/budget-written-question-skill/budget-written-question ~/.claude/skills/
   ```
4. Claude Code를 새로 열고 이렇게 부탁합니다.
   ```
   예산분석기로 모두의 AI 사업을 찾아서 GPU 예산 20억 증액 서면질의서를 써줘. 의원명은 홍길동으로.
   ```
5. 만들어진 HWPX는 한글에서 열어 화면 배치를 확인합니다.

zip 안에도 `kordoc` 폴더가 있지만 3번에서 설치한 것과 같으므로 복사하지 않아도 됩니다. 3번을 건너뛰었다면 이 `kordoc` 폴더도 `~/.claude/skills/`에 복사하고 3-3을 실행하세요.

윈도우에서는 아직 시험하지 않았습니다.

---

## 이전 버전 사용자

1.0 또는 1.1.0을 쓰고 있다면 아래 프롬프트로 1.1.1로 올립니다.

- **1.1.1** (2026-11-05): 국회 상임위 검토보고서 색인(review)을 추가했습니다. 기존 사업설명자료 색인은 그대로입니다.
- **1.1.0**: 1.0의 kordoc은 큰 HWP 문서의 뒤쪽을 경고 없이 버렸습니다. 그래서 사업이 빠지거나 색인 만들기가 `오류: (719, 777)`처럼 멈췄습니다. 1.1.0에서 고쳤습니다. 1.0에서 올라오는 경우에만 해당합니다.

`prompts/` 폴더의 프롬프트를 열어 내용을 복사하고 코딩 에이전트에 붙여넣습니다. `[zip 경로]`는 받은 zip 파일 경로로 바꿉니다.

- 윈도우: [prompts/윈도우_업데이트_1.1.1.md](prompts/윈도우_업데이트_1.1.1.md)
- 맥: [prompts/맥_업데이트_1.1.1.md](prompts/맥_업데이트_1.1.1.md)

에이전트가 기존 파일을 지우지 않고 새 버전을 설치합니다. 1.0으로 만든 작업 폴더는 새 폴더에 다시 변환합니다. 1.1.0에서 올라오는 경우에는 다시 변환할 필요가 없습니다.

---

## 문제가 생겼을 때

| 증상 | 해결 |
|---|---|
| START.cmd 창이 바로 닫힘 | 명령 프롬프트에서 `cd /d C:\kordoc-budget-windows-x64` 다음 `check.cmd`를 실행해 오류 문구를 확인 |
| "경로가 너무 깁니다" | `C:\`처럼 짧은 경로에 다시 풀기 |
| 회사 PC에서 실행이 막힘 | 보안 정책으로 exe 실행이 막힌 경우라 전산 담당자에게 문의 |
| check에서 manifest 오류 | 압축이 덜 풀렸거나 파일이 바뀐 것. zip을 새로 받아 다시 풀기 |
| `install-skills`가 "기존 스킬을 보존하기 위해 중단" | 같은 이름의 스킬이 이미 있음. 이전 버전 사용자는 업데이트 프롬프트를 사용 |
| Claude Code에 스킬이 안 보임 | Claude Code를 완전히 닫았다 다시 열기 |
| 사업이 일부만 색인됨 | 1.0으로 변환한 Markdown일 수 있음. 1.1로 원본을 다시 변환 |

---

## 국회 검토보고서 색인 (신규)

사업설명자료는 "사업이 무엇이고 얼마인가"를, 국회 상임위원회 전문위원이 쓴 **예산안 검토보고서**는 "그 사업에서 무엇이 문제로 지적됐는가"를 담고 있습니다. 두 문서는 형식이 달라서 같은 색인기로 읽지 않고, 별도 색인(`review.sqlite`)을 만들어 **사업 코드(예: `1111-111`)와 제목으로 연결**해서 봅니다. 합치지 않고 연결만 합니다. 사업 코드는 회계가 다르면 중복되므로(2027년 과기정통부 자료에서 36개 코드) 코드만으로 붙이지 않고, 제목이 맞는 사업만 연결합니다.

- 소관과 → 회계·기금 → 사업(코드) → 쟁점(가·나·다…) 순서로 나누고, 쟁점마다 표 제목·`(단위: …)`·원문 행 번호를 보존합니다.
- 목차와 본문의 소관과·사업이 어긋나면 색인을 게시하지 않고 오류를 냅니다(기존 색인은 그대로 둡니다).
- 검색: `review_core.py search "GPU 임차"`. 사업과 쟁점 조회: `review_core.py show 1111-111 --issue 임차`. 윈도우는 `review.cmd`.

**검증 범위 — 과방위 기준.** 2027년도 과학기술정보통신부 소관 예산안·기금운용계획안 검토보고서(**과학기술정보방송통신위원회**, 과방위, 2026. 11., HWP 607쪽) 1건으로 만들고 검증했습니다. 목차와 본문의 소관과 18곳·사업 60개·쟁점 152개가 일치했습니다. 같은 부처 2027년 정부안 사업설명자료 8권(777개 사업)과는 60개 항목 중 55개가 연결됐고, 나머지는 코드 없는 총괄 주제 4개와 세입 항목 1개입니다.
**다른 상임위(기재위, 국토위, 복지위 등)도 같은 편집 관례를 따를 것으로 보고 같은 어댑터로 시도할 수 있게 했지만, 실제 자료로 확인하지 않았습니다.** 처음 쓸 때 `build` 출력의 오류·경고와 `.budget-index/REVIEW_CATALOG.md`를 꼭 확인하세요. 목차 대조에서 막히면 편집 형식이 다른 것이므로 `patterns` 설정이나 어댑터 보완이 필요합니다.

**윈도우는 실기에서 시험하지 못했습니다.** `windows/`의 review 기능(`review.cmd`, `kit.cmd init --review`, `check.cmd`의 가상 보고서 시험)은 macOS의 호스트 Python으로만 실행해 봤습니다. 윈도우 PC에서는 `check.cmd`로 먼저 확인하세요.

이 기능은 1.1.1부터 들어 있습니다. 업데이트 방법은 아래 [이전 버전 사용자](#이전-버전-사용자)를 보세요. 윈도우 zip은 `windows/developer/BUILD.md`대로 `repack.py`로 다시 만듭니다.

사용법은 `mac/budget-index/SKILL.md`의 "국회 검토보고서 색인" 절, 데이터 계약은 `mac/budget-index/references/review-schema.md`에 있습니다.

---

## 알아둘 점

- 사업설명자료 색인 기능은 과기정통부 사업설명자료 형식(`(번호) 사업명 (코드)` + 반복 목차)에 맞춰져 있습니다. 2027년 정부안 8권(777개 사업)으로 시험했습니다. 다른 부처나 다른 연도 자료는 설정을 바꿔야 하고, 편집 형식이 다르면 안 될 수 있습니다.
- 검토보고서 색인은 과방위 보고서 1건으로만 검증했습니다(위 절 참고).
- PDF·스캔 이미지(OCR)는 지원하지 않습니다.
- 금액은 검색 결과만 보지 말고 원문 표의 연도·단위와 함께 확인하세요.
- 윈도우 키트는 맥에서 같은 코드로 시험했습니다. 실제 윈도우 PC에서는 아직 실행해 보지 않았습니다. 받은 PC에서 2-2 확인을 꼭 하세요.

## 저장소 폴더

- `windows/` — 윈도우 키트 원본. 용량 때문에 `runtime/`(Node·Python), `app/node_modules/`, kordoc 소스 zip은 빠져 있고 릴리스 zip에만 있습니다. 다시 묶는 방법은 `windows/developer/BUILD.md`.
- `mac/` — 맥용 스킬 묶음 원본(릴리스 zip과 같은 내용)
- `written-question/` — 서면질의서 작성 스킬 원본
- `prompts/` — 1.0·1.1.0 → 1.1.1 업데이트 프롬프트
