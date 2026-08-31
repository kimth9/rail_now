#!/usr/bin/env python3
"""parse_ilban.py 회귀 자가검증 — 2026-08-30 rail.blue 실측 대조로 확정한
호남선 1491/1492(광주선/호남선 방향관례 충돌), 장항선/서해선 1241~1246
(서해선 관통 순환열차) 버그가 그대로 재현되지 않는지 확인한다.
build_db.py 실행 후 돌릴 것.
"""
import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else "output/kr_rail_timetable.sqlite"


def stop_row(cur, trip_id, station):
    cur.execute(
        """
        SELECT st.stop_seq, st.arr_sec, st.dep_sec, st.stop_type
        FROM stop_times st
        JOIN stops s ON st.stop_id = s.stop_id
        JOIN station_groups sg ON s.group_id = sg.group_id
        WHERE st.trip_id = ? AND sg.name_ko = ?
        """,
        (trip_id, station),
    )
    return cur.fetchone()


def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()

    # 버그① 극락강/광주 순서 (광주선/호남선 방향관례 충돌)
    seq, _, dep, stype = stop_row(cur, "IB#호남선#호남선 하행#1491", "광주")
    assert (seq, stype) == (1, "origin"), f"1491 광주: seq={seq} stype={stype} (기대: 1, origin)"
    seq, arr, dep, stype = stop_row(cur, "IB#호남선#호남선 하행#1491", "극락강")
    assert seq == 2, f"1491 극락강: seq={seq} (기대: 2)"
    print("OK  1491 하행: 광주(origin) -> 극락강 순서 정상")

    seq, arr, dep, stype = stop_row(cur, "IB#호남선#호남선 상행#1492", "광주")
    assert stype == "destination", f"1492 광주: stype={stype} (기대: destination)"
    seq2, _, _, stype2 = stop_row(cur, "IB#호남선#호남선 상행#1492", "극락강")
    assert stype2 == "stop" and seq2 == seq - 1, f"1492 극락강: seq={seq2} stype={stype2}"
    print("OK  1492 상행: 극락강(stop) -> 광주(destination) 순서 정상")

    # 버그②③ 서해선 관통 순환열차(1241~1246) — 장항선에서 빠지고 서해선에 온전히 존재
    cur.execute(
        "SELECT COUNT(*) FROM trips WHERE line_name='장항선(일반)' "
        "AND train_no IN ('1241','1242','1243','1244','1245','1246')"
    )
    (n,) = cur.fetchone()
    assert n == 0, f"장항선(일반)에 1241~1246이 아직 {n}건 남아있음"
    print("OK  장항선(일반): 1241~1246 전부 제외됨")

    for train_no in ("1241", "1242", "1243", "1244", "1245", "1246"):
        trip_id = f"IB#서해선#서해선 하행#{train_no}"
        origin = stop_row(cur, trip_id, "홍성(출발)")
        dest = stop_row(cur, trip_id, "홍성(도착)")
        assert origin is not None and origin[3] == "origin", f"{trip_id}: 홍성(출발) 행 없음/타입 이상"
        assert dest is not None and dest[3] == "destination", f"{trip_id}: 홍성(도착) 행 없음/타입 이상"
        assert dest[0] == 12, f"{trip_id}: 정차역 12개가 아님(마지막 seq={dest[0]})"
        print(f"OK  서해선 {train_no}: 홍성(출발)->...->홍성(도착) 12개 역 순환 정상")

    print("\n전부 통과")


if __name__ == "__main__":
    main()
