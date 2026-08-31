#!/usr/bin/env python3
"""의정부경전철(비코레일) 시각표 -> 정규화 테이블

RAW 원본이 없다(운영사가 엑셀을 배포하지 않음) — 공식 홈페이지
(ulrt.co.kr)의 역별 시각표 이미지(jpg) 29장을 다운로드해 Claude(Sonnet 5)
서브에이전트가 직접 이미지를 읽고 육안으로 전사한 결과를
`RAW/web_크롤링/의정부경전철/raw_extract.txt`에 정리해둔 걸 읽는다.
분(分) 단위 정밀도만 제공(초 단위 없음). 평일/휴일(토+일) 2종 다이어만
존재(대구·부산·광주1호선 같은 3종 다이어 아님 — SUN_ONLY_LABEL 불필요).

원본 구조는 다른 웹크롤링 노선과 같은 "역별 발차 시각 목록"이라
`_station_list_reconstruct.link_trips()`로 열차 단위 trip을 복원한다.

**차량기지임시승강장 분기**: 15개 역(발곡~탑석) 대부분 열차는 탑석에서
정상 종착하지만 일부는 탑석을 지나 차량기지임시승강장까지 연장 운행한다.
역별 시각표 이미지에는 이 연장 열차의 발차 시각이 다른 색(빨간색)으로
표시돼 있었으나(전사 시 (R)로 표기해 남겨둠), 실제 재구성에는 이 색상
플래그를 쓰지 않았다 — 광주1호선의 소태/녹동 분기와 완전히 같은 구조라
그때와 동일한 방식(전 구간 실측 + 분기점 자체의 실측 기록으로 이중
FIFO 재구성)을 그대로 재사용했다: 발곡~송산(상행 방면1) 트렁크를 먼저
FIFO로 이어붙이고, 송산 도달 체인의 마지막 시각을 tapseok-1(탑석→
차량기지, 실측)과 다시 한 번 FIFO 매칭해 매칭되면 차량기지행,
안 되면 탑석 종착으로 확정한다. (R) 플래그는 원본 웹사이트의 시각적
안내일 뿐 재구성 로직에는 불필요해 그대로만 보존(참고용).

하행(탑석→발곡) 방향은 탑석역 자체 발차 목록(tapseok-2, 정상 시종착)에
차량기지에서 복귀하는 depot-2(차량기지→탑석, 추정 2분 소요로 탑석
도착 시각 환산)를 합쳐 하나의 "탑석" 블록으로 만든 뒤 트렁크 FIFO —
광주1호선의 하행(평동 방면) 처리와 대칭되는 구조.

발곡은 방면2가 없고(노선 시종착), 탑석은 방면1이 없다(정상 방면1은
차량기지행 전용이라 tapseok-1로 별도 처리) — 그 외 13개 역은 방면1/2
모두 존재.
"""
import csv
import os
import re
import sys
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(__file__))
from _station_list_reconstruct import link_trips

SRC = sys.argv[1] if len(sys.argv) > 1 else "RAW/web_크롤링/의정부경전철/raw_extract.txt"
OUT = sys.argv[2] if len(sys.argv) > 2 else "tmp/out_uijeongbu"

# 발곡..탑석, 노선 순서 그대로(15개 역)
STATION_ORDER = ["발곡", "회룡", "범골", "경전철의정부", "의정부시청", "흥선",
                  "의정부중앙", "동오", "새말", "경기도청북부청사", "효자",
                  "곤제", "어룡", "송산", "탑석"]

# 역명 -> (방면1 slug 또는 None, 방면2 slug 또는 None)
SLUG = {
    "발곡": ("balgok-1", None),
    "회룡": ("hoeryong-1", "hoeryong-2"),
    "범골": ("beomgol-1", "beomgol-2"),
    "경전철의정부": ("uijeongbu-1", "uijeongbu-2"),
    "의정부시청": ("city-hall-1", "city-hall-2"),
    "흥선": ("heungseon-1", "heungseon-2"),
    "의정부중앙": ("jungang-1", "jungang-2"),
    "동오": ("dongo-1", "dongo-2"),
    "새말": ("saemal-1", "saemal-2"),
    "경기도청북부청사": ("north-office-1", "north-office-2"),
    "효자": ("hyoja-1", "hyoja-2"),
    "곤제": ("gonje-1", "gonje-2"),
    "어룡": ("eoryong-1", "eoryong-2"),
    "송산": ("songsan-1", "songsan-2"),
    "탑석": (None, "tapseok-2"),
}
DEPOT_UP_SLUG = "tapseok-1"   # 탑석 -> 차량기지임시승강장 (상행 연장)
DEPOT_DOWN_SLUG = "depot-2"   # 차량기지임시승강장 -> 탑석 (하행 복귀)
DEPOT_NAME = "차량기지임시승강장"

# 1호선 '회룡'과 실제 환승역 -> merge_key 없이(같은 이름) 자동 병합.
# '경전철의정부'는 표기가 달라 기존 '의정부'(일반열차·1호선)와 명시적 병합.
MERGE_KEY = {"경전철의정부": "의정부"}

MAX_HOP_MIN = 5
ESTIMATED_LAST_HOP_MIN = 2  # 탑석<->차량기지임시승강장 추정 소요시간

HEADER_RE = re.compile(r"^=== (\S+) \((\S+) 방면(\d), (\S+?)행\)")
TOKEN_RE = re.compile(r"^(\d+)(\(R\))?")


def parse_time_list(text):
    """'H:m(R),m,...;H:...' -> [(abs_min, is_r), ...] 오름차순."""
    out = []
    if not text.strip():
        return out
    for part in text.split(";"):
        part = part.strip()
        if not part:
            continue
        hour_s, _, rest = part.partition(":")
        hour = int(hour_s)
        for tok in rest.split(","):
            tok = tok.strip()
            m = TOKEN_RE.match(tok)
            if not m:
                continue
            out.append((hour * 60 + int(m.group(1)), bool(m.group(2))))
    out.sort()
    return out


def load_raw(path):
    """slug -> {"WD": [(abs_min, is_r)], "HD": [...]}"""
    data = {}
    cur = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            m = HEADER_RE.match(line)
            if m:
                cur = m.group(1)
                data[cur] = {"WD": [], "HD": []}
                continue
            m = re.match(r"(WD|HD): (.*)$", line)
            if m and cur:
                data[cur][m.group(1)] = parse_time_list(m.group(2))
    return data


DAYTYPES = ["WD", "HD"]
DAYTYPE_LABEL = {"WD": "평일", "HD": "휴일"}


def main():
    raw = load_raw(SRC)

    stops = OrderedDict()
    for name in STATION_ORDER + [DEPOT_NAME]:
        stops[name] = f"UJ{len(stops) + 1:04d}"

    trips, stop_times = [], []

    def times_of(slug, daykey):
        if not slug or slug not in raw:
            return []
        return [m for m, _r in raw[slug][daykey]]

    def process_up(daykey):
        """상행(탑석 방면) — 발곡..송산(14개 역) 방면1 트렁크 FIFO, 송산 도달
        체인만 tapseok-1(차량기지행 실측)과 재매칭해 탑석/차량기지 분기 확정."""
        trunk_names = STATION_ORDER[:-1]  # 발곡..송산
        blocks = [(n, times_of(SLUG[n][0], daykey)) for n in trunk_names]
        blocks = [(n, t) for n, t in blocks if t]
        if len(blocks) < 2:
            return
        chains = link_trips(blocks, MAX_HOP_MIN)

        depot_times = times_of(DEPOT_UP_SLUG, daykey)
        tail_times = sorted(t for bi, t in (c[-1] for c in chains) if bi == len(blocks) - 1)
        depot_match = {}
        if tail_times and depot_times:
            reconcile = link_trips([("송산_tail", tail_times), (DEPOT_UP_SLUG, depot_times)], MAX_HOP_MIN)
            for rc in reconcile:
                if len(rc) == 2:
                    depot_match[rc[0][1]] = rc[1][1]

        label = DAYTYPE_LABEL[daykey]
        for ci, chain in enumerate(chains):
            if len(chain) < 2:
                continue
            reaches_songsan = chain[-1][0] == len(blocks) - 1
            last_t = chain[-1][1]
            trip_id = f"up#{label}#{ci}"
            for seq, (bi, t) in enumerate(chain, start=1):
                stop_times.append({"trip_id": trip_id, "stop_seq": seq,
                                    "stop_id": stops[blocks[bi][0]], "dep_sec": t * 60})
            dest_name = blocks[chain[-1][0]][0]
            if reaches_songsan:
                matched_depot = depot_match.get(last_t)
                tapseok_t = matched_depot if matched_depot is not None else last_t + ESTIMATED_LAST_HOP_MIN
                stop_times.append({"trip_id": trip_id, "stop_seq": len(chain) + 1,
                                    "stop_id": stops["탑석"], "dep_sec": tapseok_t * 60})
                dest_name = "탑석"
                if matched_depot is not None:
                    stop_times.append({"trip_id": trip_id, "stop_seq": len(chain) + 2,
                                        "stop_id": stops[DEPOT_NAME],
                                        "dep_sec": (matched_depot + ESTIMATED_LAST_HOP_MIN) * 60})
                    dest_name = DEPOT_NAME
            trips.append({"trip_id": trip_id, "train_no": trip_id,
                           "line_id": "UIJEONGBU", "line_name": "의정부경전철",
                           "formation": "경전철", "direction": "up",
                           "service_id": label,
                           "origin": stops[blocks[chain[0][0]][0]],
                           "destination": stops[dest_name], "next_train_no": ""})

    def process_down(daykey):
        """하행(발곡 방면) — 탑석(방면2 실측 ∪ 차량기지 복귀분) 부터 회룡까지
        트렁크 FIFO. 발곡은 방면2가 없어 트렁크에 포함하지 않음(회룡에서 종착)."""
        tapseok_times = sorted(set(times_of(SLUG["탑석"][1], daykey)) |
                                {t + ESTIMATED_LAST_HOP_MIN for t in times_of(DEPOT_DOWN_SLUG, daykey)})
        names = list(reversed(STATION_ORDER[:-1]))  # 송산..회룡
        blocks = [("탑석", tapseok_times)] + [(n, times_of(SLUG[n][1], daykey)) for n in names]
        blocks = [(n, t) for n, t in blocks if t]
        if len(blocks) < 2:
            return
        chains = link_trips(blocks, MAX_HOP_MIN)

        label = DAYTYPE_LABEL[daykey]
        for ci, chain in enumerate(chains):
            if len(chain) < 2:
                continue
            trip_id = f"down#{label}#{ci}"
            for seq, (bi, t) in enumerate(chain, start=1):
                stop_times.append({"trip_id": trip_id, "stop_seq": seq,
                                    "stop_id": stops[blocks[bi][0]], "dep_sec": t * 60})
            dest_name = blocks[chain[-1][0]][0]
            trips.append({"trip_id": trip_id, "train_no": trip_id,
                           "line_id": "UIJEONGBU", "line_name": "의정부경전철",
                           "formation": "경전철", "direction": "down",
                           "service_id": label,
                           "origin": stops[blocks[chain[0][0]][0]],
                           "destination": stops[dest_name], "next_train_no": ""})

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
    dest_count = Counter(t["destination"] for t in trips if t["direction"] == "up")
    print(f"up-destination breakdown: {dict(dest_count)}")

    # 단조증가 검증
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
