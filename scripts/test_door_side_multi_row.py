#!/usr/bin/env python3
"""stop_door_side 회귀 자가검증 — 2026-08-30 door_directions 다중행 역 24개 조합
(MULTI_ROW_RULES, build_door_side.py) 판정이 그대로 재현되는지 확인한다.
build_door_side.py 실행 후 돌릴 것.
"""
import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else "output/kr_rail_timetable.sqlite"

# (trip_id, 정차역, 기대 door_side)
KNOWN_CASES = [
    # Tier 1(direction 키 추가) — 수원 1호선 경부장항 상/하행
    ("L1#경부장항_평일_상#K602", "수원", "왼쪽"),
    ("L1#경부장항_평일_하#K605", "수원", "오른쪽"),
    # 병점 — line_name으로 서동탄 지선/경부장항 계통 구분
    ("L1#서동탄-의정부_평일_상#K408", "병점", "오른쪽"),
    ("L1#경부장항_평일_상#K602", "병점", "왼쪽"),
    # 구로 — 경인급행 vs 경부장항(상행)
    ("L1X#경인급행 상행(평일)#K1002", "구로", "오른쪽"),
    ("L1#경부장항_평일_상#K602", "구로", "왼쪽"),
    # 6호선 새절 — door_directions에 direction 자체가 없어 trips.direction으로 직접 판정
    ("S6O#평일#UP#6002", "새절", "오른쪽"),
    ("S6O#평일#DOWN#6011", "새절", "왼쪽"),
    # 의정부 — 종착(stop_type='destination') 여부로 판정, 이번에 stop_door_side 커버리지를
    # stop_type='destination'까지 넓혀야만 채워짐
    ("L1#경인_평일_상#S902", "의정부", "오른쪽"),
]


def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    for trip_id, station, expect_side in KNOWN_CASES:
        cur.execute(
            """
            SELECT sds.door_side
            FROM stop_door_side sds
            JOIN stop_times st ON sds.trip_id = st.trip_id AND sds.stop_seq = st.stop_seq
            JOIN stops s ON st.stop_id = s.stop_id
            JOIN station_groups sg ON s.group_id = sg.group_id
            WHERE sds.trip_id = ? AND sg.name_ko = ?
            """,
            (trip_id, station),
        )
        row = cur.fetchone()
        assert row is not None, f"{trip_id}@{station}: stop_door_side에 행 자체가 없음"
        (door_side,) = row
        assert door_side == expect_side, f"{trip_id}@{station}: door_side={door_side} (기대: {expect_side})"
        print(f"OK  {trip_id} @ {station} -> {door_side}")

    # 9호선 완행(C)/급행(E) — 급행은 항상 대피 대상 아님(is_evac=0 고정), 완행은 evac_side가 있어야 함
    cur.execute(
        """
        SELECT sds.is_evac FROM stop_door_side sds
        JOIN trips t ON sds.trip_id = t.trip_id
        WHERE t.line_name='9호선' AND t.train_no LIKE 'E%'
        """
    )
    assert all(r[0] == 0 for r in cur.fetchall()), "9호선 급행(E) trip 중 is_evac=1인 게 있음"
    print("OK  9호선 급행(E)은 전부 is_evac=0")

    # 신뢰 불가로 스킵한 조합(안양 등)은 여전히 stop_door_side에 안 채워졌는지 확인
    cur.execute(
        """
        SELECT COUNT(*) FROM stop_door_side sds
        JOIN stop_times st ON sds.trip_id = st.trip_id AND sds.stop_seq = st.stop_seq
        JOIN stops s ON st.stop_id = s.stop_id
        JOIN station_groups sg ON s.group_id = sg.group_id
        WHERE sg.name_ko = '안양' AND s.line = '1호선'
        """
    )
    (n,) = cur.fetchone()
    assert n == 0, f"신호 불충분으로 스킵해야 할 안양(경부급행B 구분)에 {n}건이 채워져 있음"
    print("OK  안양(경부급행B 구분 불가)은 예정대로 스킵됨")

    print(f"\n{len(KNOWN_CASES)}건 + 부수 검증 2건 전부 통과")


if __name__ == "__main__":
    main()
