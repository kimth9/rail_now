# 업무진행 상황록 (history)

> 담당자(사람·AI 세션)가 작업을 마칠 때마다 **무엇을 했는지 3~5줄 내외**로 기록하는 시간순 상황록.
> 규칙: 항상 **문서 맨 아래에 추가**(오래된 → 최신), 과거 항목은 수정하지 않는다.
> 권장 구성: 한 일 / 발견한 문제 / 다음에 할 일

---

## 2026-07-05 — Claude (표준화 작업)

- 팀장 발행 `standard_order.md` 지시에 따라 폴더 구조 표준화 진행: `API_Key.env` → `.env` 리네임 + `.env.example` 신설, `scripts/`(fetch_station_data.py) · `data/`(people_2024.*, tago_station_mapping.csv) · `docs/`(이미지 2종) · `logs/`(로그 4종, gitignore 처리) 신설·이동, `project_goal.txt` 내용을 README.md로 승격, CLAUDE.md·todo.md 신설.
- 사전 조사로 standard_order.md의 P0 진단(`API_Key.env`가 git 이력에 커밋됨)이 실제와 다름을 확인 — `git log --all --full-history`로도 커밋 이력이 없어 로테이션은 생략(사용자 승인). 이 프로젝트는 GitHub(origin)에 이미 push된 상태로 로컬 전용이 아님도 확인.
- `.claude/settings.local.json`이 실수로 git에 추적되고 있던 것을 발견해 `git rm --cached` + `.gitignore` 처리.
- 다음 할 일: vitest 테스트 도입, `scripts/fetch_station_data.py`의 환경변수 이름 불일치(TRAIN_TIME_API_KEY_* vs TAGO_API_KEY_*) 정리 — 둘 다 todo.md에 등록.

## 2026-07-05 — Claude (Azure 배포 워크플로 정리)

- 표준화 커밋 push 후 CI 확인 중 Azure 배포 워크플로 2개(azure-deploy.yml, main_krtraintimetable.yml)가 `AADSTS700016`(앱 등록 없음)으로 실패한 것을 발견. 담당자 확인 결과 비용 문제로 Azure 리소스를 최근 직접 삭제한 것으로 확인 — 자격증명 문제가 아니라 의도된 삭제였음.
- 더 이상 성공할 수 없는 Azure 배포 워크플로 2개를 삭제. 현재 CI는 `deploy.yml`(GitHub Pages)만 남아 `dist/`(프론트엔드 정적 빌드)를 배포 중.
- 발견한 문제: `api/server.ts`(Express 백엔드)는 Azure 삭제 이후 어디에도 배포되어 있지 않음 — GitHub Pages는 정적 파일만 서빙하므로 백엔드 호스팅 공백 상태. README·todo.md에 반영.
- 다음에 할 일: 백엔드 배포처 결정 (todo.md 등록).

## 2026-07-05 — Claude (GitHub 연결 해제, 로컬 프로젝트 전환)

- 담당자가 Azure 리소스를 이미 삭제했음을 확인 후, "GitHub도 Azure 배포용으로만 썼다"며 GitHub 연결 자체를 완전히 중단하기로 결정. 마지막 커밋(`d22cad1`)까지 `origin/main`에 push해 GitHub 쪽 이력은 보존한 뒤, `git remote remove origin` → `.git` 폴더 삭제 → `.github/`·`.gitignore` 제거로 순수 로컬 파일 상태로 전환.
- README.md·CLAUDE.md의 git/GitHub/CI 관련 서술을 로컬 전용 상태에 맞게 갱신 (버전관리 없음, 배포 없음 명시).
- 발견한 문제: 이제 버전관리 수단이 전혀 없어 OneDrive 동기화 이력에만 의존 — 실수 삭제·덮어쓰기 복구가 어려움. 팀 표준(버전관리는 git으로만)의 명시적 예외 사례.
- 다음에 할 일: 필요 시 `git init`으로 로컬 버전관리만이라도 재도입할지 검토 (원격 없이 로컬 커밋만 하는 것도 가능).

## 2026-07-05 — Claude (3차 표준화, order3.md 이행)

- 팀장 발행 `order3.md`(1·2차 지시서 회수 후 잔여 항목만 담은 3차 지시서) 이행: P1 지시에 따라 `node_modules/`(104MB) 삭제, README.md 빠른 시작에 재설치 필요 안내 문구 추가. 완료했던 `todo.md`의 관련 항목 삭제.
- P2(루트 파일 수)는 팀장이 vite 필수 설정군을 감안해 현 수준(13개) 그대로 허용한다고 명시해 별도 조치 없음.
- 공통 정책 재확인: 캐시 디렉터리(`__pycache__/`, `.pytest_cache/` 등) 조사 결과 이 프로젝트엔 해당 없음. 시크릿 로테이션은 이전 라운드와 동일하게 사용자 판단으로 생략(git/GitHub 이력에 노출된 적 없음을 재확인).
- `order3.md`는 지시서 원문에 따라 팀장 회수 시까지 루트에 그대로 유지(삭제·이동하지 않음).
- 다음에 할 일: 다음 개발 세션 시작 시 `npm install`로 `node_modules/` 재생성 필요.

## 2026-07-05 — 팀장 (CLAUDE.md 규칙 갱신)

- CLAUDE.md §5에 파이썬 캐시 자동 삭제 규칙(해당 시) 추가, §6의 죽은 `standard_order.md` 참조(실존 파일 없음) 정리.
- `__pycache__`/`.pytest_cache` 실물 조사 결과 해당 없음(node_modules/.git 제외).

## 2026-07-05 — 팀장 (RAW 문서 변환 규칙 추가)

- CLAUDE.md §5에 RAW/ 문서(PDF·DOCX·PPTX·HWP·HWPX) 변환 판단 규칙 추가 — 크거나 반복 참조할 문서는 `../converter_tool/docs_to_markdown/AGENTS.md`로 변환, 소형·스캔본은 직접 읽기.

## 2026-07-05 — 팀장 (커밋 규약 반영)

- CLAUDE.md §5에 git 커밋 메시지 팀 규약(`타입: 한 줄 요약` + history.md 참조, 세션당 최소 1커밋, 상세는 프로젝트_표준_가이드.md §5.4) 추가 — 이 프로젝트는 git 미사용 상태라 재도입 시부터 적용.

## 2026-07-06 — Claude (참조 정리·장기 계획 이관)

- todo.md 안내문의 `future_plan_Fable.md` 참조를 실제 파일명 규칙에 맞춰 `future_plan.md`로 수정 (실제 해당 파일명 파일은 없었음).
- todo.md `대기` 항목 중 "배포가 다시 필요해지면 프론트엔드·백엔드 호스팅을 처음부터 재구성"을 장기 구상으로 판단해 신규 `future_plan.md`(`## 구상`)로 이관하고 todo.md에서 제거. 나머지 대기 항목(버전관리 재도입 검토, vitest 도입, 환경변수 이름 정리)은 단기 항목으로 판단해 유지.

## 2026-07-06 — Claude (git 도입, order_git.md 이행)

- 팀장 지시서 order_git.md 이행 — 팀 표준 .gitignore(v1.0) 신설 후 `git init`, 초기 커밋 `0305d19` 생성(32개 파일). CLAUDE.md §5의 git 미사용 예외 조항을 재도입 반영으로 갱신.
- `.env`는 미추적 확인(`git ls-files` 결과 없음, `.env.example`만 커밋), node_modules/·dist/ 제외 확인. 원격 추가 없음(로컬 전용).

## 2026-07-12 — Claude (order_4 이행, 분석일지 체계 소급 적용)

- `docs/analysis/` 폴더 신설 + `_TEMPLATE/docs/analysis/_양식.md` 복사.
- 기존 문서 전수 확인(`docs/`엔 참고 이미지 2종만 존재, 루트·`output/`엔 md 없음, `output/`은 애초에 없고 `dist/`만 사용) 결과 **이관 대상 분석·기록성 문서 없음** — P1의 이관 항목은 해당 없음으로 종결.
- P2(참조 갱신)·P3(output 소급 개명)도 이관이 없어 조치 불필요.
- order_4.md는 완료 확인 후 §12.2 수명 규약에 따라 자체 삭제.

## 2026-07-15 — Claude(문서 표준화 세션)

- 프로젝트 표준 가이드(§4) 기준으로 README/todo/history/future_plan 형식 점검·정리.
- README 상단 상태줄·§5의 "버전관리 없음(git 미사용)" 서술이 2026-07-06 git 재도입(CLAUDE.md·history.md 확인) 이후로 사실과 어긋나 있어 현재 상태(로컬 git, 원격 없음)에 맞게 수정하고 최종 검증 날짜를 갱신; todo.md의 완료 표시(`[x]`) 항목(버전관리 재도입 검토, 2026-07-06 이미 완료 기록됨)을 제거. history.md·future_plan.md는 형식이 이미 표준에 부합해 손대지 않음.

## 2026-07-31 — Claude/ponytail (코드 압축)

- 베이스라인 `14dff07`(clean) 확인 후 진행. `node_modules` 미설치 상태라 `npm run build`(tsc/vite)가 원천 실행 불가함을 먼저 기록 — 사전 결함(2026-07-05 의도적 삭제)이라 설치는 시도하지 않고, 편집 파일에 대해 참조 전수 검색(grep 0건 확인) + 괄호·중괄호 균형 검사로 구문 스모크를 대체.
- 전수 grep으로 무참조 확인 후 삭제: `src/api.ts`(파일 자체가 "레거시 코드, 실제 호출은 api/server.ts 담당"이라 명시했고 참조 0건이던 구 Azure 프록시 클라이언트, STATION_MAPPING 중복 포함 151줄), `src/utils/search.ts`(getChoseong/searchStations, 어디서도 import되지 않는 프론트엔드 고아 모듈 43줄 — StationInput은 이미 백엔드 apiClient.searchStations를 씀). CLAUDE.md §2의 관련 서술(station_rank.json 공유처)도 갱신.
- `TrainBox.tsx`의 항등 래퍼 `formatDestination`을 호출부에 인라인, `TrainBox.tsx`·`TrainModal.tsx`의 미사용 `import React`(jsx:"react-jsx"라 React 네임스페이스 미사용 시 불필요) 제거.
- 순변화: 5개 파일, +2/-200줄. 최상위 진입점(main.tsx, App.tsx, api/server.ts)은 미삭제.
