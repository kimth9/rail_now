# japanese_style_timetable — 일본식 감성 결합 한국 철도 시각표 웹앱

> 상태: 활성(로컬 실행 전용, 배포 없음) · 스택: TypeScript/React 18 + Vite + Express (Node ≥ 22) · 최종 검증: 2026-07-15

일본 철도 시각표(Stem-and-Leaf 스타일)의 가독성과 한국 철도 시스템의 데이터를 결합하여, 사용자가 출발/도착역 간의 여정을 한눈에 파악할 수 있는 모바일 최적화 웹앱.

## 1. 빠른 시작

> `node_modules/`는 OneDrive 동기화 부담(3차 표준화 지시, order3.md P1)으로 삭제되어 있다. 아래 `npm install`이 최초 실행 시 반드시 필요하다.

```bash
npm install
npm run dev      # 프론트엔드(vite) + 백엔드(api/server.ts) 동시 실행
npm run build    # 프로덕션 빌드 (dist/ 생성)
```

Windows에서는 `setup.bat`(최초 1회, `npm install`) → `run.bat`(실행)으로도 동일하게 띄울 수 있다. 백엔드 기본 포트는 3000이며, 이미 사용 중이면 `run.bat`이 자동으로 다음 빈 포트(3001, 3002, …)를 찾아 띄운다. 프론트엔드(vite) 기본 포트는 5173이며 충돌 시 vite가 자체적으로 다음 포트로 넘어간다 — 실제 접속 URL은 콘솔에 뜨는 `Local:` 로그를 확인한다.

- 프론트엔드만: `npm run dev:frontend`
- 백엔드만: `npm run dev:backend`
- 배포용 서버 실행: `npm start`

## 2. 프로젝트 구조

표준 골격(`../프로젝트_표준_가이드.md` §2.1) 대비 추가·변형된 폴더만 적는다.

| 폴더/파일 | 내용 |
|---|---|
| `src/` | React 프론트엔드 (vite 기본 구조) |
| `api/server.ts` | Express 백엔드 — 철도 API 프록시 및 CORS/rate-limit 처리 |
| `dist/` | `npm run build` 산출물 (output/의 공인 별칭) |
| `scripts/fetch_station_data.py` | 역별 열차 실적/계획 데이터 수집용 일회성 스크립트 |
| `data/` | `people_2024.csv/xlsx`, `tago_station_mapping.csv` — 참고용 데이터 (코드에서 import되지 않음) |
| `docs/` | 참고 이미지(`1.png`, `20240708_165442.jpg`) |
| `logs/` | 개발 중 발생한 로그 |

## 3. 환경 설정

1. `.env.example`을 `.env`로 복사
2. TAGO(공공데이터포털) 발급 API 키를 입력 — 발급처는 `.env.example` 주석 참조
3. `.env`는 절대 외부에 공유·복사하지 않는다 (버전관리가 없어 OneDrive 동기화 외에는 안전장치가 없음)

## 4. 동작 방식

사용자가 출발역·도착역·날짜를 입력하면(`StationInput`, `DatePicker`) 프론트엔드가 `src/services/apiClient.ts`를 통해 `api/server.ts`(Express)에 요청하고, 서버는 TAGO 공공데이터 API(`DATA_GO_KR_SERVICE_KEY`)를 프록시 호출해 열차 시각표를 조회한다. 응답은 `Center-Hour` 3단 그리드(시각 중앙, 좌측 출발분/우측 도착분)로 렌더링되며, 열차 클릭 시 `TrainModal`이 상세 경로·구간별 소요 시간을 표시한다. 로컬 개발 시 vite dev 서버(`vite.config.ts`)가 `/api` 요청을 `localhost:3000`(Express)으로 프록시한다.

## 5. 알려진 제약·주의

- `scripts/fetch_station_data.py`는 `TRAIN_TIME_API_KEY_3`/`TRAIN_TIME_API_KEY_4` 환경변수를 참조하지만, `.env`에는 `TAGO_API_KEY_1/2/3`만 정의되어 있어 이름이 일치하지 않는다. 이 스크립트를 실행하려면 실제 사용 중인 키 이름에 맞게 코드를 수정하거나 `.env`에 해당 이름의 키를 추가해야 한다.
- `api/server.ts`는 `dotenv`를 로드하지 않고 `process.env`를 직접 참조한다 — 로컬 개발 시에는 별도 방법(예: `dotenv-cli`)으로 `.env`를 주입해야 한다.
- **Azure 배포·GitHub 연결 모두 중단됨(비용 문제, 2026-07)** — 이 프로젝트는 순수 로컬 실행(`npm run dev`) 전용이며 어디에도 배포되어 있지 않다. 재배포가 필요해지면 별도 호스팅(프론트엔드 정적 배포 + 백엔드 서버 호스팅)을 처음부터 다시 구성해야 한다.
- 로컬 git으로만 버전관리(2026-07-06 재도입, 원격 없음) — GitHub 등 원격 저장소 연결은 없으므로 로컬 git 이력 + OneDrive 동기화에만 의존한다.
- 테스트 스위트 없음 — 향후 도입 시 `todo.md` 참조.
