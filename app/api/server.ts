import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import rateLimit from 'express-rate-limit';
import axios from 'axios';
import path from 'path';
import { fileURLToPath } from 'url';
import { STATION_MAPPING, ALL_STATIONS, TRAIN_TYPE_MAP } from '../src/shared/constants.ts';
import { Train, TrainStop } from '../src/shared/types.ts';
import stationRankData from '../src/station_rank.json' assert { type: 'json' };

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const port = process.env.PORT || 3000;

// 보안 헤더 설정
app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      scriptSrc: ["'self'", "'unsafe-inline'"],
      styleSrc: ["'self'", "'unsafe-inline'"],
      imgSrc: ["'self'", "data:"],
      connectSrc: ["'self'"],
    }
  }
}));

// CORS: 허용 오리진 환경변수로 제어
const allowedOrigins = process.env.ALLOWED_ORIGINS
  ? process.env.ALLOWED_ORIGINS.split(',').map(o => o.trim())
  : ['http://localhost:5173', 'http://localhost:3000', 'https://krtraintimetable.azurewebsites.net'];

app.use(cors({
  origin: (origin, callback) => {
    // 서버 사이드 요청(origin 없음)은 허용, 등록된 오리진만 허용
    if (!origin || allowedOrigins.includes(origin)) {
      callback(null, true);
    } else {
      callback(new Error('CORS 정책에 의해 차단된 요청입니다.'));
    }
  },
  methods: ['GET'],
  allowedHeaders: ['Content-Type'],
}));

// Rate Limiting: 엔드포인트별 적용
const timetableLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15분
  max: 60,                   // 시간표 조회: 15분당 60건
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: '요청이 너무 많습니다. 15분 후 다시 시도하세요.' },
});

const stopsLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15분
  max: 500,                  // 정차역 조회: 15분당 500건 (백그라운드 배치 요청 허용)
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: '요청이 너무 많습니다. 15분 후 다시 시도하세요.' },
});

const stationsLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15분
  max: 200,                  // 역 검색: 15분당 200건
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: '요청이 너무 많습니다. 15분 후 다시 시도하세요.' },
});

app.use(express.json());
app.use('/api/timetable', timetableLimiter);
app.use('/api/stops', stopsLimiter);
app.use('/api/stations', stationsLimiter);

// 배포 확인을 위한 헬스체크 API (내부 정보 노출 최소화)
app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
  });
});

const SERVICE_KEYS = process.env.DATA_GO_KR_SERVICE_KEY
  ? [process.env.DATA_GO_KR_SERVICE_KEY]
  : [];

if (SERVICE_KEYS.length === 0) {
  console.error('[CRITICAL] DATA_GO_KR_SERVICE_KEY 환경변수가 설정되지 않았습니다.');
}

const stationRank: Record<string, number> = stationRankData;

// 초성 추출 함수
function getChoseong(str: string) {
  const CHOSEONG = [
    'ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'
  ];
  let result = '';
  for (let i = 0; i < str.length; i++) {
    const code = str.charCodeAt(i) - 44032;
    if (code > -1 && code < 11172) {
      result += CHOSEONG[Math.floor(code / 588)];
    } else {
      result += str.charAt(i);
    }
  }
  return result;
}

// 날짜 형식 검증 (YYYYMMDD)
function isValidDate(date: unknown): date is string {
  if (typeof date !== 'string') return false;
  if (!/^\d{8}$/.test(date)) return false;
  const y = parseInt(date.substring(0, 4));
  const m = parseInt(date.substring(4, 6));
  const d = parseInt(date.substring(6, 8));
  return y >= 2020 && y <= 2099 && m >= 1 && m <= 12 && d >= 1 && d <= 31;
}

// 1. 역 검색 API
app.get('/api/stations', (req, res) => {
  const query = req.query.q as string;
  if (!query) return res.json([]);

  // 입력 길이 제한 및 허용 문자 검증 (한글, 영문, 초성, 괄호만 허용)
  if (query.length > 30 || !/^[가-힣ㄱ-ㅎa-zA-Z0-9\s()]+$/.test(query)) {
    return res.status(400).json({ error: '유효하지 않은 검색어입니다.' });
  }

  const isChoseong = /^[ㄱ-ㅎ]+$/.test(query);
  const filtered = ALL_STATIONS.filter(station => {
    if (isChoseong) {
      return getChoseong(station).includes(query);
    }
    return station.includes(query);
  });

  const sorted = filtered.sort((a, b) => {
    const rankA = stationRank[a] || 0;
    const rankB = stationRank[b] || 0;
    return rankB - rankA;
  });

  res.json(sorted);
});

// 차종 매핑 함수 (기존 로직 복구)
function mapTrainType(id: string, name: string) {
  if (id) {
    switch (id) {
      case "00": return "KTX";
      case "01": return "새마을";
      case "02": return "무궁화";
      case "03": return "통근";
      case "04": return "누리로";
      case "06": return "AREX직통";
      case "07": return "A산천";
      case "08": return "I새마을";
      case "09": return "I청춘";
      case "10": return "B산천";
      case "16": return "이음";
      case "17": return "SRT";
      case "18": return "마음";
      case "19": return "청룡";
    }
  }
  if (name.includes("KTX-산천(A-type)")) return "A산천";
  if (name.includes("KTX-산천(B-type)")) return "B산천";
  if (name.includes("KTX-산천")) return "산천";
  if (name.includes("새마을호")) return "새마을"; // '새마을호'를 '새마을'로 변경
  if (name.includes("무궁화호")) return "무궁화"; // '무궁화호'를 '무궁화'로 변경
  if (name.includes("ITX-새마을")) return "I새마을";
  if (name.includes("ITX-청춘")) return "I청춘";
  if (name.includes("ITX-마음")) return "마음";
  if (name.includes("KTX-이음")) return "이음";
  if (name.includes("KTX-청룡")) return "청룡";
  return name;
}

// 2. 열차 시간표 API
app.get('/api/timetable', async (req, res) => {
  const { dep, arr, date } = req.query;

  if (!isValidDate(date)) {
    return res.status(400).json({ error: '날짜 형식이 올바르지 않습니다. (YYYYMMDD)' });
  }

  const depNodeId = STATION_MAPPING[dep as string];
  const arrNodeId = STATION_MAPPING[arr as string];

  if (!depNodeId || !arrNodeId) {
    return res.status(400).json({ error: '유효하지 않은 역 이름입니다.' });
  }

  if (SERVICE_KEYS.length === 0) {
    return res.status(503).json({ error: 'API 키가 설정되지 않았습니다.' });
  }

  try {
    const targetUrl = `https://apis.data.go.kr/1613000/TrainInfo/GetStrtpntAlocFndTrainInfo`;
    const response = await axios.get(targetUrl, {
      timeout: 10000,
      params: {
        serviceKey: decodeURIComponent(SERVICE_KEYS[0]),
        _type: 'json',
        depPlaceId: depNodeId,
        arrPlaceId: arrNodeId,
        depPlandTime: date,
        numOfRows: 1000,
        pageNo: 1
      }
    });

    const data = response.data;
    if (data.response?.header?.resultCode !== "00") {
      throw new Error(data.response?.header?.resultMsg || "API 호출 실패");
    }

    const items = data.response.body.items.item;
    const rawItems = Array.isArray(items) ? items : items ? [items] : [];
    
    // 열차 번호(trainno)와 출발 시각(HHmm) 기준 중복 제거 강화
    // 0시 이후 중복 표시 문제를 해결하기 위해 날짜와 시:분까지만 엄격하게 체크
    const uniqueMap = new Map();
    rawItems.forEach((item: any) => {
      const trainNo = String(item.trainno).trim();
      const depTimeStr = String(item.depplandtime);
      const datePart = depTimeStr.substring(0, 8);
      const timePart = depTimeStr.substring(8, 12); // HHmm
      
      // 요청한 날짜(date)와 실제 데이터의 날짜가 일치하는 것만 우선적으로 처리하거나,
      // 동일 열차번호+동일시각은 하나만 남김
      const key = `${trainNo}-${timePart}`;
      
      if (!uniqueMap.has(key)) {
        uniqueMap.set(key, item);
      } else {
        // 이미 존재하는 경우, 요청한 날짜와 더 정확히 일치하는 데이터를 우선시할 수 있음
        if (datePart === date) {
          uniqueMap.set(key, item);
        }
      }
    });

    const uniqueItems = Array.from(uniqueMap.values());

    const trains: Train[] = uniqueItems.map((item: any, index: number) => {
      const trainType = mapTrainType(item.vehiclekndid, item.traingradename);
      const depTimeStr = String(item.depplandtime);
      const arrTimeStr = String(item.arrplandtime);
      
      const finalDest = item.endplacename ? `${item.endplacename}행` : `${item.arrplacename}행`;
      
      return {
        id: `${item.trainno}-${index}`,
        type: trainType,
        trainNo: String(item.trainno),
        destination: finalDest,
        depTime: `${depTimeStr.substring(8, 10)}:${depTimeStr.substring(10, 12)}`,
        arrTime: `${arrTimeStr.substring(8, 10)}:${arrTimeStr.substring(10, 12)}`,
        originalType: item.traingradename
      };
    });

    // 출발 시각 기준 오름차순 정렬 추가
    trains.sort((a, b) => a.depTime.localeCompare(b.depTime));

    res.json({ trains });
  } catch (error: any) {
    console.error('Tago API Error:', error.message);
    res.status(500).json({ error: '열차 시간표를 가져오는데 실패했습니다.' });
  }
});

// 3. 열차 정차역 상세 API
app.get('/api/stops', async (req, res) => {
  const { trainNo, date } = req.query;

  // 열차 번호: 1~6자리 숫자만 허용
  if (typeof trainNo !== 'string' || !/^\d{1,6}$/.test(trainNo)) {
    return res.status(400).json({ error: '유효하지 않은 열차 번호입니다.' });
  }

  if (!isValidDate(date)) {
    return res.status(400).json({ error: '날짜 형식이 올바르지 않습니다. (YYYYMMDD)' });
  }

  const targetUrl = `https://rail.blue/railroad/logis/getscheduleinfo.aspx?u=1&train=${encodeURIComponent(trainNo)}&date=${encodeURIComponent(date)}&json=1&version=20180415`;

  try {
    const response = await axios.get(targetUrl, {
      timeout: 10000,
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      },
      responseType: 'text'
    });

    let data = response.data;
    if (typeof data === 'string') {
      try {
        // 혹시 모를 BOM이나 불필요한 문자가 포함된 경우 제거 후 파싱
        data = JSON.parse(data.trim());
      } catch (e) {
        console.error('JSON Parsing failed for rail.blue response');
        return res.status(500).json({ error: '데이터 형식이 올바르지 않습니다.' });
      }
    }

    if (!data.s || !Array.isArray(data.s)) {
      return res.status(404).json({ error: '상세 경로 정보를 찾을 수 없습니다.' });
    }

    const stops: TrainStop[] = data.s
      .filter((stop: any) => stop.stop !== 'skip')
      .map((stop: any) => {
        const rawStation = stop.s.d || stop.s.i || "";
        // 역 이름 정규화 (예: "대전 " -> "대전", "서울역" -> "서울")
        const normalizedStation = rawStation.replace(/역$/, '').trim();
        
        return {
          station: normalizedStation,
          arrTime: stop.a ? stop.a.substring(0, 5) : "--:--",
          depTime: stop.b ? stop.b.substring(0, 5) : "--:--",
          stopType: stop.stop
        };
      });

    res.json(stops);
  } catch (error: any) {
    console.error('RailBlue API Error:', error.message);
    res.status(500).json({ error: '정차역 정보를 가져오는데 실패했습니다.' });
  }
});

// 정적 파일 제공 (빌드된 프론트엔드)
// __dirname은 api 폴더 내부이므로 한 단계 상위로 올라가 dist를 찾습니다.
const distPath = path.resolve(__dirname, '..', 'dist');
app.use(express.static(distPath));
app.use('/assets', express.static(path.join(distPath, 'assets')));

app.get('*', (req, res) => {
  if (!req.path.startsWith('/api')) {
    const indexPath = path.join(distPath, 'index.html');
    res.sendFile(indexPath);
  }
});

app.listen(port, () => {
  console.log('=========================================');
  console.log(`Server starting...`);
  console.log(`Port: ${port}`);
  console.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
  console.log(`Static path: ${distPath}`);
  console.log('=========================================');
});
