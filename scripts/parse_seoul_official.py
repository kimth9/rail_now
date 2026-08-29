#!/usr/bin/env python3
"""서울교통공사 공식 데이터포털 CSV("서울 도시철도 열차운행시각표") -> 정규화 테이블.

RAW 엑셀 파서들(열차=행/역=열)과 달리 이 CSV는 "역 하나당 그 역을 지나는 모든
열차" 구조 — (호선,주중주말,방향,열차코드)로 묶어 트립을 역추적한다. 급행
통과역은 행 자체가 없어(엑셀 파서의 '빈 시각 칸'과 달리) stop_type이 전부
origin/destination/stop뿐이다. 주중주말이 3종(DAY/SAT/END=평일/토요일/휴일)이라
대구·부산·광주1호선과 같은 계열로 build_db.py에서 SUN_ONLY_LABEL 처리가 필요.
"""
import csv
import os
import re
import sys
from collections import OrderedDict, defaultdict

SRC = sys.argv[1]
LINE = sys.argv[2]  # "5","6","8","9" 등 CSV의 '호선' 컬럼 값
OUT = sys.argv[3]

DAYTYPE = {"DAY": "평일", "SAT": "토요일", "END": "휴일"}
TIME_RE = re.compile(r"^(\d{1,2}):(\d{2}):(\d{2})$")


def to_sec(v):
    if not v:
        return None
    m = TIME_RE.match(v.strip())
    if not m:
        return None
    h, mi, s = (int(x) for x in m.groups())
    return h * 3600 + mi * 60 + s


def main():
    stops = OrderedDict()
    groups = defaultdict(list)

    with open(SRC, encoding="cp949") as f:
        for row in csv.DictReader(f):
            if row["호선"] != LINE:
                continue
            name = row["역사명"]
            if name not in stops:
                stops[name] = f"S{LINE}M{len(stops) + 1:04d}"
            key = (row["주중주말"], row["방향"], row["열차코드"])
            groups[key].append({"name": name, "arr": to_sec(row["열차도착시간"]),
                                 "dep": to_sec(row["열차출발시간"])})

    trips, stop_times, warnings = [], [], []
    for (daytype, direction, train_no), rows in groups.items():
        rows.sort(key=lambda e: e["dep"] if e["dep"] is not None else e["arr"])

        rolled, prev = 0, -1
        for e in rows:
            for k in ("arr", "dep"):
                if e[k] is None:
                    continue
                adj = e[k] + rolled * 86400
                if prev >= 0 and adj < prev:
                    rolled += 1
                    adj = e[k] + rolled * 86400
                e[k] = adj
                prev = adj

        if len(rows) < 2:
            warnings.append(f"{daytype}/{direction}/{train_no}: 정차 {len(rows)}개 — 제외")
            continue

        trip_id = f"{DAYTYPE[daytype]}#{direction}#{train_no}"
        for seq, e in enumerate(rows, start=1):
            kind = "origin" if seq == 1 else ("destination" if seq == len(rows) else "stop")
            stop_times.append({
                "trip_id": trip_id, "stop_seq": seq, "stop_id": stops[e["name"]],
                "arr_sec": e["arr"] if e["arr"] is not None else "",
                "dep_sec": e["dep"] if e["dep"] is not None else "",
                "stop_type": kind,
            })
        trips.append({
            "trip_id": trip_id, "train_no": train_no,
            "line_id": f"SEOUL{LINE}", "line_name": f"{LINE}호선",
            "formation": "전동차", "direction": direction.lower(),
            "service_id": DAYTYPE[daytype],
            "origin": stops[rows[0]["name"]], "destination": stops[rows[-1]["name"]],
            "next_train_no": "",
        })

    os.makedirs(OUT, exist_ok=True)

    with open(f"{OUT}/stops.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["stop_id", "name_ko"])
        for name, sid in stops.items():
            w.writerow([sid, name])

    with open(f"{OUT}/trips.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(trips[0].keys()))
        w.writeheader()
        w.writerows(trips)

    with open(f"{OUT}/stop_times.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["trip_id", "stop_seq", "stop_id",
                                          "arr_sec", "dep_sec", "stop_type"])
        w.writeheader()
        w.writerows(stop_times)

    with open(f"{OUT}/calendar.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["service_id", "mon", "tue", "wed", "thu", "fri", "sat", "sun"])
        w.writerow(["평일", 1, 1, 1, 1, 1, 0, 0])
        w.writerow(["토요일", 0, 0, 0, 0, 0, 1, 0])
        w.writerow(["휴일", 0, 0, 0, 0, 0, 0, 1])

    print(f"stops      {len(stops):6d}")
    print(f"trips      {len(trips):6d}")
    print(f"stop_times {len(stop_times):6d}")
    print(f"warnings   {len(warnings):6d}")
    for w_ in warnings[:20]:
        print("  -", w_)


if __name__ == "__main__":
    main()
