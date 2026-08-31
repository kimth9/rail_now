#!/usr/bin/env python3
"""우이신설선(우이신설경전철, 비코레일) 시각표 -> 정규화 테이블

RAW 원본 파일이 없다(운영사가 엑셀을 배포하지 않음) — 공식 홈페이지
(https://www.ui-line.com)의 역별 페이지 13개를 curl로 받아 `RAW/web_크롤링/
우이신설선/01.html`~`13.html`로 저장해둔 걸 읽는다. 역 링크가
`javascript:f_route('05')` 형태라 JS 실행이 필요해 보였지만, 실제
`f_route()` 정의는 `location.href = "/html/intro/intro00/intro_00_" + arg
+ ".php?pGubn=T2"`로 단순 페이지 이동이라 브라우저 자동화 없이 curl
순차 GET으로 끝났다.

역 페이지마다 `<table>` 4개가 고정 순서로 있다: [0]=평일 요약, [1]=평일
상세(하선(북한산우이 방향)/시각/상선(신설동 방향) 3열 — 신림선과 달리
양방향이 한 테이블에 같이 있음), [2]=주말 요약, [3]=주말 상세. 신림선과
달리 daytype 탭이 "평일"/"주말" 2개뿐(토요일 별도 없음).

원본 구조는 김포골드라인·대전1호선과 같은 "출발역 기준 배차표" —
`_station_list_reconstruct.link_trips()`로 열차 단위 trip을 복원한다.
괄호 등 목적지 분기 표기는 관찰되지 않았다(단일 종점 노선).
"""
import csv
import os
import re
import sys
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(__file__))
from _station_list_reconstruct import link_trips

SRC_DIR = sys.argv[1] if len(sys.argv) > 1 else "RAW/web_크롤링/우이신설선"
OUT = sys.argv[2] if len(sys.argv) > 2 else "tmp/out_ui_sinseol"

STATION_ORDER = ["북한산우이", "솔밭공원", "4·19민주묘지", "가오리", "화계",
                  "삼양", "삼양사거리", "솔샘", "북한산보국문", "정릉",
                  "성신여대입구", "보문", "신설동"]
MAX_HOP_MIN = 6
ESTIMATED_LAST_HOP_MIN = 2

# 성신여대입구(4호선/안산과천선)·보문(6호선)·신설동(1호선)은 실제 환승역이라
# 이름 그대로 자동 병합되게 두고, 별도 merge_key가 필요한 동명역 충돌 없음.

TABLE_RE = re.compile(r"<table.*?</table>", re.S)
ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
TAG_RE = re.compile(r"<[^>]+>")
HOUR_RE = re.compile(r"(\d{1,2})시")


def parse_detail_table(table_html):
    """{hour: (down_minutes, up_minutes)} — 하선(북한산우이 방향)/상선(신설동 방향)."""
    out = {}
    for row in ROW_RE.findall(table_html):
        cells = CELL_RE.findall(row)
        if len(cells) != 3:
            continue
        cells = [TAG_RE.sub("", c).strip() for c in cells]
        m = HOUR_RE.fullmatch(cells[1])
        if not m:
            continue
        hour = int(m.group(1))
        down = [int(x) for x in cells[0].split() if x.isdigit()]
        up = [int(x) for x in cells[2].split() if x.isdigit()]
        out[hour] = (down, up)
    return out


def load_station(idx):
    with open(f"{SRC_DIR}/{idx:02d}.html", encoding="utf-8-sig") as f:
        html = f.read()
    tables = TABLE_RE.findall(html)
    weekday, weekend = (parse_detail_table(tables[i]) for i in (1, 3))

    def to_minutes(hours, col):
        return sorted(h * 60 + m for h, cols in hours.items() for m in cols[col])

    return (to_minutes(weekday, 0), to_minutes(weekday, 1),
            to_minutes(weekend, 0), to_minutes(weekend, 1))


def main():
    per_station = {name: load_station(i + 1) for i, name in enumerate(STATION_ORDER)}

    stops = OrderedDict()
    for name in STATION_ORDER:
        stops[name] = f"UI{len(stops) + 1:04d}"

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
                "line_id": "UI_SINSEOL", "line_name": "우이신설선",
                "formation": "경전철", "direction": direction,
                "service_id": daytype_label,
                "origin": stops[blocks[chain[0][0]][0]],
                "destination": stops[dest_name],
                "next_train_no": "",
            })

    down_names = list(reversed(STATION_ORDER))  # 신설동 -> 북한산우이 (하선)
    up_names = STATION_ORDER  # 북한산우이 -> 신설동 (상선)

    process("down", "북한산우이", down_names, 0, "평일")
    process("up", "신설동", up_names, 1, "평일")
    process("down", "북한산우이", down_names, 2, "휴일")
    process("up", "신설동", up_names, 3, "휴일")

    os.makedirs(OUT, exist_ok=True)

    with open(f"{OUT}/stops.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["stop_id", "name_ko", "merge_key"])
        for name, sid in stops.items():
            w.writerow([sid, name, ""])

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
