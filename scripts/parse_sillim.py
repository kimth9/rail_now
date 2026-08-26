#!/usr/bin/env python3
"""신림선(남서울경전철, 비코레일) 시각표 -> 정규화 테이블

RAW 원본 파일이 없다(운영사가 엑셀을 배포하지 않음) — 공식 홈페이지
(http://www.sillimlrt.com, https 인증서 깨져있어 http로만 접속됨)의 역별
페이지 11개(01010201.html~01010211.html, 샛강→관악산 순)를 curl로 받아
`RAW/web_크롤링/신림선/01.html`~`11.html`로 저장해둔 걸 읽는다.

역 페이지마다 <table> 6개가 고정 순서로 있다: [0]=평일 요약, [1]=평일 하행선
(관악산방면) 역별 발차시각, [2]=평일 상행선(샛강방면), [3]=주말·공휴일 요약,
[4]=주말·공휴일 하행선, [5]=주말·공휴일 상행선(일부 역의 <caption> 텍스트가
"평일"로 잘못 표기돼 있으나 실제 분(分) 값은 다름 — 사이트 표기 오류일 뿐이라
캡션이 아니라 위치(인덱스)로 구분한다).

원본 구조는 김포골드라인·대전1호선과 같은 "출발역 기준 배차표" —
`_station_list_reconstruct.link_trips()`로 열차 단위 trip을 복원한다.
괄호 등 목적지 분기 표기는 관찰되지 않았다(전 역 확인, 단일 종점 노선).
"""
import csv
import os
import re
import sys
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(__file__))
from _station_list_reconstruct import link_trips

SRC_DIR = sys.argv[1] if len(sys.argv) > 1 else "RAW/web_크롤링/신림선"
OUT = sys.argv[2] if len(sys.argv) > 2 else "tmp/out_sillim"

STATION_ORDER = ["샛강", "대방(성애병원)", "서울지방병무청", "보라매", "보라매공원",
                  "보라매병원(전문건설회관)", "당곡", "신림", "서원",
                  "서울대벤처타운", "관악산(서울대)"]
MAX_HOP_MIN = 6
ESTIMATED_LAST_HOP_MIN = 2

# 다른 노선망의 동명역과 무관하게 실제 물리적 환승역인 것만 병합(merge_key로 지정).
# 신림·보라매·샛강은 이름이 그대로 같아 기본 병합(merge_key 생략)으로 자동 연결됨.
MERGE_KEY = {
    "대방(성애병원)": "대방",  # 1호선/경인급행의 "대방"과 실제 환승역(부제만 다름)
}

TABLE_RE = re.compile(r"<table.*?</table>", re.S)
ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
TAG_RE = re.compile(r"<[^>]+>")


def parse_table(table_html):
    """{hour: [minute, ...]} — &nbsp;(빈 셀)는 무시."""
    out = {}
    for row in ROW_RE.findall(table_html):
        cells = CELL_RE.findall(row)
        if len(cells) != 2:
            continue
        hour_txt = TAG_RE.sub("", cells[0]).strip()
        if not hour_txt.isdigit():
            continue
        min_txt = TAG_RE.sub("", cells[1]).replace("&nbsp;", "").strip()
        out[int(hour_txt)] = [int(x) for x in min_txt.split() if x.isdigit()]
    return out


def load_station(idx):
    with open(f"{SRC_DIR}/{idx:02d}.html", encoding="utf-8", errors="ignore") as f:
        html = f.read()
    tables = TABLE_RE.findall(html)
    down_wd, up_wd, down_hol, up_hol = (parse_table(tables[i]) for i in (1, 2, 4, 5))

    def to_minutes(hours):
        return sorted(h * 60 + m for h, ms in hours.items() for m in ms)

    return (to_minutes(down_wd), to_minutes(up_wd),
            to_minutes(down_hol), to_minutes(up_hol))


def main():
    per_station = {name: load_station(i + 1) for i, name in enumerate(STATION_ORDER)}

    stops = OrderedDict()
    for name in STATION_ORDER:
        stops[name] = f"SL{len(stops) + 1:04d}"

    trips, stop_times = [], []

    def process(direction, terminus, station_names, col, daytype_label):
        blocks = [(name, per_station[name][col]) for name in station_names]
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
                "line_id": "SILLIM", "line_name": "신림선",
                "formation": "경전철", "direction": direction,
                "service_id": daytype_label,
                "origin": stops[blocks[chain[0][0]][0]],
                "destination": stops[dest_name],
                "next_train_no": "",
            })

    down_names = STATION_ORDER  # 샛강 -> 관악산
    up_names = list(reversed(STATION_ORDER))  # 관악산 -> 샛강

    process("down", "관악산(서울대)", down_names, 0, "평일")
    process("up", "샛강", up_names, 1, "평일")
    process("down", "관악산(서울대)", down_names, 2, "휴일")
    process("up", "샛강", up_names, 3, "휴일")

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
