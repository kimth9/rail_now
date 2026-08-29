#!/usr/bin/env python3
"""서울교통공사 공식 CSV에서 2호선 지선(성수지선·신정지선)만 추출.

2호선 본선(순환선)은 기존 RAW 데이터를 그대로 쓰기로 했으므로, 이 CSV에서는
지선 6개 역(용답·신답·용두·도림천·양천구청·신정네거리) 중 하나라도 거치는
트립만 뽑는다 — 본선 순환 열차는 이 역들을 지나지 않으므로 자연히 걸러진다.
"""
import csv
import os
import re
import sys
from collections import OrderedDict, defaultdict

SRC = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else "tmp/out_seoul2_branch"

BRANCH_STATIONS = {"용답", "신답", "용두", "도림천", "양천구청", "신정네거리"}
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
    groups = defaultdict(list)
    with open(SRC, encoding="cp949") as f:
        for row in csv.DictReader(f):
            if row["호선"] != "2":
                continue
            key = (row["주중주말"], row["방향"], row["열차코드"])
            groups[key].append(row)

    branch_keys = {k for k, rows in groups.items()
                   if any(r["역사명"] in BRANCH_STATIONS for r in rows)}

    stops = OrderedDict()
    trips, stop_times, warnings = [], [], []
    for key in branch_keys:
        daytype, direction, train_no = key
        rows = [{"name": r["역사명"], "arr": to_sec(r["열차도착시간"]),
                 "dep": to_sec(r["열차출발시간"])} for r in groups[key]]
        rows.sort(key=lambda e: e["dep"] if e["dep"] is not None else e["arr"])
        if len(rows) < 2:
            warnings.append(f"{daytype}/{direction}/{train_no}: 정차 {len(rows)}개 — 제외")
            continue

        for e in rows:
            if e["name"] not in stops:
                stops[e["name"]] = f"S2BM{len(stops) + 1:04d}"

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
            "line_id": "SEOUL2_BRANCH", "line_name": "2호선",
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

    print(f"stops(지선+접속역) {len(stops):6d}")
    print(f"trips              {len(trips):6d}")
    print(f"stop_times         {len(stop_times):6d}")
    print(f"warnings           {len(warnings):6d}")
    for name in stops:
        print("  -", name)


if __name__ == "__main__":
    main()
