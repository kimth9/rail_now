# 레일블루(rail.blue) 연동 가이드

`japanese_style_timetable` 프로젝트(`api/server.ts`, `src/components/TrainModal.tsx`)에서 실제로 쓰고 있던 레일블루 연동 코드를 분석해 정리한 문서. 공식 API가 아니라 레일블루 웹사이트가 자체 페이지 렌더링에 쓰는 비공개 JSON 엔드포인트를 그대로 호출하는 방식(비공식 스크레이핑에 가까움)이므로, 이식 시 이 점을 감안해야 한다.

## 1. 용도

TAGO(공공데이터포털) 열차 시각표 API는 출발역→도착역 구간 조회만 제공하고, 해당 열차의 **전체 경유역 목록(정차역·통과역, 각 역의 도착/출발 시각)**은 주지 않는다. 레일블루는 이 정보를 보완하는 용도로만 쓰였다:

- 열차 리스트를 받은 뒤 백그라운드로 각 열차의 최종 종착역을 알아내 "OO행"으로 표시
- 검색한 출발역이 그 열차의 진짜 시발역인지 판별해 "당역 출발" 마크(●) 표시
- 사용자가 열차를 클릭했을 때 뜨는 모달에 전체 정차역 타임라인 표시
- 모달 하단에 레일블루 원본 페이지로 바로가기 링크 제공

## 2. 엔드포인트

### 2.1 JSON 데이터 API (서버 프록시로 호출)

```
GET https://rail.blue/railroad/logis/getscheduleinfo.aspx?u=1&train={열차번호}&date={YYYYMMDD}&json=1&version=20180415
```

- 인증 키 불필요 (레일블루 자체 웹페이지가 내부적으로 호출하는 엔드포인트를 그대로 사용)
- `version=20180415` 등 쿼리 파라미터는 고정값으로 사용 — 실제 버전 확인 없이 프론트엔드 소스에서 하드코딩된 값을 그대로 가져다 씀
- 응답이 `Content-Type: text` 등으로 내려오는 경우가 있어 `responseType: 'text'`로 받은 뒤 직접 `JSON.parse` 하는 방어 코드가 필요했음 (BOM·공백 등 섞여 있을 수 있어 `.trim()` 후 파싱)

**요청 예시 (axios, 서버 사이드에서 호출):**

```ts
const targetUrl = `https://rail.blue/railroad/logis/getscheduleinfo.aspx?u=1&train=${encodeURIComponent(trainNo)}&date=${encodeURIComponent(date)}&json=1&version=20180415`;

const response = await axios.get(targetUrl, {
  timeout: 10000,
  headers: {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  },
  responseType: 'text',
});
```

- `User-Agent`를 일반 브라우저처럼 위장해서 보냄 — 기본 axios UA로는 차단되거나 다른 응답이 올 가능성을 고려한 것으로 보임
- `timeout: 10000`(10초)으로 응답 지연 시 빠르게 실패 처리

### 2.2 사람이 보는 원본 페이지 (딥링크용)

```
https://rail.blue/railroad/logis/scheduleinfo.aspx?date={YYYYMMDD}&train={열차번호}#!
```

"레일블루 바로가기" 버튼의 `href`로만 쓰며, 서버에서 호출하지 않고 프론트엔드에서 `target="_blank"`로 새 탭에 여는 용도.

## 3. 요청 파라미터 규칙

| 파라미터 | 형식 | 비고 |
|---|---|---|
| `train` | 열차번호 문자열 | JSON API 호출 시엔 원본 열차번호(숫자 문자열)를 그대로 `encodeURIComponent` |
| `date` | `YYYYMMDD` | 8자리 숫자 |

단, **딥링크용 열차번호**는 별도 포맷팅이 필요하다 (레일블루 웹페이지가 3~4자리 0-패딩된 번호를 기대함):

```ts
const formatTrainNo = (trainNo: string) => {
  const val = parseInt(trainNo.replace(/[^0-9]/g, ''), 10);
  if (isNaN(val)) return trainNo;
  const s = String(val);
  return s.length <= 3 ? s.padStart(3, '0') : s.padStart(4, '0');
};
```

- 숫자 외 문자 제거 후 정수 변환
- 3자리 이하면 3자리로, 4자리 이상이면 4자리로 0-패딩 (예: `7` → `007`, `1234` → `1234`)
- JSON API 호출(`getscheduleinfo.aspx`)에는 이 포맷팅을 적용하지 않고 원본 번호를 그대로 사용했음 — 두 엔드포인트가 기대하는 번호 형식이 다를 수 있으니 이식 시 각각 확인 필요

## 4. 응답 구조

정확한 전체 스키마는 알 수 없고(비공식 API), 실제 사용한 필드만 파악:

```jsonc
{
  "s": [
    {
      "stop": "stop" | "skip" | ...,   // 정차 여부. "skip"이면 통과역 → 필터링 대상
      "s": { "d": "역이름 (역 포함 가능)", "i": "..." },  // d 우선, 없으면 i
      "a": "HH:MM:SS" | null,  // 도착 시각 (없으면 시발역)
      "b": "HH:MM:SS" | null   // 출발 시각 (없으면 종착역)
    },
    ...
  ]
}
```

**파싱/정규화 로직:**

```ts
if (!data.s || !Array.isArray(data.s)) {
  // 상세 경로 정보 없음 → 404 처리
}

const stops = data.s
  .filter((stop: any) => stop.stop !== 'skip')          // 통과역 제외, 정차역만 남김
  .map((stop: any) => {
    const rawStation = stop.s.d || stop.s.i || "";
    const normalizedStation = rawStation.replace(/역$/, '').trim();  // "서울역" -> "서울"

    return {
      station: normalizedStation,
      arrTime: stop.a ? stop.a.substring(0, 5) : "--:--",  // "HH:MM:SS" -> "HH:MM"
      depTime: stop.b ? stop.b.substring(0, 5) : "--:--",
      stopType: stop.stop,
    };
  });
```

- `stop === 'skip'`인 항목(통과역)은 제거하고 실제 정차역만 남김
- 역명은 끝의 "역" 글자를 제거해 프로젝트 내부 역명 표기(`STATION_MAPPING` 등)와 맞춤
- 시각은 앞 5자리만 잘라 `HH:MM` 포맷으로 통일
- 첫 정차역(`stops[0]`)이 사실상 시발역, 마지막(`stops[stops.length-1]`)이 종착역이라는 전제로 프론트엔드 로직이 짜여 있음

## 5. 자체 백엔드 프록시 설계 (Express 예시)

레일블루를 브라우저에서 직접 호출하지 않고 자체 백엔드를 거치게 한 이유: CORS 우회 + 요청 검증 + Rate limit + User-Agent 통일.

```ts
app.get('/api/stops', async (req, res) => {
  const { trainNo, date } = req.query;

  // 열차 번호: 1~6자리 숫자만 허용 (인젝션 방지 목적의 화이트리스트 검증)
  if (typeof trainNo !== 'string' || !/^\d{1,6}$/.test(trainNo)) {
    return res.status(400).json({ error: '유효하지 않은 열차 번호입니다.' });
  }

  if (!isValidDate(date)) {  // YYYYMMDD 형식 검증
    return res.status(400).json({ error: '날짜 형식이 올바르지 않습니다. (YYYYMMDD)' });
  }

  const targetUrl = `https://rail.blue/railroad/logis/getscheduleinfo.aspx?u=1&train=${encodeURIComponent(trainNo)}&date=${encodeURIComponent(date)}&json=1&version=20180415`;

  try {
    const response = await axios.get(targetUrl, {
      timeout: 10000,
      headers: { 'User-Agent': '...(위 참고)...' },
      responseType: 'text',
    });

    let data = response.data;
    if (typeof data === 'string') {
      try {
        data = JSON.parse(data.trim());
      } catch (e) {
        console.error('JSON Parsing failed for rail.blue response');
        return res.status(500).json({ error: '데이터 형식이 올바르지 않습니다.' });
      }
    }

    if (!data.s || !Array.isArray(data.s)) {
      return res.status(404).json({ error: '상세 경로 정보를 찾을 수 없습니다.' });
    }

    const stops = /* 위 4절의 필터·매핑 로직 */;

    res.json(stops);
  } catch (error: any) {
    console.error('RailBlue API Error:', error.message);
    res.status(500).json({ error: '정차역 정보를 가져오는데 실패했습니다.' });
  }
});
```

**Rate limit** (`express-rate-limit`, 배경 배치 조회를 허용하기 위해 다른 엔드포인트보다 여유 있게 설정):

```ts
const stopsLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15분
  max: 500,                  // 15분당 500건 — 열차 리스트를 한꺼번에 조회하는 배치 요청 고려
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: '요청이 너무 많습니다. 15분 후 다시 시도하세요.' },
});
app.use('/api/stops', stopsLimiter);
```

이 500이라는 숫자는 레일블루 측 실제 제한이 아니라 **자체 서버가 자체 사용자에게 거는 제한**이다. 레일블루 원 서버의 실제 호출 한도·차단 정책은 코드에서 확인 불가 — 알려진 바 없음.

## 6. 프론트엔드 사용 패턴

### 6.1 배치(청크) 조회 — 목록 전체의 종착지·당역출발 여부 채우기

시간표 검색 직후, 화면엔 TAGO 데이터로 먼저 그리고 나서 레일블루로 종착역 정보를 백그라운드로 보충한다 (한 번에 다 쏘지 않고 5건씩 나눠서, 요청 사이 100ms 대기 — 과도한 동시 요청으로 레일블루 서버에 부담 주지 않기 위한 자체 스로틀링으로 보임):

```ts
const chunkSize = 5;
for (let i = 0; i < trainsToUpdate.length; i += chunkSize) {
  const chunk = trainsToUpdate.slice(i, i + chunkSize);

  await Promise.all(chunk.map(async (train) => {
    try {
      const stops = await apiClient.fetchTrainStops(train.trainNo, date);
      if (stops && stops.length > 0) {
        const finalStop = stops[stops.length - 1];
        const newDest = `${finalStop.station}행`;
        const isOrigin = normalizeName(stops[0].station) === normalizedDepStation;
        // ...setTrains로 개별 열차 갱신...
      }
    } catch (e) {
      console.error(`Background update failed for train #${train.trainNo}:`, e);
      // 개별 실패가 전체 루프를 막지 않도록 catch로 격리
    }
  }));

  if (i + chunkSize < trainsToUpdate.length) {
    await new Promise(res => setTimeout(res, 100));
  }
}
```

### 6.2 단건 조회 — 열차 클릭 시 상세 모달

```ts
const handleTrainClick = async (train: Train) => {
  setSelectedTrain(train);
  setLoadingStops(true);
  setSelectedTrainStops([]);
  try {
    const stops = await apiClient.fetchTrainStops(train.trainNo, targetDate);
    setSelectedTrainStops(stops);
    const lastStop = stops[stops.length - 1];
    if (lastStop) {
      setSelectedTrain(prev => prev ? { ...prev, destination: `${lastStop.station}행` } : null);
    }
  } catch (error) {
    console.error(error);
  } finally {
    setLoadingStops(false);
  }
};
```

### 6.3 프론트엔드 API 클라이언트 래퍼

```ts
async fetchTrainStops(trainNo: string, date: string): Promise<TrainStop[]> {
  const res = await fetch(`/api/stops?trainNo=${trainNo}&date=${date}`);
  if (!res.ok) throw new Error('정차역 정보 조회 실패');
  return res.json();
}
```

### 6.4 타입 정의

```ts
export interface TrainStop {
  station: string;
  arrTime: string; // HH:mm
  depTime: string; // HH:mm
  stopType?: string;
}
```

### 6.5 딥링크 버튼 (레일블루 원본 페이지로)

```tsx
<a
  href={`https://rail.blue/railroad/logis/scheduleinfo.aspx?date=${targetDate}&train=${formatTrainNo(train.trainNo)}#!`}
  target="_blank"
  rel="noopener noreferrer"
>
  레일블루 바로가기
</a>
```

## 7. 이식 시 유의사항

- **비공식 엔드포인트**: 레일블루가 공식 공개 API로 제공하는 것이 아니라, 자사 웹페이지가 내부적으로 쓰는 JSON 엔드포인트를 그대로 호출하는 구조. 언제든 URL 구조나 응답 스키마가 예고 없이 바뀔 수 있음 — 실제로 겪은 장애 이력은 이 코드베이스 안에서는 없었지만, 방어 코드(JSON 파싱 실패·`data.s` 부재 처리)가 이미 이런 상황을 가정하고 들어가 있음.
- **직접 프론트엔드에서 호출하지 말 것**: CORS 문제뿐 아니라, 브라우저에서 직접 호출하면 User-Agent 위장이 의미가 없어지고 요청 패턴이 그대로 노출됨. 반드시 자체 백엔드를 프록시로 두고 입력 검증(열차번호 정규식, 날짜 형식)을 거칠 것.
- **속도 제한은 자체적으로 설계**해야 함 — 레일블루 쪽 실제 한도는 알려진 바 없으므로, 이 프로젝트처럼 청크+딜레이로 스스로 완만하게 요청하는 편이 안전.
- **역명 정규화**(`역$` 제거)와 **시각 포맷**(`substring(0,5)`)은 레일블루 응답 특성에 맞춘 것이므로, 새 프로젝트의 역명 표기 규칙에 맞게 재조정 필요.
- **트래픽/이용약관**: 이 문서는 코드 분석 결과이며 레일블루 측 이용약관·이용 허가 여부는 확인하지 않았음. 상업적/대규모 트래픽으로 이식하기 전에 별도 확인 권장.
