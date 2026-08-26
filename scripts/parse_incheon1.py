#!/usr/bin/env python3
"""인천 도시철도 1호선(인천교통공사, 비코레일) 시각표 xls -> 정규화 테이블

`.xls`(구버전 바이너리) 포맷이라 openpyxl이 못 열어서 xlrd로 읽는다(프로젝트
최초로 xlrd 의존성 추가 — 요구사항 필요 시 requirements에 반영).

구조는 KTX와 같은 "열차=행/역=열, 역당 시각 1개"(도착/출발 구분 없음). 시트 =
평일_상선/평일_하선/토휴일_상선/토휴일_하선 — **토요일과 휴일을 하나로 묶은
다이어**(대구·부산과 달리 별도 토요일 다이어가 없음, 확인됨). 시각은
"HH:MM" 텍스트(초 단위 없음).
"""
import csv
import os
import re
import sys
from collections import OrderedDict
import xlrd

SRC = sys.argv[1] if len(sys.argv) > 1 else "RAW/인천1호선 열차운행 시간표.xls"
OUT = sys.argv[2] if len(sys.argv) > 2 else "tmp/out_incheon1"

SHEETS = {
    "평일_상선": ("평일", "down"), "평일_하선": ("평일", "up"),
    "토휴일_상선": ("휴일", "down"), "토휴일_하선": ("휴일", "up"),
}

TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")


def clean(v):
    return str(v).strip() if v not in (None, "") else ""


def to_sec(v):
    if not isinstance(v, str):
        return None
    m = TIME_RE.match(v.strip())
    if not m:
        return None
    h, mi, s = m.group(1), m.group(2), m.group(3)
    return int(h) * 3600 + int(mi) * 60 + (int(s) if s else 0)


def main():
    wb = xlrd.open_workbook(SRC)

    stops = OrderedDict()
    trips, stop_times = [], []
    warnings = []

    for sheet, (daytype, direction) in SHEETS.items():
        ws = wb.sheet_by_name(sheet)
        stations = [clean(ws.cell_value(0, c)) for c in range(1, ws.ncols)]
        for name in stations:
            if name not in stops:
                stops[name] = f"IC1{len(stops) + 1:04d}"

        for r in range(1, ws.nrows):
            train_no = clean(ws.cell_value(r, 0))
            if not train_no:
                continue
            if isinstance(ws.cell_value(r, 0), float):
                train_no = str(int(ws.cell_value(r, 0)))

            raw = []
            for i, name in enumerate(stations):
                sec = to_sec(ws.cell_value(r, i + 1))
                if sec is not None:
                    raw.append([name, sec])
            if len(raw) < 2:
                if raw:
                    warnings.append(f"[{sheet}] {train_no}: 유효 정차 {len(raw)}개 — 제외")
                continue

            rolled, prev = 0, -1
            for row in raw:
                adj = row[1] + rolled * 86400
                if prev >= 0 and adj < prev:
                    rolled += 1
                    adj = row[1] + rolled * 86400
                if prev >= 0 and adj < prev:
                    warnings.append(f"[{sheet}] {train_no}: {row[0]} 시각 역행")
                row[1] = adj
                prev = adj

            trip_id = f"{sheet}#{train_no}"
            for seq, (name, sec) in enumerate(raw, start=1):
                stop_times.append({
                    "trip_id": trip_id, "stop_seq": seq,
                    "stop_id": stops[name], "dep_sec": sec,
                })
            trips.append({
                "trip_id": trip_id, "train_no": train_no,
                "line_id": "INCHEON1", "line_name": "인천1호선",
                "formation": "전동차", "direction": direction,
                "service_id": daytype,
                "origin": stops[raw[0][0]],
                "destination": stops[raw[-1][0]],
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
        w = csv.DictWriter(f, fieldnames=["trip_id", "stop_seq", "stop_id", "dep_sec"])
        w.writeheader()
        w.writerows(stop_times)

    with open(f"{OUT}/calendar.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["service_id", "mon", "tue", "wed", "thu", "fri", "sat", "sun"])
        w.writerow(["평일", 1, 1, 1, 1, 1, 0, 0])
        w.writerow(["휴일", 0, 0, 0, 0, 0, 1, 1])

    print(f"stops      {len(stops):6d}")
    print(f"trips      {len(trips):6d}")
    print(f"stop_times {len(stop_times):6d}")
    print(f"warnings   {len(warnings):6d}")
    for w_ in warnings[:20]:
        print("  -", w_)


if __name__ == "__main__":
    main()
