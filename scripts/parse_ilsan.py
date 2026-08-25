#!/usr/bin/env python3
"""일산선(서울 지하철 3호선 중 코레일 구간 포함 오금~대화 전 구간 직결) 시각표 xlsx
-> 정규화 테이블 (parse_ansan_gwacheon.py와 같은 패턴 — 코레일이 직결 전체 노선을 배포)

입력 구조 (관측):
  - 시트 = 일산(3호)선 평일_상행 / 평일_하행 / 휴일_상행 / 휴일_하행
  - 헤더는 다른 노선과 동일(3행: 시발역/종착역/열차번호, 4행부터 역). '연계열번' 없음.
  - 오금~대화 전 44개 역(서울교통공사 구간 포함)이 한 파일에 다 들어있다 — 안산과천선과
    같은 패턴(직결운행 전체 시각표를 코레일이 배포).
  - `3`으로 시작/끝나는 라벨(3수서·3도곡·3옥수·3충무·3을지·3종로·3대곡·금호3)은 절삭이
    아니라 **다른 노선에 같은 이름의 역이 있어 붙는 3호선 구분 표기**다(안산과천선의
    `4`접두사와 같은 부류). 예: `3수서`=수서(수인분당선·국철과 동명), `3충무`=충무로
    (안산과천선의 `4충무`와 짝을 이루는 4호선측 충무로와 환승). 나무위키 "서울 지하철
    3호선/역 목록" 문서로 전수 대조 완료, 미확인 없음.
"""
import csv
import datetime
import os
import sys
from collections import OrderedDict
from openpyxl import load_workbook

SRC = sys.argv[1] if len(sys.argv) > 1 else "RAW/korail_시각표_20260825/일산선_20220801부터.xlsx"
OUT = sys.argv[2] if len(sys.argv) > 2 else "tmp/out_ilsan"

SHEETS = {
    "일산(3호)선 평일_상행": ("평일", "up"), "일산(3호)선 평일_하행": ("평일", "down"),
    "일산(3호)선 휴일_상행": ("휴일", "up"), "일산(3호)선 휴일_하행": ("휴일", "down"),
}

NOT_A_STATION = set()
JUNCTIONS = {}

STATION_ALIAS = {
    "경찰병": ("경찰병원", "✔"),
    "가락시": ("가락시장", "✔"),
    "3수서": ("수서", "✔"),         # 3호선 구분 표기(수인분당선·국철 수서와 동명)
    "3도곡": ("도곡", "✔"),         # 3호선 구분 표기(수인분당선 도곡과 동명)
    "남부터": ("남부터미널", "✔"),
    "고속터": ("고속터미널", "✔"),
    "3옥수": ("옥수", "✔"),         # 3호선 구분 표기(경의중앙선 옥수와 동명)
    "금호3": ("금호", "✔"),
    "동대입": ("동대입구", "✔"),     # 정식 역명 자체가 '동대입구'(동대문입구 아님)
    "3충무": ("충무로", "✔"),       # 3호선 구분 표기(안산과천선 4충무=충무로와 환승)
    "3을지": ("을지로3가", "✔"),
    "3종로": ("종로3가", "✔"),      # 3호선 구분 표기(1호선 종로3가와 동명)
    "3대곡": ("대곡", "✔"),         # 3호선 구분 표기(경의중앙선·경의선 대곡과 동명)
}

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def is_time(v):
    return isinstance(v, (datetime.time, datetime.datetime))


def to_sec(v):
    if not is_time(v):
        return None
    return v.hour * 3600 + v.minute * 60 + v.second


def clean(v):
    return str(v).strip() if v is not None else ""


def resolve(label):
    if label in STATION_ALIAS:
        return STATION_ALIAS[label]
    return (label, "✔")


def main():
    wb = load_workbook(SRC, data_only=True)

    stops, stop_verify = OrderedDict(), {}
    trips, stop_times = [], []
    warnings = []

    for sheet, (daytype, direction) in SHEETS.items():
        ws = wb[sheet]

        header_row = next(r for r in range(1, 6) if clean(ws.cell(r, 1).value) == "열차번호")

        st_rows = []
        for r in range(header_row + 1, ws.max_row + 1):
            label = clean(ws.cell(r, 1).value)
            if not label or label in NOT_A_STATION:
                continue
            if label in JUNCTIONS:
                st_rows.append((r, "@" + JUNCTIONS[label]))
                continue
            name, vf = resolve(label)
            if name not in stops:
                stops[name] = f"SB{len(stops) + 1:04d}"
                stop_verify[name] = (label, vf)
            st_rows.append((r, name))

        for c in range(2, ws.max_column + 1):
            train_no = clean(ws.cell(header_row, c).value)
            if not train_no:
                continue

            raw = []
            for r, name in st_rows:
                a = to_sec(ws.cell(r, c).value)
                d = to_sec(ws.cell(r + 1, c).value)
                if a is None and d is None:
                    continue
                raw.append([name, a, d])
            if len(raw) < 2:
                warnings.append(f"[{sheet}] {train_no}: 유효 정차 {len(raw)}개 — 제외")
                continue

            rolled, prev = 0, -1
            for row in raw:
                for i in (1, 2):
                    if row[i] is None:
                        continue
                    adj = row[i] + rolled * 86400
                    if prev >= 0 and adj < prev:
                        rolled += 1
                        adj = row[i] + rolled * 86400
                    if prev >= 0 and adj < prev:
                        warnings.append(f"[{sheet}] {train_no}: {row[0]} 시각 역행")
                    row[i] = adj
                    prev = adj

            trip_id = f"{sheet}#{train_no}"
            for seq, (name, a, d) in enumerate(raw, start=1):
                if seq == 1:
                    kind = "origin"
                elif seq == len(raw):
                    kind = "destination"
                elif a is not None and d is not None:
                    kind = "stop"
                elif name.startswith("@"):
                    kind = "junction"
                else:
                    kind = "pass"
                stop_times.append({
                    "trip_id": trip_id, "stop_seq": seq,
                    "stop_id": name if name.startswith("@") else stops[name],
                    "arr_sec": a if a is not None else "",
                    "dep_sec": d if d is not None else "",
                    "stop_type": kind,
                })

            trips.append({
                "trip_id": trip_id, "train_no": train_no,
                "line_id": "IS", "line_name": "일산선",
                "formation": "전동차", "direction": direction,
                "service_id": daytype,
                "origin": stops.get(raw[0][0], raw[0][0]),
                "destination": stops.get(raw[-1][0], raw[-1][0]),
                "next_train_no": "",
            })

    os.makedirs(OUT, exist_ok=True)

    with open(f"{OUT}/stops.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["stop_id", "name_ko", "raw_label", "verify"])
        for name, sid in stops.items():
            w.writerow([sid, name, stop_verify[name][0], stop_verify[name][1]])

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
        w.writerow(["service_id"] + DAYS)
        w.writerow(["평일", 1, 1, 1, 1, 1, 0, 0])
        w.writerow(["휴일", 0, 0, 0, 0, 0, 1, 1])

    from collections import Counter
    kinds = Counter(s["stop_type"] for s in stop_times)
    print(f"stops      {len(stops):6d}")
    print(f"trips      {len(trips):6d}")
    print(f"stop_times {len(stop_times):6d}  {dict(kinds)}")
    print(f"warnings   {len(warnings):6d}")
    for w_ in warnings[:20]:
        print("  -", w_)


if __name__ == "__main__":
    main()
