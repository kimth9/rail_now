#!/usr/bin/env python3
"""김포골드라인(김포골드라인운영, 비코레일) 시각표 -> 정규화 테이블

RAW 원본 파일이 없다(운영사가 엑셀을 배포하지 않음) — 공식 홈페이지
(https://gimpogoldline.com/?page_id=484)를 2026-08-26에 브라우저로 방문해 DOM을
직접 읽어(각 역 tab의 `<table>`에 `td.hour`/`td.minute-w`(평일)/`td.minute-h`
(토요일·일요일·공휴일) 구조로 전 역 데이터가 항상 로드돼 있음— tab 클릭은 단순
CSS 표시 전환이라 JS로 한 번에 전부 추출 가능) `RAW/web_크롤링/김포골드라인/
gimpo_goldline_raw.json`으로 저장해둔 걸 읽는다.

원본 구조는 "출발역 기준 배차표"(대전1호선과 같은 부류) — 열차 단위 컬럼이 없고
역마다 그 역을 출발하는 시각 목록만 있다. `_station_list_reconstruct.link_trips()`
로 열차 단위 trip을 복원한다.

시각 표기에 괄호가 섞여있다(예: `(08) 10 13`) — 사이트에 범례가 없고 CSS로도
구분이 안 돼 의미를 특정하지 못했다(값 자체는 항상 유효한 분 단위 시각). 실제
승차 가능한 시각이라는 점은 분명하므로 괄호를 벗기고 모두 동일하게 취급했다 —
후속 조사에서 의미가 밝혀지면(예: 특정 조건부 운행) 재검토 필요.
"""
import csv
import json
import os
import re
import sys
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(__file__))
from _station_list_reconstruct import link_trips

SRC = sys.argv[1] if len(sys.argv) > 1 else \
    "RAW/web_크롤링/김포골드라인/gimpo_goldline_raw.json"
OUT = sys.argv[2] if len(sys.argv) > 2 else "tmp/out_gimpo_goldline"

STATION_ORDER = ["양촌", "구래", "마산", "장기", "운양", "걸포북변",
                 "사우(김포시청)", "풍무", "고촌", "김포공항"]
MAX_HOP_MIN = 6
ESTIMATED_LAST_HOP_MIN = 3   # 종점 자체는 "출발" 기록이 없어 근사(대전1호선과 동일 방식)

# 김포 밖 다른 노선망에 무관한 동명역이 있어 이름만 보고 자동 병합하면 오작동한다.
MERGE_KEY = {
    "마산": "김포마산",  # 경전선(일반열차) 마산(경남 창원)과 무관
    "고촌": "김포고촌",  # 부산4호선 고촌(부산 해운대구)과 무관
}

NUM_RE = re.compile(r"\(?(\d{1,2})\)?")


def clean_station(name):
    return name[:-1] if name.endswith("역") else name


def parse_minutes(cell_text):
    if cell_text.strip() == "-":
        return []
    return [int(m.group(1)) for m in NUM_RE.finditer(cell_text)]


def main():
    with open(SRC, encoding="utf-8") as f:
        raw_tables = json.load(f)

    # 역별로 테이블을 순서대로 수집(양촌·김포공항은 1개, 나머지는 2개 — 첫 번째가
    # "김포공항 방면"(하행), 두 번째가 "양촌 방면"(상행)임을 station 등장 순서로 확정)
    by_station = OrderedDict()
    for station, _direction_label, rows in raw_tables:
        name = clean_station(station)
        by_station.setdefault(name, []).append(rows)

    # daytype별로 (역명, [시각(분)]) 블록 생성
    def build_blocks(station_names, table_index):
        blocks = []
        for name in station_names:
            tables = by_station[name]
            if table_index >= len(tables):
                continue
            rows = tables[table_index]
            times_w, times_h = [], []
            for hour_s, w_cell, h_cell in rows:
                hour = int(hour_s)
                for m in parse_minutes(w_cell):
                    times_w.append(hour * 60 + m)
                for m in parse_minutes(h_cell):
                    times_h.append(hour * 60 + m)
            blocks.append((name, sorted(times_w), sorted(times_h)))
        return blocks

    down_blocks_raw = build_blocks(STATION_ORDER[:-1], 0)   # 양촌..고촌, "김포공항 방면"

    # 구래~고촌은 테이블 2개(0=김포공항 방면, 1=양촌 방면), 김포공항은 1개(0=양촌 방면)
    up_blocks_raw = []
    for name in reversed(STATION_ORDER[1:]):
        tables = by_station[name]
        idx = 1 if len(tables) > 1 else 0
        rows = tables[idx]
        times_w, times_h = [], []
        for hour_s, w_cell, h_cell in rows:
            hour = int(hour_s)
            for m in parse_minutes(w_cell):
                times_w.append(hour * 60 + m)
            for m in parse_minutes(h_cell):
                times_h.append(hour * 60 + m)
        up_blocks_raw.append((name, sorted(times_w), sorted(times_h)))

    stops = OrderedDict()
    for name in STATION_ORDER:
        stops[name] = f"GG{len(stops) + 1:04d}"

    trips, stop_times = [], []

    def process(direction, terminus, blocks_raw, daytype_key, daytype_label):
        blocks = [(name, w if daytype_key == "w" else h)
                  for name, w, h in blocks_raw]
        blocks = [(name, times) for name, times in blocks if times]
        if len(blocks) < 2:
            return
        chains = link_trips(blocks, MAX_HOP_MIN)
        for ci, chain in enumerate(chains):
            if len(chain) < 2:
                continue
            full_run = chain[-1][0] == len(blocks) - 1
            trip_id = f"{direction}#{daytype_label}#{ci}"
            for seq, (block_idx, t) in enumerate(chain, start=1):
                stop_times.append({
                    "trip_id": trip_id, "stop_seq": seq,
                    "stop_id": stops[blocks[block_idx][0]],
                    "dep_sec": t * 60,
                })
            dest_name = blocks[chain[-1][0]][0]
            if full_run:
                stop_times.append({
                    "trip_id": trip_id, "stop_seq": len(chain) + 1,
                    "stop_id": stops[terminus],
                    "dep_sec": (chain[-1][1] + ESTIMATED_LAST_HOP_MIN) * 60,
                })
                dest_name = terminus
            trips.append({
                "trip_id": trip_id, "train_no": trip_id,
                "line_id": "GIMPO_GOLDLINE", "line_name": "김포골드라인",
                "formation": "경전철", "direction": direction,
                "service_id": daytype_label,
                "origin": stops[blocks[chain[0][0]][0]],
                "destination": stops[dest_name],
                "next_train_no": "",
            })

    process("down", "김포공항", down_blocks_raw, "w", "평일")
    process("down", "김포공항", down_blocks_raw, "h", "휴일")
    process("up", "양촌", up_blocks_raw, "w", "평일")
    process("up", "양촌", up_blocks_raw, "h", "휴일")

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


if __name__ == "__main__":
    main()
