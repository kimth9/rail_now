#!/usr/bin/env python3
"""광주 도시철도 1호선(광주교통공사, 비코레일) 시각표 -> 정규화 테이블

RAW 원본 파일이 없다(운영사가 엑셀을 배포하지 않음) — 공식 사이버스테이션
(grtc.co.kr/cyber?timetable=N, N=1~20)에서 역별로 "열차시각표" 탭을 열어
DOM(class="pd"/"nd", 평일=WEEK/토요일=SAT/휴일=DAYOFF/명절=HOLI)을 직접 읽어
`RAW/web_크롤링/광주1호선/raw_extract.txt`로 정리해둔 걸 읽는다. 브라우저
자동화(역 클릭 → 탭 클릭 → DOM 추출)로 20개 역 × 4개 다이어를 전부 확보 —
정찰 중 `/cyber/portlet/subwayTimetable` 내부 API(POST)를 발견했지만 세션
파라미터를 알아내지 못해 재현이 안 돼, DOM 직접 추출로 대체했다.

원본 구조는 김포골드라인 등과 같은 "역별 발차 시각 목록"이라
`_station_list_reconstruct.link_trips()`로 열차 단위 trip을 복원한다.

**목적지 분기(소태행/녹동행)**: 대부분 열차는 소태에서 종착하고 일부만
녹동까지 연장 운행한다. 사이버스테이션 페이지가 이 분기를 이미 CSS
class("nd" = 녹동행 전용 표시)로 구분해 두고 있어, 사용자가 우려했던
"색상 정보라 못 뽑는다"는 문제를 겪지 않고 스크레이핑 시점에 이미 각
시각이 녹동행인지 여부를 확정해 가져올 수 있었다(원본 텍스트에도
"녹동행"이라는 접두 라벨이 실제로 박혀 있음). 상행(소태 방향, ND 컬럼)
재구성 시 각 시각을 FIFO로 이어붙이되, 소태역 자체에 도달한 체인의
마지막 시각이 "nd"로 표시돼 있으면 그 열차만 녹동까지 연장(추정
소요시간만큼 더해 도착시각 근사), 아니면 소태에서 종착시킨다.

원본 데이터 이상치 1건 확인: 금남로4가역 휴일(명절) 다이어 20시대에
"99분"이라는 있을 수 없는 값이 있었다(앞뒤 값이 07,20,33,46 순으로 13분
간격이라 다음 값은 59여야 함) — 59로 보정. 문화전당(구도청)역 휴일(명절)
다이어 9시대의 "60분"은 오탈자가 아니라 절대 분(9시*60+60=10시*60+0과
동일)로 계산해도 자연히 다음 시간대와 순서가 맞아 그대로 둔다.
"""
import csv
import os
import re
import sys
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(__file__))
from _station_list_reconstruct import link_trips

SRC = sys.argv[1] if len(sys.argv) > 1 else "RAW/web_크롤링/광주1호선/raw_extract.txt"
OUT = sys.argv[2] if len(sys.argv) > 2 else "tmp/out_gwangju1"

STATION_ORDER = ["평동", "도산", "광주송정역", "송정공원", "공항",
                  "김대중컨벤션센터(마륵)", "상무", "운천", "쌍촌", "화정",
                  "농성", "돌고개", "양동시장", "금남로5가", "금남로4가",
                  "문화전당(구도청)", "남광주", "학동증심사입구", "소태", "녹동"]
# raw_extract.txt의 "=== station N 역명 ===" 헤더는 중점(·)이 빠져 있어(스크래핑
# 당시 표기 그대로) STATION_ORDER는 그 표기를 그대로 써서 내부 매칭에 쓰고,
# 실제 역명(display)만 이 표로 되돌린다.
DISPLAY_NAME = {"학동증심사입구": "학동·증심사입구"}

# 다른 노선망과 이름이 겹치는 역 — 실제 환승역만 병합, 우연히 동명인 역은 분리
MERGE_KEY = {
    "광주송정역": "광주송정",  # KTX·일반열차 '광주송정'과 실제 환승역(표기만 다름)
    "화정": "광주화정",  # 일산선(고양시) '화정'과 무관
    "운천": "광주운천",  # 경의선(파주시) '운천'과 무관
}

DAYTYPES = ["WEEK", "SAT", "HOLI", "DAYOFF"]
DAYTYPE_LABEL = {"WEEK": "평일", "SAT": "토요일", "DAYOFF": "휴일", "HOLI": "명절"}

MAX_HOP_MIN = 6
ESTIMATED_LAST_HOP_MIN = 2

# 원본 사이트 자체의 오탈자 1건 보정(주석 참조) — (역, daykey, 시, 잘못된 분) -> 올바른 분
KNOWN_TYPO_FIX = {("금남로4가", "HOLI", 20, 99): 59}

TOKEN_RE = re.compile(r"^(\d+)")


def parse_minute_list(text):
    """'H:m,m,m;H:m,m,m' -> [(hour, [raw_min,...])], 괄호 주석은 무시."""
    text = text.strip()
    if not text or text == "(none)":
        return []
    blocks = []
    for part in text.split(";"):
        part = part.strip()
        if not part:
            continue
        hour_s, _, rest = part.partition(":")
        hour = int(hour_s)
        mins = []
        if rest:
            for tok in rest.split(","):
                m = TOKEN_RE.match(tok.strip())
                if m:
                    mins.append(int(m.group(1)))
        blocks.append((hour, mins))
    return blocks


def load_raw(path):
    """station -> {daykey: {"PD": text, "ND": text}}"""
    data = OrderedDict()
    current = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            m = re.match(r"=== station \d+ (\S+)", line)
            if m:
                current = m.group(1)
                data[current] = {}
                continue
            m = re.match(r"(WEEK|SAT|HOLI|DAYOFF):\s*(.*)$", line)
            if m and current:
                daykey, rest = m.group(1), m.group(2)
                pd_text, _, nd_text = rest.partition("||")
                pd_text = pd_text.replace("PD", "", 1).strip()
                nd_text = nd_text.replace("ND", "", 1)
                nd_text = re.sub(r"\(전부 녹동행\)", "", nd_text).strip()
                data[current][daykey] = {"PD": pd_text, "ND": nd_text}
    return data


def to_abs_minutes(station, daykey, col, blocks):
    """[(hour, [raw_min,...])] -> [(abs_min, is_nd)], 오탈자 보정 포함."""
    out = []
    for hour, raws in blocks:
        for raw in raws:
            fixed = KNOWN_TYPO_FIX.get((station, daykey, hour, raw))
            if fixed is not None:
                raw = fixed
            is_nd = raw >= 100
            real_min = raw - 100 if is_nd else raw
            out.append((hour * 60 + real_min, is_nd))
    out.sort()
    return out


def main():
    raw = load_raw(SRC)

    # station -> daykey -> {"PD": [(abs_min, is_nd)], "ND": [...]}
    parsed = {}
    for station in STATION_ORDER:
        parsed[station] = {}
        for daykey in DAYTYPES:
            entry = raw.get(station, {}).get(daykey, {"PD": "", "ND": ""})
            parsed[station][daykey] = {
                "PD": to_abs_minutes(station, daykey, "PD", parse_minute_list(entry["PD"])),
                "ND": to_abs_minutes(station, daykey, "ND", parse_minute_list(entry["ND"])),
            }

    stops = OrderedDict()
    for name in STATION_ORDER:
        stops[name] = f"GJ{len(stops) + 1:04d}"

    trips, stop_times = [], []

    def process_down(daykey):
        """하행(평동방면) — 녹동..도산(19개 역) PD 사용, 평동은 추정 종착."""
        names = list(reversed(STATION_ORDER[1:]))  # 녹동..도산
        blocks = [(n, [m for m, _nd in parsed[n][daykey]["PD"]]) for n in names]
        blocks = [(n, times) for n, times in blocks if times]
        if len(blocks) < 2:
            return
        chains = link_trips(blocks, MAX_HOP_MIN)
        label = DAYTYPE_LABEL[daykey]
        for ci, chain in enumerate(chains):
            if len(chain) < 2:
                continue
            full_run = chain[-1][0] == len(blocks) - 1
            trip_id = f"down#{label}#{ci}"
            for seq, (bi, t) in enumerate(chain, start=1):
                stop_times.append({"trip_id": trip_id, "stop_seq": seq,
                                    "stop_id": stops[blocks[bi][0]], "dep_sec": t * 60})
            dest_name = blocks[chain[-1][0]][0]
            if full_run:
                stop_times.append({"trip_id": trip_id, "stop_seq": len(chain) + 1,
                                    "stop_id": stops["평동"],
                                    "dep_sec": (chain[-1][1] + ESTIMATED_LAST_HOP_MIN) * 60})
                dest_name = "평동"
            trips.append({"trip_id": trip_id, "train_no": trip_id,
                           "line_id": "GWANGJU1", "line_name": "광주1호선",
                           "formation": "도시철도", "direction": "down",
                           "service_id": label,
                           "origin": stops[blocks[chain[0][0]][0]],
                           "destination": stops[dest_name], "next_train_no": ""})

    def process_up(daykey):
        """상행(소태/녹동 방면) — 평동..학동(18개 역, 트렁크 구간)까지는 소태행/
        녹동행 열차가 전부 섞여서 같이 다니므로 ND 값을 그대로 FIFO 재구성.
        소태역 자체의 ND 기록은(확인 결과) 소태에서 종착하는 열차는 없고
        **녹동까지 연장 운행하는 열차만** 남아있다 — 즉 소태는 대부분 열차에게
        "도착만 하고 끝"이라 도착 기록이 별도로 없다(평동·녹동처럼 편도 종점
        추정이 필요한 역). 그래서 트렁크 체인이 학동까지 도달하면, 그 시각과
        소태의 (전부 녹동행인) 실제 기록을 다시 한 번 link_trips로 매칭해
        - 매칭되면: 그 실제 소태 시각을 그대로 쓰고 녹동까지 추정 연장(녹동행)
        - 매칭 안 되면: 학동 시각 + 추정 소요시간으로 소태 도착 근사(소태행)
        """
        trunk_names = STATION_ORDER[:-2]  # 평동..학동 (18개)
        sotae_name, nokdong_name = STATION_ORDER[-2], STATION_ORDER[-1]
        trunk_blocks = [(n, [m for m, _nd in parsed[n][daykey]["ND"]]) for n in trunk_names]
        trunk_blocks = [(n, times) for n, times in trunk_blocks if times]
        if len(trunk_blocks) < 2:
            return
        chains = link_trips(trunk_blocks, MAX_HOP_MIN)

        sotae_times = sorted(m for m, _nd in parsed[sotae_name][daykey]["ND"])
        tail_times = sorted(t for bi, t in (c[-1] for c in chains) if bi == len(trunk_blocks) - 1)
        sotae_match = {}
        if tail_times and sotae_times:
            reconcile = link_trips([("학동_tail", tail_times), (sotae_name, sotae_times)], MAX_HOP_MIN)
            for rc in reconcile:
                if len(rc) == 2:
                    sotae_match[rc[0][1]] = rc[1][1]

        label = DAYTYPE_LABEL[daykey]
        for ci, chain in enumerate(chains):
            if len(chain) < 2:
                continue
            reaches_hakdong = chain[-1][0] == len(trunk_blocks) - 1
            last_t = chain[-1][1]
            trip_id = f"up#{label}#{ci}"
            for seq, (bi, t) in enumerate(chain, start=1):
                stop_times.append({"trip_id": trip_id, "stop_seq": seq,
                                    "stop_id": stops[trunk_blocks[bi][0]], "dep_sec": t * 60})
            dest_name = trunk_blocks[chain[-1][0]][0]
            if reaches_hakdong:
                matched_sotae = sotae_match.get(last_t)
                if matched_sotae is not None:
                    stop_times.append({"trip_id": trip_id, "stop_seq": len(chain) + 1,
                                        "stop_id": stops[sotae_name], "dep_sec": matched_sotae * 60})
                    stop_times.append({"trip_id": trip_id, "stop_seq": len(chain) + 2,
                                        "stop_id": stops[nokdong_name],
                                        "dep_sec": (matched_sotae + ESTIMATED_LAST_HOP_MIN) * 60})
                    dest_name = nokdong_name
                else:
                    stop_times.append({"trip_id": trip_id, "stop_seq": len(chain) + 1,
                                        "stop_id": stops[sotae_name],
                                        "dep_sec": (last_t + ESTIMATED_LAST_HOP_MIN) * 60})
                    dest_name = sotae_name
            trips.append({"trip_id": trip_id, "train_no": trip_id,
                           "line_id": "GWANGJU1", "line_name": "광주1호선",
                           "formation": "도시철도", "direction": "up",
                           "service_id": label,
                           "origin": stops[trunk_blocks[chain[0][0]][0]],
                           "destination": stops[dest_name], "next_train_no": ""})

    for daykey in DAYTYPES:
        process_down(daykey)
        process_up(daykey)

    os.makedirs(OUT, exist_ok=True)

    with open(f"{OUT}/stops.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["stop_id", "name_ko", "merge_key"])
        for name, sid in stops.items():
            w.writerow([sid, DISPLAY_NAME.get(name, name), MERGE_KEY.get(name, "")])

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
        w.writerow(["토요일", 0, 0, 0, 0, 0, 1, 0])
        w.writerow(["휴일", 0, 0, 0, 0, 0, 0, 1])
        w.writerow(["명절", 0, 0, 0, 0, 0, 0, 0])  # 날짜기반(calendar_dates류) — 요일 매핑 없음

    from collections import Counter
    print(f"stops      {len(stops):6d}")
    print(f"trips      {len(trips):6d}  {dict(Counter((t['direction'], t['service_id']) for t in trips))}")
    print(f"stop_times {len(stop_times):6d}")
    dest_count = Counter(t["destination"] for t in trips if t["direction"] == "up")
    print(f"up-destination breakdown: {dict(dest_count)}")


if __name__ == "__main__":
    main()
