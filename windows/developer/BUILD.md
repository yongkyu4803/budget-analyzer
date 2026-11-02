# 소스와 재배포

실행에는 인터넷이나 npm/pip가 필요하지 않다. `app/portable.py`와 `skills/*/scripts/`가 직접 수정할 수 있는 Python 소스이며, kordoc의 TypeScript 원본은 `developer/kordoc-v4.22.13-source.zip`이다. 이 ZIP의 소스 버전은 실행 패키지와 같은 태그이나, 실행 dist는 npm 공식 패키지에서 가져왔다. 바이트 단위 재현 빌드를 주장하지 않는다.

`app/package-lock.json`은 실제 설치에 사용한 의존성 잠금 파일이다. 새 빌드를 준비하는 배포자만 인터넷이 되는 개발 PC에서 `npm ci --omit=optional --omit=dev --ignore-scripts --no-audit --no-fund`로 복구할 수 있다. 최종 사용자에게 이 명령을 실행시키지 않는다. 다시 설치했다면 `node developer/patch-limits.cjs app/node_modules/kordoc/dist`로 HWP 읽기 상한을 다시 올리고 `--check`로 확인한다(1.1.0부터). npm은 Windows 실행 번들에 포함하지 않았다.

Node.js와 Python의 원본 다운로드 URL·SHA-256은 `provenance.json`에 있다. Node ZIP의 node.exe·LICENSE·README.md를 동봉하고, Python 임베디드 ZIP은 전체를 동봉했다. Node와 Python 배포 파일의 SHA를 공식 배포 목록과 대조했고 PE Machine 0x8664를 확인했다. 선택 네이티브 모듈은 설치하지 않았으며 JavaScript 의존성에 .node/.so/.dylib/.dll/.exe 파일이 없는지 검사했다. npm .bin 심볼릭 링크는 쓰지 않으므로 배포에서 제외했다.

kordoc 자체를 수정·빌드하려면 소스 ZIP을 별도 개발 폴더에 풀고 그 레포의 빌드 절차를 따른다. upstream 개발용 의존성 전체는 동봉하지 않았다. PDF/OCR 등 선택 기능을 추가할 때는 Windows x64에서 해당 의존성을 준비하고 실제 Windows 테스트 및 새 라이선스 고지를 추가한다.

## 수정 후 시험과 ZIP 재생성

Windows CMD, 패키지 폴더 기준:

```bat
runtime\python\python.exe -X utf8 -B developer\test_budget.py
runtime\python\python.exe -X utf8 -B developer\test_portable.py
runtime\python\python.exe -X utf8 -B developer\repack.py --output ..\kordoc-budget-custom.zip
check.cmd
```

repack은 manifest를 재작성한다. check는 현재 코드로 만든 manifest 검증 후 가상 HWPX 변환부터 인덱스·검색·금액 표 확인까지 실행한다. check가 성공한 뒤에만 재배포한다. 실패하면 배포하지 말고 코드를 고친 뒤 새 이름으로 다시 패키징한다. ZIP 생성 후 파일을 고쳤다면 ZIP도 다시 만들어야 한다.

호스트 개발 시험은 `python3 app/portable.py --host-node /absolute/node check`로 실행할 수 있지만 Windows 네이티브 검증을 대신하지 않는다. 원본 파일을 바꾼 뒤 check의 해시 검증을 통과하려면 repack으로 새 manifest를 먼저 만들어야 한다.

repack은 diagnostics, workspace, .git, __pycache__를 제외한다. 자료를 다른 폴더에 임의로 추가했다면 재배포 전에 반드시 직접 내용물을 검토한다. SHA-256은 무결성 대조용이며 발행자 서명은 아니다.

각 구성 요소의 LICENSE·NOTICE·THIRD_PARTY를 유지한다. 패키지 내부의 실제 문서·인덱스는 가상 예제뿐이다.
