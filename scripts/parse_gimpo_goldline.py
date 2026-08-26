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

시각 표기에 괄호가 섞여있다(예: `(08) 10 13`) — 사이트에 범례가 없었지만
사용자 확인(2026-08-26): **괄호 = 양촌행 열차, 비괄호 = 구래행(단축) 열차**.
양촌역은 차량기지 성격이라 운행 횟수가 적어, "구래(양촌) 방면" 표 하나에
실제로는 종점이 다른 두 종류의 열차가 섞여 실려있는 것 — 괄호 여부로 미리
분리하지 않으면 FIFO 재구성이 서로 다른 두 열차의 시각을 잘못 이어붙일 위험이
있다. 그래서 상행(양촌 방향)은 두 그룹을 완전히 분리해 각각 재구성한다
(양촌행=괄호 값만, 구래행=비괄호 값만 + 구래에서 종착). 하행(김포공항 방면)은
표에 괄호가 전혀 없어(모든 역에서 확인) 분리가 필요 없다.
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

PAREN_RE = re.compile(r"\((\d{1,2})\)")
BARE_RE = re.compile(r"(?<!\()\b(\d{1,2})\b(?!\))")


def clean_station(name):
    return name[:-1] if name.endswith("역") else name


def parse_minutes_split(cell_text):
    """(괄호 안 분 목록, 괄호 밖 분 목록) — 괄호=양촌행, 비괄호=구래행(단축)."""
    if cell_text.strip() == "-":
        return [], []
    return ([int(x) for x in PAREN_RE.findall(cell_text)],
            [int(x) for x in BARE_RE.findall(cell_text)])


def main():
    with open(SRC, encoding="utf-8") as f:
        raw_tables = json.load(f)

    # 역별로 테이블을 순서대로 수집(양촌·김포공항은 1개, 나머지는 2개 — 첫 번째가
    # "김포공항 방면"(하행), 두 번째가 "양촌 방면"(상행)임을 station 등장 순서로 확정)
    by_station = OrderedDict()
    for station, _direction_label, rows in raw_tables:
        name = clean_station(station)
        by_station.setdefault(name, []).append(rows)

    # 역별로 (평일_괄호, 평일_비괄호, 휴일_괄호, 휴일_비괄호) 4종 분(分) 리스트 생성
    def build_blocks(station_names, table_index):
        blocks = []
        for name in station_names:
            tables = by_station[name]
            if table_index >= len(tables):
                continue
            rows = tables[table_index]
            w_paren, w_bare, h_paren, h_bare = [], [], [], []
            for hour_s, w_cell, h_cell in rows:
                hour = int(hour_s)
                p, b = parse_minutes_split(w_cell)
                w_paren += [hour * 60 + m for m in p]
                w_bare += [hour * 60 + m for m in b]
                p, b = parse_minutes_split(h_cell)
                h_paren += [hour * 60 + m for m in p]
                h_bare += [hour * 60 + m for m in b]
            blocks.append((name, sorted(w_paren), sorted(w_bare), sorted(h_paren), sorted(h_bare)))
        return blocks

    # 김포공항 방면(하행)은 전 역에서 괄호가 전혀 없음(확인됨) — 비괄호(=전부) 값만 사용
    down_blocks_raw = build_blocks(STATION_ORDER[:-1], 0)   # 양촌..고촌

    # 양촌 방면(상행)은 괄호=양촌행/비괄호=구래행(단축)이 섞여있어 분리 필요.
    # 구래~고촌은 테이블 2개(0=김포공항 방면, 1=양촌 방면), 김포공항은 1개(0=양촌 방면)
    up_stations = list(reversed(STATION_ORDER[1:]))   # 김포공항..구래
    up_blocks_raw = []
    for name in up_stations:
        tables = by_station[name]
        idx = 1 if len(tables) > 1 else 0
        rows = tables[idx]
        w_paren, w_bare, h_paren, h_bare = [], [], [], []
        for hour_s, w_cell, h_cell in rows:
            hour = int(hour_s)
            p, b = parse_minutes_split(w_cell)
            w_paren += [hour * 60 + m for m in p]
            w_bare += [hour * 60 + m for m in b]
            p, b = parse_minutes_split(h_cell)
            h_paren += [hour * 60 + m for m in p]
            h_bare += [hour * 60 + m for m in b]
        up_blocks_raw.append((name, sorted(w_paren), sorted(w_bare), sorted(h_paren), sorted(h_bare)))

    stops = OrderedDict()
    for name in STATION_ORDER:
        stops[name] = f"GG{len(stops) + 1:04d}"

    trips, stop_times = [], []

    def process(direction, terminus, blocks, daytype_label):
        """blocks: [(역명, [시각(분)]), ...] — daytype·괄호여부로 이미 골라둔 것."""
        blocks = [(name, times) for name, times in blocks if times]
        if len(blocks) < 2:
            return
        chains = link_trips(blocks, MAX_HOP_MIN)
        for ci, chain in enumerate(chains):
            if len(chain) < 2:
                continue
            full_run = chain[-1][0] == len(blocks) - 1
            trip_id = f"{direction}#{terminus}#{daytype_label}#{ci}"
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

    process("down", "김포공항", [(n, wb) for n, _wp, wb, _hp, _hb in down_blocks_raw], "평일")
    process("down", "김포공항", [(n, hb) for n, _wp, _wb, _hp, hb in down_blocks_raw], "휴일")
    process("up", "양촌", [(n, wp) for n, wp, _wb, _hp, _hb in up_blocks_raw], "평일")
    process("up", "양촌", [(n, hp) for n, _wp, _wb, hp, _hb in up_blocks_raw], "휴일")
    process("up", "구래", [(n, wb) for n, _wp, wb, _hp, _hb in up_blocks_raw], "평일")
    process("up", "구래", [(n, hb) for n, _wp, _wb, _hp, hb in up_blocks_raw], "휴일")

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
