#!/usr/bin/env python3
"""인천 도시철도 2호선(인천교통공사) 시각표 -> 정규화 테이블 (추정치 기반)

공식 사이트(ictr.or.kr)가 인천1호선과 달리 2호선은 **분 단위 상세 시각표를
공개하지 않는다** — 공개된 건 (1) 시간대별 배차간격(운행시격) 표와
(2) 역별 첫차/막차 시각뿐이다(`RAW/web_크롤링/인천2호선/timetable2.jsp.html`,
`timetable2_se.jsp.html`, 둘 다 정적 HTML이라 curl로 확보). 그래서 이
노선은 실제 관측 시각표가 아니라 **배차간격으로 근사 생성한 간이
시각표**다 — `scripts/_headway_estimate.py` 공유 헬퍼로 기준역(그 방면의
시발역) 첫차~막차를 배차간격으로 채운 뒤, 나머지 역은 막차 기준 오프셋
(막차는 실제로 항상 완주하는 열차라 신뢰 가능 — 반대로 첫차는 중간
시발역 존재로 신뢰 불가, 아래 참조)으로 평행이동한다.

**중간 시발역(단축운행) 주의**: 역별 첫차 시각을 보면 인천시청·주안·
서부여성회관·검암 등 여러 역에서 첫차가 이전 역보다 오히려 이르다(예:
석천사거리 05:41 다음 인천시청이 05:30) — 이 역들이 실제로는 노선
중간의 별도 시발역(단축 운행 열차의 출발점)이라는 뜻이다. 이 근사
로직은 이런 중간 시발역의 "첫차 시각 하나"만 반영하고 그 역 자체의
나머지 배차(단축 운행 열차들)는 복원하지 못한다 — 추정치의 근본적
한계로 README에 명시한다.

배차간격이 범위로 공개된 밴드(예: "3~13분")는 평균값으로 단일화했다.
"""
import csv
import os
import sys
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(__file__))
from _headway_estimate import generate_schedule, hm_to_min, parse_hm, shift_schedule

OUT = sys.argv[1] if len(sys.argv) > 1 else "tmp/out_incheon2"

# (역명, WD_첫차, WD_막차, HD_첫차, HD_막차) — 방면별 시발역(운연/검단오류)부터 순서대로
UP_ROWS = [  # 검단오류 방면(상선), 시발역=운연
    ("운연", "05:30", "24:12", "05:30", "24:12"),
    ("인천대공원", "05:32", "24:14", "05:32", "24:14"),
    ("남동구청", "05:34", "24:17", "05:34", "24:17"),
    ("만수", "05:37", "24:19", "05:37", "24:19"),
    ("모래내시장", "05:39", "24:21", "05:39", "24:21"),
    ("석천사거리", "05:41", "24:23", "05:41", "24:23"),
    ("인천시청", "05:30", "24:25", "05:30", "24:25"),
    ("석바위시장", "05:31", "24:26", "05:31", "24:26"),
    ("시민공원", "05:33", "24:28", "05:33", "24:28"),
    ("주안", "05:30", "24:31", "05:36", "24:31"),
    ("주안국가산단", "05:31", "24:32", "05:37", "24:32"),
    ("가재울", "05:33", "24:34", "05:39", "24:34"),
    ("인천가좌", "05:36", "24:37", "05:42", "24:37"),
    ("서부여성회관", "05:30", "24:39", "05:30", "24:39"),
    ("석남", "05:31", "24:40", "05:31", "24:40"),
    ("가정중앙시장", "05:33", "24:42", "05:33", "24:42"),
    ("가정", "05:35", "24:44", "05:35", "24:44"),
    ("서해구청", "05:38", "24:47", "05:38", "24:47"),
    ("아시아드경기장", "05:39", "24:48", "05:39", "24:48"),
    ("검바위", "05:41", "24:50", "05:41", "24:50"),
    ("검암", "05:30", "24:52", "05:30", "24:52"),
    ("독정", "05:33", "24:55", "05:33", "24:55"),
    ("완정", "05:34", "24:57", "05:34", "24:57"),
    ("마전", "05:36", "24:59", "05:36", "24:59"),
    ("검단사거리", "05:38", "25:01", "05:38", "25:01"),
    ("왕길", "05:40", "25:03", "05:40", "25:03"),
    ("검단오류", "05:43", "25:05", "05:43", "25:05"),
]

DOWN_ROWS = [  # 운연 방면(하선), 시발역=검단오류
    ("검단오류", "05:30", "24:12", "05:30", "24:12"),
    ("왕길", "05:32", "24:14", "05:32", "24:14"),
    ("검단사거리", "05:34", "24:17", "05:34", "24:17"),
    ("마전", "05:36", "24:19", "05:36", "24:19"),
    ("완정", "05:38", "24:21", "05:38", "24:21"),
    ("독정", "05:40", "24:22", "05:40", "24:22"),
    ("검암", "05:30", "24:25", "05:30", "24:25"),
    ("검바위", "05:31", "24:27", "05:31", "24:27"),
    ("아시아드경기장", "05:34", "24:29", "05:34", "24:29"),
    ("서해구청", "05:30", "24:31", "05:35", "24:31"),
    ("가정", "05:32", "24:34", "05:38", "24:34"),
    ("가정중앙시장", "05:34", "24:36", "05:40", "24:36"),
    ("석남", "05:36", "24:38", "05:42", "24:38"),
    ("서부여성회관", "05:30", "24:39", "05:30", "24:39"),
    ("인천가좌", "05:31", "24:41", "05:31", "24:41"),
    ("가재울", "05:34", "24:44", "05:34", "24:44"),
    ("주안국가산단", "05:36", "24:46", "05:36", "24:46"),
    ("주안", "05:38", "24:48", "05:38", "24:48"),
    ("시민공원", "05:40", "24:50", "05:40", "24:50"),
    ("석바위시장", "05:42", "24:52", "05:42", "24:52"),
    ("인천시청", "05:30", "24:53", "05:30", "24:53"),
    ("석천사거리", "05:31", "24:55", "05:31", "24:55"),
    ("모래내시장", "05:33", "24:57", "05:33", "24:57"),
    ("만수", "05:35", "24:58", "05:35", "24:58"),
    ("남동구청", "05:37", "25:01", "05:37", "25:01"),
    ("인천대공원", "05:40", "25:03", "05:40", "25:03"),
    ("운연", "05:42", "25:05", "05:42", "25:05"),
]

# 시간대별 배차간격(분) — 범위 공개 구간은 평균값으로 단일화. 상행/하행 값이
# 다른 구간(07:46~08:16)만 방향별로 분리
BANDS_WD_COMMON = [(hm_to_min(5, 30), 8), (hm_to_min(6, 30), 3), (hm_to_min(8, 16), 3),
                    (hm_to_min(9, 45), 6.2), (hm_to_min(16, 10), 4.7), (hm_to_min(17, 35), 3.6),
                    (hm_to_min(20, 10), 6.2), (hm_to_min(23, 4), 9)]
BANDS_WD_UP = sorted(BANDS_WD_COMMON + [(hm_to_min(7, 46), 3)])
BANDS_WD_DOWN = sorted(BANDS_WD_COMMON + [(hm_to_min(7, 46), 2.5)])
BANDS_HD = [(hm_to_min(5, 30), 10), (hm_to_min(7, 0), 5.5), (hm_to_min(22, 0), 8.5)]


def build_direction(rows, bands_wd, bands_hd, direction, terminus_name):
    origin_name = rows[0][0]
    origin_wd_first, origin_wd_last = parse_hm(rows[0][1]), parse_hm(rows[0][2])
    origin_hd_first, origin_hd_last = parse_hm(rows[0][3]), parse_hm(rows[0][4])

    origin_wd = generate_schedule(origin_wd_first, origin_wd_last, bands_wd)
    origin_hd = generate_schedule(origin_hd_first, origin_hd_last, bands_hd)

    per_station = OrderedDict()
    for name, wd_f, wd_l, hd_f, hd_l in rows:
        wd_first, wd_last = parse_hm(wd_f), parse_hm(wd_l)
        hd_first, hd_last = parse_hm(hd_f), parse_hm(hd_l)
        wd_offset = wd_last - origin_wd_last
        hd_offset = hd_last - origin_hd_last
        wd_sched = shift_schedule(origin_wd, wd_offset, wd_last, real_first_min=wd_first)
        hd_sched = shift_schedule(origin_hd, hd_offset, hd_last, real_first_min=hd_first)
        per_station[name] = {"평일": wd_sched, "휴일": hd_sched}
    return per_station


def main():
    up_names = [r[0] for r in UP_ROWS]
    down_names = [r[0] for r in DOWN_ROWS]
    stops = OrderedDict()
    for name in up_names:
        if name not in stops:
            stops[name] = f"IC2{len(stops) + 1:04d}"

    up_data = build_direction(UP_ROWS, BANDS_WD_UP, BANDS_HD, "up", "검단오류")
    down_data = build_direction(DOWN_ROWS, BANDS_WD_DOWN, BANDS_HD, "down", "운연")

    trips, stop_times = [], []

    def emit(direction, names, data, daykey):
        for ci in range(len(data[names[0]][daykey])):
            trip_id = f"{direction}#{daykey}#{ci}"
            seq = 0
            last_t = None
            for name in names:
                sched = data[name][daykey]
                if ci >= len(sched):
                    continue
                # 중간 시발역(단축운행) 첫차 스냅이 이전 역보다 앞서는 경우가
                # 있어(그 역의 별도 열차라 실제로는 다른 물리적 열차) 한 trip
                # 안에서는 단조증가를 강제한다(추정치 근사, 캐비어트 참조)
                t = sched[ci] if last_t is None else max(sched[ci], last_t)
                last_t = t
                seq += 1
                stop_times.append({"trip_id": trip_id, "stop_seq": seq,
                                    "stop_id": stops[name], "dep_sec": t * 60})
            if seq == 0:
                continue
            trips.append({"trip_id": trip_id, "train_no": trip_id,
                           "line_id": "INCHEON2", "line_name": "인천2호선(추정)",
                           "formation": "도시철도", "direction": direction,
                           "service_id": daykey,
                           "origin": stops[names[0]], "destination": stops[names[-1]],
                           "next_train_no": ""})

    for daykey in ["평일", "휴일"]:
        emit("up", up_names, up_data, daykey)
        emit("down", down_names, down_data, daykey)

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

    print(f"stops {len(stops)} / trips {len(trips)} / stop_times {len(stop_times)}")


if __name__ == "__main__":
    main()
