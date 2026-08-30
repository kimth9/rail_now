#!/usr/bin/env python3
"""stop_door_side 회귀 자가검증 — 이 세션에서 시각 단위로 직접 대조해 확정한 대피 사례가
build_door_side.py 계산 결과에 그대로 재현되는지 확인한다. build_door_side.py 실행 후 돌릴 것.
"""
import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else "output/kr_rail_timetable.sqlite"

# (trip_id, 정차역, 기대 door_side, 기대 overtaken_by_trip_id)
KNOWN_EVAC_CASES = [
    ("GJ#경의중앙선 하행#평일#K5021", "능곡", "오른쪽", "GJ#경의중앙선 하행#평일#K5701"),
    ("GC#경춘선 상행#평일#up#K8012", "청평", "오른쪽", "IC#ITX청춘 상행#평일#S2002"),
    ("AR#평일#0#A2015", "디지털미디어시티", "오른쪽", "AR#평일#0#A1003"),
]


def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    for trip_id, station, expect_side, expect_by in KNOWN_EVAC_CASES:
        cur.execute(
            """
            SELECT sds.door_side, sds.is_evac, sds.overtaken_by_trip_id
            FROM stop_door_side sds
            JOIN stop_times st ON sds.trip_id = st.trip_id AND sds.stop_seq = st.stop_seq
            JOIN stops s ON st.stop_id = s.stop_id
            WHERE sds.trip_id = ? AND s.name_ko = ?
            """,
            (trip_id, station),
        )
        row = cur.fetchone()
        assert row is not None, f"{trip_id}@{station}: stop_door_side에 행 자체가 없음"
        door_side, is_evac, overtaken_by = row
        assert is_evac == 1, f"{trip_id}@{station}: is_evac={is_evac} (기대: 1)"
        assert door_side == expect_side, f"{trip_id}@{station}: door_side={door_side} (기대: {expect_side})"
        assert overtaken_by == expect_by, f"{trip_id}@{station}: overtaken_by={overtaken_by} (기대: {expect_by})"
        print(f"OK  {trip_id} @ {station} -> {door_side} (by {overtaken_by})")

    print(f"\n{len(KNOWN_EVAC_CASES)}건 전부 통과")


if __name__ == "__main__":
    main()
