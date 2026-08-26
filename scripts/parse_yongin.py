#!/usr/bin/env python3
"""용인경전철(용인에버라인㈜) 시각표 -> 정규화 테이블 (추정치 기반)

공식 사이트(ever-line.co.kr, `/page/?M2_IDX=28909`)도 인천2호선과 같은
부류 — **분 단위 상세 시각표를 공개하지 않는다.** 공개된 건 (1) 시간대별
배차간격표(평일/토·일요일·공휴일 2종)와 (2) 역별 첫차/막차뿐인데, 첫차/
막차는 (인천2호선과 달리) 요일 구분 없이 값이 하나씩만 있다 —
`RAW/web_크롤링/용인경전철/M2_IDX_28909.html`(정적 HTML, curl로 확보).
`scripts/_headway_estimate.py` 공유 헬퍼로 배차간격 기반 근사 시각표를
생성한다(방법론은 `parse_incheon2.py`와 동일 — 막차 기준 오프셋으로
평행이동, 첫차만 그 역의 실제 값으로 스냅, 트립 내 단조증가 강제).

중간 시발역(단축운행) 패턴이 이 노선에도 있다(예: 용인중앙시장·초당의
첫차가 바로 이전 역보다 이르다) — 인천2호선과 같은 한계이자 같은
보정 방식으로 처리했다.
"""
import csv
import os
import sys
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(__file__))
from _headway_estimate import generate_schedule, hm_to_min, parse_hm, shift_schedule

OUT = sys.argv[1] if len(sys.argv) > 1 else "tmp/out_yongin"

# (역명, 기흥행_첫차, 기흥행_막차, 전대행_첫차, 전대행_막차) — 사이트 표시 순서
# (기흥 -> 전대·에버랜드) 그대로. 요일 구분 없이 값이 하나씩만 공개됨
ROWS = [
    ("기흥", None, None, "05:30", "23:30"),
    ("강남대", "05:37", "23:57", "05:31", "23:31"),
    ("지석", "05:35", "23:55", "05:33", "23:33"),
    ("어정", "05:34", "23:53", "05:35", "23:35"),
    ("동백", "05:32", "23:51", "05:37", "23:37"),
    ("초당", "05:30", "23:49", "05:30", "23:39"),
    ("삼가", "05:36", "23:45", "05:33", "23:42"),
    ("시청·용인대", "05:35", "23:44", "05:35", "23:44"),
    ("명지대", "05:33", "23:42", "05:36", "23:46"),
    ("김량장", "05:31", "23:40", "05:38", "23:47"),
    ("용인중앙시장", "05:30", "23:39", "05:30", "23:49"),
    ("고진", "05:37", "23:37", "05:31", "23:51"),
    ("보평", "05:35", "23:35", "05:34", "23:53"),
    ("둔전", "05:33", "23:33", "05:35", "23:55"),
    ("전대·에버랜드", "05:30", "23:30", None, None),
]

# 시간대별 배차간격(분) — 평일/토·일요일·공휴일 2종, 방향 구분 없음
BANDS_WD = [(hm_to_min(5, 30), 10), (hm_to_min(7, 0), 3), (hm_to_min(9, 0), 6),
            (hm_to_min(17, 0), 4), (hm_to_min(20, 0), 6), (hm_to_min(21, 0), 6),
            (hm_to_min(22, 0), 10), (hm_to_min(23, 30), 30)]
BANDS_HD = [(hm_to_min(5, 30), 10), (hm_to_min(7, 0), 6), (hm_to_min(9, 0), 6),
            (hm_to_min(17, 0), 6), (hm_to_min(20, 0), 6), (hm_to_min(21, 0), 10),
            (hm_to_min(22, 0), 10), (hm_to_min(23, 30), 30)]
BANDS = {"평일": BANDS_WD, "휴일": BANDS_HD}

# 부산2호선에도 동명역 '동백'(기장군)이 있어 무관한 역이라 merge_key로 분리.
# 기흥은 수인분당선과 실제 환승역이라 이름 그대로 자동 병합
MERGE_KEY = {"동백": "용인동백"}


def build_direction(names, firsts, lasts, bands):
    """names/firsts/lasts: 시발역부터 순서대로. firsts[0]/lasts[0]가 기준."""
    origin_first, origin_last = firsts[0], lasts[0]
    origin_sched = generate_schedule(origin_first, origin_last, bands)
    per_station = OrderedDict()
    for name, first, last in zip(names, firsts, lasts):
        offset = last - origin_last
        per_station[name] = shift_schedule(origin_sched, offset, last, real_first_min=first)
    return per_station


def main():
    all_names = [r[0] for r in ROWS]
    stops = OrderedDict((name, f"YI{i + 1:04d}") for i, name in enumerate(all_names))

    up_rows = [r for r in reversed(ROWS) if r[1] is not None]  # 전대->강남대 (기흥 자체는 제외)
    down_rows = [r for r in ROWS if r[3] is not None]  # 기흥->둔전 (전대·에버랜드 자체는 제외)
    ESTIMATED_LAST_HOP_MIN = 2
    TERMINUS = {"up": "기흥", "down": "전대·에버랜드"}

    trips, stop_times = [], []

    def emit(direction, rows, daykey):
        names = [r[0] for r in rows]
        idx = 1 if direction == "up" else 3
        firsts = [parse_hm(r[idx]) for r in rows]
        lasts = [parse_hm(r[idx + 1]) for r in rows]
        data = build_direction(names, firsts, lasts, BANDS[daykey])
        n = len(data[names[0]])
        terminus = TERMINUS[direction]
        for ci in range(n):
            trip_id = f"{direction}#{daykey}#{ci}"
            seq, last_t = 0, None
            for name in names:
                sched = data[name]
                if ci >= len(sched):
                    continue
                t = sched[ci] if last_t is None else max(sched[ci], last_t)
                last_t = t
                seq += 1
                stop_times.append({"trip_id": trip_id, "stop_seq": seq,
                                    "stop_id": stops[name], "dep_sec": t * 60})
            if seq == 0:
                continue
            seq += 1
            stop_times.append({"trip_id": trip_id, "stop_seq": seq,
                                "stop_id": stops[terminus],
                                "dep_sec": (last_t + ESTIMATED_LAST_HOP_MIN) * 60})
            trips.append({"trip_id": trip_id, "train_no": trip_id,
                           "line_id": "YONGIN", "line_name": "용인경전철(추정)",
                           "formation": "경전철", "direction": direction,
                           "service_id": daykey,
                           "origin": stops[names[0]], "destination": stops[terminus],
                           "next_train_no": ""})

    for daykey in ["평일", "휴일"]:
        emit("up", up_rows, daykey)
        emit("down", down_rows, daykey)

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

    print(f"stops {len(stops)} / trips {len(trips)} / stop_times {len(stop_times)}")


if __name__ == "__main__":
    main()
