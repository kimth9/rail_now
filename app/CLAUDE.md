# japanese_style_timetable — Claude 작업 가이드

> **2026-08-28, kr_rail로 흡수통합됨**(2026-08-30 프로젝트 자체가 `rail_now`로 개칭) — 독립
> 프로젝트였던 `japanese_style_timetable`을 자산으로 `rail_now/app/`에 코드 전체(node_modules·
> dist·.git·logs·.env 제외) 그대로 옮겨왔다. 팀 공통 규칙과 rail_now 자체 CLAUDE.md는 상위
> 폴더에서 자동 상속된다. 재사용 가치가 있는 자산: TAGO API 역 매핑(`data/tago_station_mapping.csv`,
> 265개 역), 열차 종별 폴백 스타일, 심야 시각 보정(`getAdjustedHour`). **주의**:
> `src/components/TrainModal.tsx`가 정차역 상세를 rail.blue 개인 사이트 내부 API로 가져오는
> 구조 — 실제로 다시 쓰기 전에 공식 소스(rail_now의 `output/kr_rail_timetable.sqlite`)로
> 교체해야 한다. 원본 프로젝트 폴더는 아직 남아있음(정리 여부는 별도 결정).

## 1. 목표

일본식 시각표(Stem-and-Leaf) 감성으로 한국 철도(TAGO 공공데이터) 시각표를 보여주는 모바일 웹앱.

## 2. 폴더 구조·핵심 모듈

- `src/App.tsx` — 최상위 상태(검색/시각표 뷰 전환, 날짜·역 입력, 선택 열차)
- `src/services/apiClient.ts` — 백엔드 `/api` 호출 클라이언트
- `src/shared/constants.ts` / `types.ts` — 역 매핑(`STATION_MAPPING`), 열차 종별 맵, 공용 타입
- `src/station_rank.json` — 역 순위/매핑 데이터, `api/server.ts`에서 사용
- `api/server.ts` — Express 백엔드. TAGO API 프록시, CORS/헬멧/rate-limit 처리. `dotenv` 미사용 — `process.env` 직접 참조
- `scripts/` — 일회성 데이터 수집 스크립트 (유지보수 대상 아님)

## 3. 실행·테스트 명령

```bash
npm install
npm run dev            # 프론트+백엔드 동시 실행
npm run build           # 프로덕션 빌드
npm run dev:frontend    # vite만
npm run dev:backend     # Express만 (tsx api/server.ts)
```

테스트 스위트 없음 (todo.md 참조).

## 4. 도메인 핵심 지식

- 열차 종별(KTX/KTX-산천/SRT/ITX-마음/ITX-청춘/무궁화)마다 고유 테두리 스타일이 있고, 행선지 4글자 이상은 "3글자.." 형태로 축약한다(`TrainBox`).
- 시간 표시는 0~3시를 24~27시로 변환하는 `getAdjustedHour` 로직을 쓴다(`App.tsx`) — 심야 열차를 같은 날 시각표에 이어 붙이기 위함.
- **`.env`는 프로젝트 폴더(OneDrive 동기화 대상) 밖 `%LOCALAPPDATA%\rail_now\.env`에 둔다**(2026-08-30, 과거 zip 압축 시 평문 유출 이력 때문에 이전). `api/server.ts`는 `MOLIT_TAGO_KEY`(1613000 열차시간표), `scripts/fetch_station_data.py`는 `KORAIL_KEY`(B551457 열차운행정보)를 읽는다. `package.json`의 `dev:backend`/`start`/`serve`가 `--env-file=%LOCALAPPDATA%\rail_now\.env`로 그 경로를 지정한다.
- vite dev 서버는 `/api` 요청을 `localhost:3000`(Express)으로 프록시한다(`vite.config.ts`).

## 5. (해당 시) 이 프로젝트만의 예외·추가 규칙

- **git 사용(2026-07-06 재도입)** — 과거 Azure 배포 중단과 함께 git을 해제했던 예외는 사용자 명시 요청 + 팀장 지시서(order_git.md, 2026-07-06)로 종료됨. 로컬 git으로 버전관리하며, 원격(GitHub 등) 추가는 별도 결정 전까지 금지
- 산출물은 `dist/`(output의 공인 별칭), 실험·일회성 스크립트는 `scripts/`, 로그는 `logs/`
- 루트 파일 10개 이내 유지 원칙에서 vite 설정 파일군은 표준 파일로 간주(파일 수에 영향 없음)
- RAW/ 문서(PDF·DOCX·PPTX·HWP·HWPX) 변환 판단 시 구체 기준: 크거나(수 MB·수십 페이지↑) 반복 참조할 문서는 변환(출력은 반드시 `-o docs/` 지정, 결과 위치는 stdout JSON의 `output_path`로 확인), 소형 1회성·스캔 PDF는 직접 읽기
- 목록·번호 표기 시 원문자 유니코드(①②③, ⒶⒷⒸ 등)를 쓰지 않고 괄호 표기(`(1)`, `(2)`, `(A)`, `(B)`)를 사용한다 — VS Code 폰트가 원문자를 제대로 렌더링하지 못함(전역 규칙, `~/.claude/CLAUDE.md`). 팀 표준(`_TEMPLATE/CLAUDE.md` §5)은 공통 규칙의 프로젝트별 재기술을 금지하지만, 실제 출력에 원문자가 계속 노출되는 문제가 시급하여 사용자가 이 프로젝트에 한해 명시적 재기재를 예외 승인했다 (2026-07-15).

## 6. 참고 문서

- `../프로젝트_표준_가이드.md` — 팀 폴더 표준 (git 예외는 2026-07-06 종료, 위 §5 참조)
- `docs/` — 참고 이미지
