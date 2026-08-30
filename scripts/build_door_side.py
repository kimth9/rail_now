#!/usr/bin/env python3
"""stop_times의 각 정차(trip_id, stop_seq)마다 실제로 어느 쪽 문이 열리는지
stop_door_side 테이블로 계산해 얹는다. door_directions 다음 단계(3번째 레이어).

판정 방식(Tier A만 자동 계산):
  같은 물리역(group_id)에서, 이 열차를 추월할 수 있다고 확인된 노선(EVAC_SOURCE_LINES)의
  다른 열차가 stop_type='pass'로 통과하는 시각이 이 열차의 정차 시간(arr_sec~dep_sec) 안에
  들어오면 대피(evac_side) 상황으로 본다. 그 외(door_directions에 evac_side가 없거나,
  추월 열차가 애초에 통과역 기록을 안 남기는 노선 — KTX/무궁화/ITX-마음 등 Tier B)는
  평시(normal_side)로 고정한다.

door_directions에서 같은 (line_sheet, group_id)에 행이 2개 이상인 역(노선 분기·환승으로
방면별 문방향이 갈리는 경우, 약 40개 조합)은 이번 단계에서 제외한다 — 잘못된 문방향을
확정하는 것보다 안 채우는 게 안전하다(후속 과제, todo.md 참조).
"""
import os
import sqlite3
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_door_directions import SHEET_LINE_ALIASES  # noqa: E402

DB = sys.argv[1] if len(sys.argv) > 1 else "output/kr_rail_timetable.sqlite"

# 이번 세션에서 실제로 "완행 정차창 안에 다른 열차의 pass 통과시각이 들어오는지" 초 단위로
# 검증된 조합만 등록한다. 값은 이 line_name의 열차가 추월당할 수 있는 상대 line_name 목록.
# (자기 노선 자체 급행이 있으면 자기 자신도 포함)
EVAC_SOURCE_LINES = {
    "경의중앙선": ["경의중앙선"],
    "경춘선": ["경춘선", "ITX-청춘"],
    "공항철도": ["공항철도"],
    "수인분당선": ["수인분당선"],
    "안산과천선": ["안산과천선"],
}
# 1호선은 trips.line_name이 '1호선/경부장항' 등으로 세분화돼 있어 접두사로 묶는다.
LINE1_PREFIX = "1호선/"


def evac_source_lines_for(line_name):
    if line_name in EVAC_SOURCE_LINES:
        return EVAC_SOURCE_LINES[line_name]
    if line_name.startswith(LINE1_PREFIX):
        return None  # 호출부에서 접두사로 별도 처리
    return None


SCHEMA = """
DROP TABLE IF EXISTS stop_door_side;
CREATE TABLE stop_door_side(
    trip_id TEXT, stop_seq INTEGER,
    door_side TEXT, is_evac INTEGER, overtaken_by_trip_id TEXT,
    PRIMARY KEY(trip_id, stop_seq)
);
"""


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.executescript(SCHEMA)

    # 1) line -> sheet 역매핑 (build_door_directions.py와 동일 규칙)
    line_to_sheet = {}
    cur.execute("SELECT DISTINCT line FROM stops")
    all_lines = [r[0] for r in cur.fetchall()]
    for line in all_lines:
        sheet = line
        for s, aliases in SHEET_LINE_ALIASES.items():
            if line in aliases:
                sheet = s
                break
        line_to_sheet[line] = sheet

    # 2) door_directions: (line_sheet, group_id) 단일행만 채택
    cur.execute("""
    SELECT line_sheet, group_id, normal_side, evac_side
    FROM door_directions
    GROUP BY line_sheet, group_id
    HAVING COUNT(*) = 1
    """)
    single_door = {(r["line_sheet"], r["group_id"]): (r["normal_side"], r["evac_side"]) for r in cur.fetchall()}

    # 3) stop_id -> (group_id, resolved sheet, door row) — door 정보가 있는 stop_id만
    cur.execute("SELECT stop_id, line, group_id FROM stops")
    door_stop = {}
    for r in cur.fetchall():
        sheet = line_to_sheet.get(r["line"], r["line"])
        key = (sheet, r["group_id"])
        if key in single_door:
            door_stop[r["stop_id"]] = (r["group_id"], single_door[key])

    # 3-1) 1호선은 stops.line='1호선' 한 값이지만 trips.line_name은 '1호선/경부장항' 등으로
    # 세분화돼 있어 별도로 모은다.
    cur.execute("SELECT DISTINCT line_name FROM trips WHERE line_name LIKE ?", (LINE1_PREFIX + "%",))
    line1_variants = [r[0] for r in cur.fetchall()]

    # 4) Tier A 통과(pass) 이벤트: group_id, service_id별로 모아 dict[(group_id, service_id)] = [(pass_time, trip_id, line_name)]
    cur.execute("""
    SELECT s.group_id AS group_id, t.service_id AS service_id, t.line_name AS line_name,
           st.trip_id AS trip_id, COALESCE(st.dep_sec, st.arr_sec) AS pass_time
    FROM stop_times st
    JOIN stops s ON st.stop_id = s.stop_id
    JOIN trips t ON st.trip_id = t.trip_id
    WHERE st.stop_type = 'pass'
    """)
    pass_events = defaultdict(list)
    for r in cur.fetchall():
        pass_events[(r["group_id"], r["service_id"])].append((r["pass_time"], r["trip_id"], r["line_name"]))

    # 5) 대상 정차(stop_type='stop', door 정보 있는 stop_id)만 훑는다
    cur.execute("""
    SELECT st.trip_id AS trip_id, st.stop_seq AS stop_seq, st.stop_id AS stop_id,
           st.arr_sec AS arr_sec, st.dep_sec AS dep_sec,
           t.line_name AS line_name, t.service_id AS service_id
    FROM stop_times st
    JOIN trips t ON st.trip_id = t.trip_id
    WHERE st.stop_type = 'stop'
    """)

    rows_out = []
    n_evac = 0
    for r in cur.fetchall():
        info = door_stop.get(r["stop_id"])
        if info is None:
            continue
        group_id, (normal_side, evac_side) = info
        if r["arr_sec"] is None or r["dep_sec"] is None:
            continue

        door_side, is_evac, overtaken_by = normal_side, 0, None
        if evac_side:
            src_lines = evac_source_lines_for(r["line_name"])
            if src_lines is None and r["line_name"].startswith(LINE1_PREFIX):
                src_lines = line1_variants
            if src_lines:
                for pass_time, other_trip, other_line in pass_events.get((group_id, r["service_id"]), ()):
                    if other_trip == r["trip_id"]:
                        continue
                    if other_line not in src_lines:
                        continue
                    if r["arr_sec"] <= pass_time <= r["dep_sec"]:
                        door_side, is_evac, overtaken_by = evac_side, 1, other_trip
                        n_evac += 1
                        break

        rows_out.append((r["trip_id"], r["stop_seq"], door_side, is_evac, overtaken_by))

    cur.executemany(
        "INSERT INTO stop_door_side VALUES(?,?,?,?,?)", rows_out
    )
    con.commit()

    print(f"stop_door_side {len(rows_out)}행 생성, 그 중 대피(is_evac=1) {n_evac}행")
    cur.execute("""
    SELECT t.line_name, COUNT(*) c, SUM(sds.is_evac) evac
    FROM stop_door_side sds JOIN trips t ON sds.trip_id = t.trip_id
    GROUP BY t.line_name ORDER BY c DESC LIMIT 20
    """)
    print("\n노선별 상위 20:")
    for r in cur.fetchall():
        print(" ", r["line_name"], r["c"], "건, 대피", r["evac"], "건")


if __name__ == "__main__":
    main()
