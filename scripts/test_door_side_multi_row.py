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
    # 광운대 하행 '일반'(비종착) — 2026-08-31 사용자 확인(오른쪽)
    ("L1#서동탄-의정부_평일_하#S421", "광운대", "오른쪽"),
    # 행신·강매 — "서울역행" 경의선 열차만 서울역 착발(왼쪽), 경의중앙선은 오른쪽(2026-08-31 사용자 확인)
    ("GE#경의선 상행#평일#K2201", "행신", "왼쪽"),
    ("GE#경의선 상행#평일#K2201", "강매", "왼쪽"),
    ("GJ#경의중앙선 상행#평일#K5002", "행신", "오른쪽"),
    # 2호선 신도림/성수 — 순환 방향(outer/inner) 텍스트가 trips.direction과 형식이 안 맞아
    # 미반영이던 것을 종착 여부 기준으로 해소(2026-08-31 사용자 확인)
    ("S2#평일#2호선 평일 외선#2129#68", "신도림", "오른쪽"),  # 외선순환 종착
    ("S2#평일#2호선 평일 외선#2009#7", "신도림", "왼쪽"),  # 외선순환 일반
    ("S2BR#평일#DOWN#5703", "신도림", "왼쪽"),  # 까치산지선 종점(신도림)
    ("S2#평일#2호선 평일 외선#2001#3", "성수", "왼쪽"),  # 외선순환 종착(신도림과 반대)
    ("S2BR#토요일#UP#1554", "성수", "오른쪽"),  # 성수지선 종점(성수, 신설동발)
    # 노량진 — 2026-08-31 발견한 버그 수정: 경인급행만 오른쪽, 경부장항(등 그 외 전부)은
    # 방향 무관 왼쪽. 수정 전에는 direction만 보고 상/하행 전부 경인급행 값(오른쪽)을 씀.
    ("L1X#경인급행 상행(평일)#K1002", "노량진", "오른쪽"),
    ("L1#경부장항_평일_상#K602", "노량진", "왼쪽"),
    ("L1#경부장항_평일_하#K1901", "노량진", "왼쪽"),
    # 동두천 상행 일반(비종착) — 수정 전에는 원본의 '확인필요' 상태값을 그대로 door_side로 씀.
    ("L1#경인_평일_상#K952", "동두천", "왼쪽"),
    # 안산과천선 안산 — 하행 일반은 왼쪽, 종착은 오른쪽. 수정 전에는 하행 전체가 종착값(오른쪽).
    ("AG#평일(하)#K4503", "안산", "왼쪽"),
    ("AG#평일(하)#S4301", "안산", "오른쪽"),
    # 대경선 대구 / 대전1호선 중앙로 / 공항철도 김포공항·검암 — 방향 라벨이 목적지명·방면
    # 문구(구미행/판암행/인천공항 방면 등)라 trips.direction과 안 맞아 미반영이던 것 해소
    ("DG#평일_상#K1702", "대구", "왼쪽"),
    ("DG#평일_하#K1705", "대구", "오른쪽"),
    ("AR#평일#1#A3002", "김포공항", "왼쪽"),
    ("AR#평일#0#A2001", "김포공항", "오른쪽"),
    ("AR#평일#0#A3001", "검암", "왼쪽"),  # 종착
    ("AR#평일#0#A2001", "검암", "오른쪽"),  # 일반
    # 안양·의왕·군포·금천구청 "경부급행B" — B급행(K1902/K1904/K1945, 3편뿐)만 왼쪽,
    # 나머지(A급행·완행)는 오른쪽. project_line1_gyeongbu_ab_express 메모리로 해소.
    ("L1#서울급행#K1902", "안양", "왼쪽"),
    ("L1#서울급행#K1902", "의왕", "왼쪽"),
    ("L1#서울급행#K1902", "군포", "왼쪽"),
    ("L1#서울급행#K1902", "금천구청", "왼쪽"),
    ("L1#경부장항_평일_상#K602", "안양", "오른쪽"),
    ("L1#경부장항_평일_상#K602", "의왕", "오른쪽"),
    ("L1#경부장항_평일_상#K602", "군포", "오른쪽"),
    ("L1#경부장항_평일_상#K602", "금천구청", "오른쪽"),
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

    # 신뢰 불가로 스킵 유지 중인 유일한 잔여 조합(광운대 하행 종착 — 원본이 '확인필요')은
    # 여전히 stop_door_side에 안 채워졌는지 확인
    cur.execute(
        """
        SELECT COUNT(*) FROM stop_door_side sds
        JOIN stop_times st ON sds.trip_id = st.trip_id AND sds.stop_seq = st.stop_seq
        JOIN stops s ON st.stop_id = s.stop_id
        JOIN station_groups sg ON s.group_id = sg.group_id
        JOIN trips t ON st.trip_id = t.trip_id
        WHERE sg.name_ko = '광운대' AND s.line = '1호선' AND t.direction = 'down'
          AND st.stop_type = 'destination'
        """
    )
    (n,) = cur.fetchone()
    assert n == 0, f"신호 불충분으로 스킵해야 할 광운대 하행 종착에 {n}건이 채워져 있음"
    print("OK  광운대 하행 종착(확인필요)은 예정대로 스킵됨")

    # door_side에 '왼쪽'/'오른쪽' 외의 값('확인필요'·'미판정'·'미개통' 등 원본 placeholder가
    # 그대로 샌 것)이 하나도 없는지 — 2026-08-31 실제로 2,408건 새고 있던 걸 발견해 수정함
    cur.execute("SELECT DISTINCT door_side FROM stop_door_side WHERE door_side NOT IN ('왼쪽', '오른쪽')")
    bad = cur.fetchall()
    assert not bad, f"door_side에 placeholder 값이 새고 있음: {bad}"
    print("OK  door_side에 placeholder 값 없음(왼쪽/오른쪽만 존재)")

    # 동두천 상행 종착도 위와 같은 이유(원본 '확인필요')로 스킵돼야 함 — 예전엔 방향-무관
    # 기본행(왼쪽/일반)으로 잘못 새고 있었음(2026-08-31 발견한 resolve_door 설계 버그)
    cur.execute(
        """
        SELECT COUNT(*) FROM stop_door_side sds
        JOIN stop_times st ON sds.trip_id = st.trip_id AND sds.stop_seq = st.stop_seq
        JOIN stops s ON st.stop_id = s.stop_id
        JOIN station_groups sg ON s.group_id = sg.group_id
        JOIN trips t ON st.trip_id = t.trip_id
        WHERE sg.name_ko = '동두천' AND s.line = '1호선' AND t.direction = 'up'
          AND st.stop_type = 'destination'
        """
    )
    (n,) = cur.fetchone()
    assert n == 0, f"신호 불충분으로 스킵해야 할 동두천 상행 종착에 {n}건이 채워져 있음"
    print("OK  동두천 상행 종착(확인필요)은 예정대로 스킵됨")

    print(f"\n{len(KNOWN_CASES)}건 + 부수 검증 4건 전부 통과")


if __name__ == "__main__":
    main()
