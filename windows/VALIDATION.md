# 검증 기록

검증일: 2026-10-19(1.0.0), 2026-11-02(1.1.0), 2026-11-05(1.1.1). 이 저장소의 버전: 1.1.1(릴리스 zip은 아직 만들지 않았다. 마지막 배포본은 1.1.0).

## 1.1.0 변경과 확인

- kordoc 4.22.13의 HWP5 읽기 상한 `MAX_SECTIONS`(100)과 `MAX_RECORDS`(5e5)를 동봉 `app/node_modules/kordoc/dist`에서 2000과 5e6으로 올렸다(`developer/patch-limits.cjs`). 원래 상한을 넘는 부분은 경고 없이 버려졌다.
- 실제 과기정통부 2027 정부안 HWP 8권 중 1권(구역 1개, 레코드 532,243개), 5권(구역 109개), 6권(구역 142개)이 상한을 넘었다. 1.0.0으로는 색인이 `(719, 777)` 오류로 멈췄다.
- 1.1.0의 dist로 8권을 다시 변환해 777개 사업을 색인하고 원본 대조까지 통과했다(macOS 호스트 Node 시험).
- `check`가 동봉 dist의 상한을 검사하고 결과에 `kordoc_hwp_limits`를 기록한다.
- Windows 실기 실행은 1.0.0과 마찬가지로 아직 시험하지 않았다.

## 1.1.1 변경과 확인: 검토보고서 색인 (review)

- `review.cmd`, `skills/*/scripts/review_core.py`·`review_adapter.py`, `kit.cmd init --review`, `samples/review-*`를 추가했다. `check`가 가상 검토보고서로 목차 대조·색인·검색·쟁점 조회를 추가로 시험한다. 이 변경으로 `MANIFEST.json`의 해당 파일 해시를 갱신했으나 ZIP 전체를 `repack.py`로 다시 만들지는 않았다. 배포 전에 `developer/BUILD.md`대로 repack하고 `check`를 다시 실행한다.
- 시험한 자료: 2027년도 과학기술정보통신부 소관 예산안·기금운용계획안 검토보고서(과학기술정보방송통신위원회, 과방위, 2026. 11., HWP 607쪽). 변환한 Markdown(45,496줄)에서 소관과 18곳·사업 60개·쟁점 152개가 목차와 일치했고, 무작위 20개 사업의 머리글·쟁점 경계·끝 행을 원문 줄과 대조했다. 이 시험은 macOS 호스트 Python으로 했다. **Windows 실기에서는 실행하지 않았다.**
- 사업설명자료와의 연결(macOS 호스트): 같은 부처 2027년 정부안 사업설명자료 HWP 8권(0901)을 변환해 777개 사업을 색인하고 검토보고서와 연결했다. 60개 항목 중 55개가 연결됐고(제목 완전 일치 51, 포함 2, 유사 2) 나머지는 코드 없는 총괄 주제 4개와 세입 항목 1개다. 코드가 회계별로 중복되는 사례(36개 코드)를 확인해, 코드만으로 연결하지 않고 제목이 맞는 사업만 연결하도록 했다.
- 단위 시험: `developer/test_review.py` 9개, `test_portable.py`에 review 시험 1개를 추가했다(총 9개). 기존 `test_budget.py` 17개는 그대로 통과한다.
- 다른 상임위·부처·연도의 보고서는 시험하지 않았다. 처음 쓸 때 `build`의 `toc_check`와 `REVIEW_CATALOG.md`를 확인한다.

## 확인 완료

- Node.js 24.22.0 Windows x64 ZIP과 Python 3.14.8 임베디드 x64 ZIP의 SHA-256을 공식 배포 목록과 대조했다. `provenance.json`에 URL과 해시를 기록했다.
- 두 실행 파일의 PE 헤더가 x64(0x8664)임을 확인했다. Python에는 SQLite 확장·DLL과 필요한 런타임 DLL이 동봉돼 있다.
- kordoc 4.22.13의 필수 JS 의존성을 실제 설치했다. 선택 의존성·설치 스크립트는 사용하지 않았다. 이 JS 의존성 트리에 `.node/.exe/.dll/.so/.dylib`가 없고 심볼릭 링크가 없음을 확인했다.
- 가상 HWPX → Markdown → 예산 인덱스 → GPU 임차 검색 → 원문 표의 연도·단위·1,500 값 확인을 통과했다. 가상 2개 사업 중 GPU 임차 사업 1개가 검색됐다.
- 예산 런타임 단위 테스트 17개를 통과했다. 판본·금액·본문 경계·변경 감지·원문 인용·폴더 이동을 검사했다.
- 배포 실행기 테스트 8개를 통과했다. 출력/설정/스킬 덮어쓰기 방지, 변환 실패 시 부분 결과 미게시, 한도 검사, 임시 HWPX의 XML 바이트 보존·BinData 제외를 검사했다.
- 세 스킬의 frontmatter와 형식을 `skill-creator/quick_validate.py`로 검증했다.
- 실제 과기정통부 예산자료 HWPX 8권을 이미지 없이 새로 변환하고 777개 사업을 색인했다. 원본 8개 해시 검증과 GPU+임차 검색(10개 결과)을 통과했다. 기존 인덱스와 전체 777개 사업의 ID·사업명·코드·회계가 일치했다. 실제 자료와 생성한 DB는 이 ZIP에 넣지 않았다.
- 위 실제 자료의 Markdown 합계는 33,929,563바이트였다. 해당 호스트의 변환·색인·검증·검색 전체 시험은 약 80초였다. 다른 PC의 속도를 보장하는 수치는 아니다.

## 실행 환경과 미확인 범위

코드 시험 환경은 macOS, Node.js 24.15.0, Python 3.14.5였다. 번들에는 별도로 확보한 Windows x64 Node.js 24.22.0과 Python 3.14.8이 들어 있다. Windows 실기에서 `.cmd` 및 포함된 EXE를 실행하는 시험은 아직 하지 않았다. 같은 메이저 버전의 호스트 코드 시험을 Windows 실행 검증으로 간주하지 않는다.

받는 PC에서 `check.cmd` 또는 `START.cmd`의 1번 메뉴를 실행하면 포함된 Windows 런타임으로 같은 파이프라인을 시험하고 `diagnostics/last-check.json`에 결과를 남긴다. `test_mode`가 `windows-bundled-runtime`, `ok`가 `true`인지 확인한다.

KORDOC_OFFLINE=1을 적용해 시험했다. OS 수준 패킷 캡처·전면 네트워크 차단 시험은 하지 않았다. PDF·OCR·PNG/PDF 렌더용 선택 엔진은 포함하지 않았고 시험 대상이 아니다. DOCX·XLS·XLSX·HWP 3.x/5.x의 모든 변종을 별도로 회귀 시험하지 않았다.

HWPX의 이미지 없는 변환에서는 임시 읽기용 사본에서 BinData만 제외한다. XML 본문·표·서식 데이터는 그대로 전달하고 원본 HWPX는 변경하지 않는다. 실제 8권에서 그림을 제외한 내부 항목은 11~152개, 압축 해제 크기는 약 73~99 MiB로 기본 한도 안이었다. 이미지 포함 변환은 원본 전체를 처리하므로 파일 수·크기 한도로 실패할 수 있다.

## 출처

- [kordoc v4.22.13 소스](https://github.com/chrisryugj/kordoc/tree/v4.22.13), [공식 오프라인 배포 안내](https://github.com/chrisryugj/kordoc/blob/v4.22.13/docs/offline-deployment.md)
- [Node.js 24.22.0 공식 체크섬](https://nodejs.org/dist/v24.22.0/SHASUMS256.txt)
- [Python 3.14.8 Windows 공식 배포 목록](https://www.python.org/ftp/python/3.14.8/windows-3.14.8.json)

SHA-256 manifest는 파일 누락·변경을 확인하기 위한 자료이며 발행자 서명은 아니다.
