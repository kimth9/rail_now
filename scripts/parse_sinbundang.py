#!/usr/bin/env python3
"""신분당선(네오트랜스) 시각표 -> 정규화 테이블

RAW에 xlsx가 없다 — 평일은 PDF(`250102_신분당선(평일) 역별 열차시각표.pdf`,
16개 역, 역당 1페이지), 휴일은 PNG(`220528_신분당선 역별 열차시각표_휴일4.png`,
843x9537 세로 스크린샷 16개 역치 이어붙임)만 있다. 평일/휴일 기준일이
2.5년 이상 차이난다(캐비어트로 명시).

**평일(PDF)**: `pdfplumber`로 직접 파싱 — 표 선이 없어 `extract_tables()`는
안 먹히지만, 각 역 페이지가 [신사방면 분] [시] [광교방면 분] 3열 고정
템플릿이라(시 열의 x0가 페이지 전체에서 항상 411~412 부근) 단어 좌표
(x0, top)로 열을 분리하고, 같은 'top'(같은 인쇄 줄)에 있는 시 라벨을
행 앵커로 써서 좌/우 값을 그 시각에 배정한다(단순 텍스트 줄 결합은
두 방향의 분(分) 개수가 달라 시 라벨 토큰과 겹치는 값이 있으면 모호해짐
— 좌표 기반이라야 안전).

**휴일(PNG)**: 이미지라 pdfplumber를 못 쓴다. Claude가 이미지를 8등분해
직접 읽어 `RAW/220528_신분당선_휴일_extract.txt`로 전사해둔 걸 읽는다
(다른 웹크롤링 노선의 raw_extract.txt와 같은 관례).

원본이 다른 웹크롤링 노선과 같은 "역별 발차 시각 목록" 구조이므로 재구성
원리는 `_station_list_reconstruct.link_trips()`와 같지만, 이 노선은 역간
간격이 균일하지 않다(청계산입구~판교 구간만 6~7분, 나머지는 대부분
1~4분, 최소 배차간격도 4분) — 전 구간에 공통 max_hop을 걸면 그 한 구간
때문에 값을 크게 잡아야 하고, 그러면 배차간격(4분)보다 커진 max_hop이
다른(짧은) 구간에서 엉뚱한 열차끼리 잘못 이어붙일 위험이 생긴다. 그래서
공유 `link_trips()`(전 구간 단일 max_hop) 대신 이 파일 안에서만 쓰는
`extend_active()`(한 역씩 구간별로 다른 max_hop을 주며 진행하는 버전,
알고리즘은 동일)를 둔다 — 다른 노선에 영향 없이 이 노선의 특이 구조만 대응.

**정자 단축운행 분기(하행/광교방면 한정)**: 원본에 "54(정자)" 식으로 그
열차의 실제 목적지가 광교가 아니라 정자임을 표시해 둔다. 상행(신사방면)
에는 이 표시가 전혀 없다. 판교~정자 구간은 정상 간격(3~4분)이라 단순히
FIFO로 넘기면 정자행 열차가 마침 정자역 자신의 하행 기록 중 다른(실제로는
무관한) 값과 우연히 max_hop 이내로 걸려 잘못 이어질 위험이 있다 — 그래서
판교까지는 정상 재구성하되, 판교 도달 체인 중 (정자) 표시가 있는 것만
분리해 정자에서 확정 종착시키고(추정 3분 소요), 표시 없는 것만 정자~
광교중앙 구간으로 계속 이어붙인다.

역명 충돌: 강남(2호선)·양재(3호선/일산선 계통)·신사(3호선)·판교(국철·
경강선)·정자·미금(수인분당선)은 실제 환승역이라 이름 그대로 자동 병합.
동천은 대구3호선 동명역과 무관해 merge_key로 분리.
"""
import csv
import os
import re
import sys
from collections import OrderedDict

import pdfplumber

PDF_WD = sys.argv[1] if len(sys.argv) > 1 else "RAW/250102_신분당선(평일) 역별 열차시각표.pdf"
TXT_HD = sys.argv[2] if len(sys.argv) > 2 else "RAW/220528_신분당선_휴일_extract.txt"
OUT = sys.argv[3] if len(sys.argv) > 3 else "tmp/out_sinbundang"

STATION_ORDER = ["신사", "논현", "신논현", "강남", "양재", "양재시민의숲",
                  "청계산입구", "판교", "정자", "미금", "동천", "수지구청",
                  "성복", "상현", "광교중앙", "광교"]

MERGE_KEY = {"동천": "동천(신분당선)"}  # 대구3호선 동명역과 무관

DEFAULT_HOP_MIN = 5
LONG_HOP = {("청계산입구", "판교"): 7, ("판교", "청계산입구"): 7}  # 실측 6~7분 구간, 나머지는 전부 <=4분
EST_JEONGJA_HOP = 3   # 판교->정자 추정(실측 hop 3~4분과 일치)
EST_LAST_HOP = {"신사": 2, "광교": 3}  # 트렁크 끝 다음 진짜 종점까지 추정 hop

HOUR_X0_MIN, HOUR_X0_MAX = 405, 420
TOKEN_RE = re.compile(r"^(\d+)(\(정자\))?")


def hour_to_abs(h):
    return h + 24 if h < 5 else h


def hop_for(a, b):
    return LONG_HOP.get((a, b), DEFAULT_HOP_MIN)


def extend_active(active, mh, bi, times):
    """active의 각 체인 뒤에 이번 역(bi)의 시각들을 max_hop=mh로 이어붙이는
    한 단계. (새 active 목록, 이번 단계에서 매칭 안 돼 끝난 체인 목록)을 반환."""
    new_active, finished = [], []
    ai = 0
    for t, flag in times:
        matched = False
        while ai < len(active):
            last_t = active[ai][-1][1]
            if t - last_t > mh:
                finished.append(active[ai])
                ai += 1
                continue
            if t >= last_t:
                active[ai].append((bi, t, flag))
                new_active.append(active[ai])
                ai += 1
                matched = True
            break
        if not matched:
            new_active.append([(bi, t, flag)])
    finished.extend(active[ai:])
    return new_active, finished


def parse_pdf_wd(path):
    """반환: {역명: {"up": [(분,False),...], "down": [(분,is_정자),...]}}"""
    out = {}
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            title = words[0]["text"]
            hour_words = [w for w in words
                          if HOUR_X0_MIN <= w["x0"] <= HOUR_X0_MAX and re.match(r"^\d{2}$", w["text"])]
            left = [w for w in words if w["x0"] < HOUR_X0_MIN and w["top"] > 110]
            right = [w for w in words if w["x0"] > HOUR_X0_MAX and w["top"] > 110]
            up_times, down_times = [], []
            for hw in hour_words:
                ah = hour_to_abs(int(hw["text"]))
                row_top = hw["top"]
                for w in left:
                    if abs(w["top"] - row_top) < 1.0:
                        m = TOKEN_RE.match(w["text"])
                        if m:
                            up_times.append((ah * 60 + int(m.group(1)), bool(m.group(2))))
                for w in right:
                    if abs(w["top"] - row_top) < 1.0:
                        m = TOKEN_RE.match(w["text"])
                        if m:
                            down_times.append((ah * 60 + int(m.group(1)), bool(m.group(2))))
            up_times.sort()
            down_times.sort()
            out[title] = {"up": up_times, "down": down_times}
    return out


def parse_time_list(text):
    out = []
    text = text.strip()
    if not text or text == "(없음)":
        return out
    for part in text.split(";"):
        part = part.strip()
        if not part:
            continue
        hour_s, _, rest = part.partition(":")
        h = hour_to_abs(int(hour_s))
        for tok in rest.split(","):
            tok = tok.strip()
            m = TOKEN_RE.match(tok)
            if m:
                out.append((h * 60 + int(m.group(1)), bool(m.group(2))))
    out.sort()
    return out


def parse_txt_hd(path):
    out = {}
    cur = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            m = re.match(r"=== (\S+) ===", line)
            if m:
                cur = m.group(1)
                out[cur] = {"up": [], "down": []}
                continue
            m = re.match(r"(UP|DOWN): (.*)$", line)
            if m and cur:
                key = "up" if m.group(1) == "UP" else "down"
                out[cur][key] = parse_time_list(m.group(2))
    return out


DAYTYPES = ["WD", "HD"]
DAYTYPE_LABEL = {"WD": "평일", "HD": "휴일"}


def main():
    wd = parse_pdf_wd(PDF_WD)
    hd = parse_txt_hd(TXT_HD)
    raw = {"WD": wd, "HD": hd}

    stops = OrderedDict()
    for name in STATION_ORDER:
        stops[name] = f"SB{len(stops) + 1:04d}"

    trips, stop_times = [], []
    trip_counter = [0]

    def emit(daykey, direction, chain_names, chain):
        """chain: [(bi, 분, is_정자), ...] (bi는 chain_names 안 인덱스)."""
        if len(chain) < 2:
            return
        trip_counter[0] += 1
        trip_id = f"{direction}#{DAYTYPE_LABEL[daykey]}#{trip_counter[0]}"
        for seq, (bi, t, _flag) in enumerate(chain, start=1):
            stop_times.append({"trip_id": trip_id, "stop_seq": seq,
                                "stop_id": stops[chain_names[bi]], "dep_sec": t * 60})
        trips.append({"trip_id": trip_id, "train_no": trip_id,
                       "line_id": "SINBUNDANG", "line_name": "신분당선",
                       "formation": "전동차", "direction": direction,
                       "service_id": DAYTYPE_LABEL[daykey],
                       "origin": stops[chain_names[chain[0][0]]],
                       "destination": stops[chain_names[chain[-1][0]]], "next_train_no": ""})

    def process_up(daykey):
        """상행(신사방면) — 광교부터 역순 트렁크(마지막 '신사'는 실제 상행
        데이터 없음, 추정 연장용). 정자 인근 분기 없음(원본에 표시가 상행에는
        아예 없음), 청계산입구~판교 구간만 hop_for()로 넓게."""
        names_all = list(reversed(STATION_ORDER))
        idx_nonhyeon = names_all.index("논현")
        blocks = [(n, raw[daykey].get(n, {}).get("up", [])) for n in names_all]

        first_idx = next(i for i, (_, t) in enumerate(blocks) if t)
        active = [[(first_idx, t, f)] for t, f in blocks[first_idx][1]]
        for bi in range(first_idx + 1, idx_nonhyeon + 1):
            if not blocks[bi][1]:
                continue
            mh = hop_for(names_all[bi - 1], names_all[bi])
            active, done = extend_active(active, mh, bi, blocks[bi][1])
            for chain in done:
                emit(daykey, "up", names_all, chain)

        for chain in active:
            if chain[-1][0] == idx_nonhyeon:
                last_t = chain[-1][1]
                chain = chain + [(idx_nonhyeon + 1, last_t + EST_LAST_HOP["신사"], False)]
            emit(daykey, "up", names_all, chain)

    def process_down(daykey):
        """하행(광교방면) — 신사부터 판교까지 이어붙인 뒤, 판교에 도달한 체인
        중 (정자) 표시가 있는 것만 정자에서 확정 종착시키고, 나머지(표시 없는
        것)만 이어서 정자~광교중앙~광교로 계속 진행한다. 판교 이전에 이미
        끊긴 체인(단축·시발 등)은 그대로 종착 처리."""
        names_all = STATION_ORDER  # 신사..광교(마지막 '광교'는 실제 하행 데이터 없음, 추정 연장용)
        blocks = [(n, raw[daykey].get(n, {}).get("down", [])) for n in names_all]
        idx_pangyo = names_all.index("판교")
        idx_jeongja = names_all.index("정자")
        idx_gkjungang = names_all.index("광교중앙")

        first_idx = next(i for i, (_, t) in enumerate(blocks) if t)
        active = [[(first_idx, t, f)] for t, f in blocks[first_idx][1]]
        for bi in range(first_idx + 1, idx_pangyo + 1):
            if not blocks[bi][1]:
                continue
            mh = hop_for(names_all[bi - 1], names_all[bi])
            active, done = extend_active(active, mh, bi, blocks[bi][1])
            for chain in done:
                emit(daykey, "down", names_all, chain)

        continuing = []
        for chain in active:
            if chain[-1][0] == idx_pangyo and chain[-1][2]:  # (정자) 표시 -> 확정 종착
                last_t = chain[-1][1]
                chain = chain + [(idx_jeongja, last_t + EST_JEONGJA_HOP, False)]
                emit(daykey, "down", names_all, chain)
            else:
                continuing.append(chain)
        active = continuing

        for bi in range(idx_pangyo + 1, idx_gkjungang + 1):
            if not blocks[bi][1]:
                continue
            mh = hop_for(names_all[bi - 1], names_all[bi])
            active, done = extend_active(active, mh, bi, blocks[bi][1])
            for chain in done:
                emit(daykey, "down", names_all, chain)

        for chain in active:
            if chain[-1][0] == idx_gkjungang:
                last_t = chain[-1][1]
                chain = chain + [(idx_gkjungang + 1, last_t + EST_LAST_HOP["광교"], False)]
            emit(daykey, "down", names_all, chain)

    for daykey in DAYTYPES:
        process_up(daykey)
        process_down(daykey)

    os.makedirs(OUT, exist_ok=True)

    with open(f"{OUT}/stops.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["stop_id", "name_ko", "merge_key"])
        for name, sid in stops.items():
            w.writerow([sid, name, MERGE_KEY.get(name, "")])

    with open(f"{OUT}/trips.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(trips[0].keys()))
        w.writeheader()
        w.writerows(trips)

    with open(f"{OUT}/stop_times.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["trip_id", "stop_seq", "stop_id", "dep_sec"])
        w.writeheader()
        w.writerows(stop_times)

    with open(f"{OUT}/calendar.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["service_id", "mon", "tue", "wed", "thu", "fri", "sat", "sun"])
        w.writerow(["평일", 1, 1, 1, 1, 1, 0, 0])
        w.writerow(["휴일", 0, 0, 0, 0, 0, 1, 1])

    from collections import Counter
    print(f"stops      {len(stops):6d}")
    print(f"trips      {len(trips):6d}  {dict(Counter((t['direction'], t['service_id']) for t in trips))}")
    print(f"stop_times {len(stop_times):6d}")
    stopname = {sid: n for n, sid in stops.items()}
    dest = Counter((t["direction"], t["service_id"], stopname[t["destination"]]) for t in trips)
    print("destinations:", dict(dest))

    by_trip = {}
    for st in stop_times:
        by_trip.setdefault(st["trip_id"], []).append(st)
    violations = 0
    for tid, rows in by_trip.items():
        rows.sort(key=lambda r: r["stop_seq"])
        for a, b in zip(rows, rows[1:]):
            if b["dep_sec"] < a["dep_sec"]:
                violations += 1
    print(f"monotonic violations: {violations}")


if __name__ == "__main__":
    main()
