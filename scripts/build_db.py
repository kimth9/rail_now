#!/usr/bin/env python3
"""파싱 결과(out/, out_line1/)를 하나의 SQLite 번들로 병합.

역 모델:
  stops          = 승강장 단위 (서울 / 서울(지하) 별개)
  station_groups = 동일 역사 (둘 다 '서울' 그룹)
분리 대상은 원본 파일이 접두사로 구분해 둔 역만.
"""
import csv
import itertools
import os
import sqlite3
import sys

OUT_KTX = "tmp/out_ktx"
# 1호선은 운행일 구분별로 파싱 결과가 나뉜다 (평일 / 휴일)
OUT_L1_DIRS = ["tmp/out_line1", "tmp/out_line1_hol"]
OUT_SUIN_BUNDANG = "tmp/out_suin_bundang"
OUT_ANSAN_GWACHEON = "tmp/out_ansan_gwacheon"
OUT_GYEONGUI_JUNGANG = "tmp/out_gyeongui_jungang"
OUT_GYEONGUI = "tmp/out_gyeongui"
OUT_GYEONGCHUN = "tmp/out_gyeongchun"
OUT_GYEONGIN_EXPRESS = "tmp/out_gyeongin_express"
OUT_GYEONGGANG = "tmp/out_gyeonggang"
OUT_DONGHAE = "tmp/out_donghae"
OUT_DAEGYEONG = "tmp/out_daegyeong"
OUT_ITX_CHUNCHEON = "tmp/out_itx_chuncheon"
OUT_SEOHAE = "tmp/out_seohae"
OUT_ILBAN = "tmp/out_ilban"
OUT_GWANGWANG = "tmp/out_gwangwang"
OUT_DAEGU = ["tmp/out_daegu1", "tmp/out_daegu2", "tmp/out_daegu3"]
OUT_DAEJEON1 = "tmp/out_daejeon"
OUT_BUSAN = ["tmp/out_busan1", "tmp/out_busan2", "tmp/out_busan3", "tmp/out_busan4"]
OUT_BUSAN_GIMHAE = "tmp/out_busan_gimhae"
# 서울교통공사 2·7호선 — 평일/휴일이 별개 파일이라 노선당 출력폴더 목록 (기존
# RAW 엑셀 기반 유지: 2026-08 기준 더 최신이라 판단해 공식 CSV로 안 바꿈)
OUT_SEOUL = {
    "SEOUL2": ["tmp/out_seoul2", "tmp/out_seoul2_hol"],
    "SEOUL7": ["tmp/out_seoul7", "tmp/out_seoul7_hol"],
}
SEOUL_PREFIX = {"SEOUL2": "S2", "SEOUL7": "S7"}
# 서울교통공사 3·5·6·8·9호선 — 공공데이터포털 공식 CSV(2026-06-16, 역 중심 목록)
# 기반 scripts/parse_seoul_official.py 출력. 폴더 1개에 평일/토요일/휴일 3종
# 다이어가 다 있어 대구·부산·광주1호선과 같은 SUN_ONLY_LABEL 처리가 필요하다.
# 3호선은 기존에 '일산선'이라는 이름으로만 등록돼 있던 걸 이번에 정식으로
# '3호선'으로 재정리(같은 전 구간, 오금~대화)했다.
OUT_SEOUL_OFFICIAL = {
    "SEOUL3": "tmp/out_seoul3_new", "SEOUL5": "tmp/out_seoul5_new",
    "SEOUL6": "tmp/out_seoul6_new", "SEOUL8": "tmp/out_seoul8_new",
    "SEOUL9": "tmp/out_seoul9_new",
}
SEOUL_OFFICIAL_PREFIX = {"SEOUL3": "S3O", "SEOUL5": "S5O", "SEOUL6": "S6O",
                          "SEOUL8": "S8O", "SEOUL9": "S9O"}
# 2호선 지선(성수지선·신정지선) — 본선은 기존 데이터 유지, 지선 6개 역만 같은
# 공식 CSV에서 추출(scripts/parse_seoul2_branch.py). LINE_OF["SEOUL2"]로 등록해
# 본선과 같은 '2호선' station_groups에 자동 병합된다.
OUT_SEOUL2_BRANCH = "tmp/out_seoul2_branch"
OUT_INCHEON1 = "tmp/out_incheon1"
OUT_AIRPORT_RAILROAD = "tmp/out_airport_railroad"
OUT_GIMPO_GOLDLINE = "tmp/out_gimpo_goldline"
OUT_SILLIM = "tmp/out_sillim"
OUT_UI_SINSEOL = "tmp/out_ui_sinseol"
OUT_GTXA_L08 = "tmp/out_gtxa_l08"
OUT_GTXA_L09 = "tmp/out_gtxa_l09"
OUT_GWANGJU1 = "tmp/out_gwangju1"
OUT_INCHEON2 = "tmp/out_incheon2"
OUT_YONGIN = "tmp/out_yongin"
OUT_UIJEONGBU = "tmp/out_uijeongbu"
OUT_SINBUNDANG = "tmp/out_sinbundang"
DB = sys.argv[1] if len(sys.argv) > 1 else "output/kr_rail_timetable.sqlite"

# 노선 단위로 승강장을 나눈다. 계통(경인/경부장항 등)은 나누지 않는다.
LINE_OF = {"KTX": "국철", "LINE1": "1호선", "SUIN_BUNDANG": "수인분당선",
           "ANSAN_GWACHEON": "안산과천선", "GYEONGUI_JUNGANG": "경의중앙선",
           "GYEONGUI": "경의선", "GYEONGCHUN": "경춘선", "GYEONGGANG": "경강선",
           "DONGHAE": "동해선(전동)", "DAEGYEONG": "대경선", "SEOUL3": "3호선",
           "ITX_CHUNCHEON": "ITX-청춘", "SEOHAE": "서해선(전동)",
           "DAEGU1": "대구1호선", "DAEGU2": "대구2호선", "DAEGU3": "대구3호선",
           "DAEJEON1": "대전1호선",
           "BUSAN1": "부산1호선", "BUSAN2": "부산2호선", "BUSAN3": "부산3호선",
           "BUSAN4": "부산4호선", "BUSAN_GIMHAE": "부산김해경전철",
           "SEOUL2": "2호선", "SEOUL5": "5호선", "SEOUL6": "6호선",
           "SEOUL7": "7호선", "SEOUL8": "8호선", "SEOUL9": "9호선",
           "INCHEON1": "인천1호선", "AREX": "공항철도",
           "GIMPO_GOLDLINE": "김포골드라인", "SILLIM": "신림선",
           "UI_SINSEOL": "우이신설선",
           "GTXA_L08": "GTX-A(운정~서울)", "GTXA_L09": "GTX-A(수서~동탄)",
           "GWANGJU1": "광주1호선", "INCHEON2": "인천2호선(추정)",
           "YONGIN": "용인경전철(추정)", "UIJEONGBU": "의정부경전철",
           "SINBUNDANG": "신분당선"}
# 1호선 원본이 지상/지하를 구분해 둔 이름은 노선 분리로 대체되므로 원래 이름으로 되돌린다
UNSPLIT = {"서울(지하)": "서울", "청량리(지하)": "청량리"}

SCHEMA = """
CREATE TABLE stops(stop_id TEXT PRIMARY KEY, display_name TEXT, name_ko TEXT,
                   line TEXT, name_hanja TEXT, group_id TEXT);
CREATE TABLE station_groups(group_id TEXT PRIMARY KEY, name_ko TEXT);
CREATE TABLE junctions(junction_id TEXT PRIMARY KEY, name_ko TEXT);
CREATE TABLE trips(trip_id TEXT PRIMARY KEY, train_no TEXT, line_name TEXT,
                   formation TEXT, direction TEXT, service_id TEXT,
                   origin TEXT, destination TEXT, next_train_no TEXT, source TEXT);
CREATE TABLE stop_times(trip_id TEXT, stop_seq INT, stop_id TEXT,
                        arr_sec INT, dep_sec INT, stop_type TEXT,
                        PRIMARY KEY(trip_id, stop_seq));
CREATE TABLE calendar(service_id TEXT PRIMARY KEY, mon INT,tue INT,wed INT,
                      thu INT,fri INT,sat INT,sun INT);
CREATE TABLE meta(key TEXT, value TEXT);
"""


def main():
    if os.path.exists(DB):
        os.remove(DB)
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.executescript(SCHEMA)

    name2id, groups = {}, {}

    def gid(display_name, merge_key):
        """merge_key로 그룹을 묶되, 사용자에게 보이는 이름(station_groups.name_ko)은
        항상 깨끗한 display_name — 서로 무관한 동명역을 분리하려고 merge_key에
        지명을 붙여도(예: '부산교대') 화면에는 절대 노출되지 않는다."""
        if merge_key not in groups:
            groups[merge_key] = f"G{len(groups)+1:04d}"
            cur.execute("INSERT INTO station_groups VALUES(?,?)", (groups[merge_key], display_name))
        return groups[merge_key]

    def add(raw_name, line, hanja="", eng="", merge_key=None):
        """노선별로 별개 승강장을 만들고, 같은 역명은 하나의 역사 그룹으로 묶는다.
        merge_key를 주면 그 값으로 그룹을 나눈다 — 서로 무관한 동명역(다른 도시의
        같은 지명 등)이 이름만 보고 잘못 병합되는 걸 막기 위한 내부 키일 뿐,
        station_groups.name_ko/stops.name_ko에는 절대 반영되지 않는다."""
        base = UNSPLIT.get(raw_name, raw_name)
        mkey = merge_key or base
        key = (mkey, line)
        if key in name2id:
            return name2id[key]
        sid = f"KR{len(name2id)+1:04d}"
        name2id[key] = sid
        cur.execute("INSERT INTO stops VALUES(?,?,?,?,?,?)",
                    (sid, f"{base}({line})", base, line, hanja or "", gid(base, mkey)))
        return sid

    def rd(path):
        return csv.DictReader(open(path, encoding="utf-8-sig"))

    def SUN_ONLY_LABEL(service_id):
        """평일/토요일/휴일 3종 다이어 계열(대구·부산·광주1호선)의 '휴일'은
        일요일 전용 — 2종 다이어(평일/휴일=토+일) 계열과 문자열이 같아 그대로
        두면 먼저 INSERT된 쪽에 덮여 일요일 전용 트립이 토요일에도 잘못
        노출되므로 별도 calendar 행으로 이름을 분리한다."""
        return "휴일(일요일)" if service_id == "휴일" else service_id

    # --- KTX ---
    km = {r["stop_id"]: add(r["name_ko"], LINE_OF["KTX"], r["name_hanja"])
          for r in rd(f"{OUT_KTX}/stops.csv")}
    for t in rd(f"{OUT_KTX}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("KTX#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], km[t["origin"]], km[t["destination"]],
                     "", "KTX"))
    rows = sorted(rd(f"{OUT_KTX}/stop_times.csv"),
                  key=lambda r: (r["trip_id"], int(r["stop_seq"])))
    for tid, grp in itertools.groupby(rows, key=lambda r: r["trip_id"]):
        g = list(grp)
        for i, s in enumerate(g):
            kind = "origin" if i == 0 else ("destination" if i == len(g) - 1 else "stop")
            sec = int(s["dep_sec"])
            # KTX 원본은 역당 시각 1개 — 종착역만 도착시각으로 해석
            cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                        ("KTX#" + tid, int(s["stop_seq"]), km[s["stop_id"]],
                         sec if kind == "destination" else None,
                         None if kind == "destination" else sec, kind))
    for r in rd(f"{OUT_KTX}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 일반열차(무궁화·ITX-새마을·ITX-마음 등) — KTX와 같은 "역당 시각 1개" 구조라
    #     같은 해석 규칙을 쓰고, LINE_OF["KTX"]("국철")로 등록해 KTX와 stop_id 공유 ---
    ibm = {r["stop_id"]: add(r["name_ko"], LINE_OF["KTX"], r["name_hanja"],
                             merge_key=r.get("merge_key") or None)
           for r in rd(f"{OUT_ILBAN}/stops.csv")}
    for t in rd(f"{OUT_ILBAN}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("IB#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], ibm[t["origin"]], ibm[t["destination"]],
                     "", "ILBAN"))
    rows = sorted(rd(f"{OUT_ILBAN}/stop_times.csv"),
                  key=lambda r: (r["trip_id"], int(r["stop_seq"])))
    for tid, grp in itertools.groupby(rows, key=lambda r: r["trip_id"]):
        g = list(grp)
        for i, s in enumerate(g):
            kind = "origin" if i == 0 else ("destination" if i == len(g) - 1 else "stop")
            sec = int(s["dep_sec"])
            cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                        ("IB#" + tid, int(s["stop_seq"]), ibm[s["stop_id"]],
                         sec if kind == "destination" else None,
                         None if kind == "destination" else sec, kind))
    for r in rd(f"{OUT_ILBAN}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 관광열차 (KTX/일반열차와 같은 선로를 쓰므로 "국철"로 등록) ---
    gwm = {r["stop_id"]: add(r["name_ko"], LINE_OF["KTX"])
           for r in rd(f"{OUT_GWANGWANG}/stops.csv")}
    for t in rd(f"{OUT_GWANGWANG}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("GW#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], gwm.get(t["origin"], t["origin"]),
                     gwm.get(t["destination"], t["destination"]), t["next_train_no"], "GWANGWANG"))
    for st in rd(f"{OUT_GWANGWANG}/stop_times.csv"):
        cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                    ("GW#" + st["trip_id"], int(st["stop_seq"]),
                     gwm.get(st["stop_id"], st["stop_id"]),
                     int(st["arr_sec"]) if st["arr_sec"] else None,
                     int(st["dep_sec"]) if st["dep_sec"] else None, st["stop_type"]))
    for r in rd(f"{OUT_GWANGWANG}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 1호선 (평일 / 휴일) ---
    cur.execute("INSERT INTO junctions VALUES(?,?)", ("@시흥연결선", "시흥연결선"))
    # 마전(경원선 양주~덕계)은 여객취급 안 하는 신호장 — 인천2호선 마전역과 동명이라
    # 예전엔 station_groups에서 잘못 병합돼 있었음(2026-08-29 발견, parse_line1.py의
    # JUNCTIONS로 분리)
    cur.execute("INSERT INTO junctions VALUES(?,?)", ("@마전신호장", "마전신호장"))
    for d in OUT_L1_DIRS:
        lm = {r["stop_id"]: add(r["name_ko"], LINE_OF["LINE1"])
              for r in rd(f"{d}/stops.csv")}
        for t in rd(f"{d}/trips.csv"):
            cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                        ("L1#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                         t["direction"], t["service_id"], lm.get(t["origin"], t["origin"]),
                         lm.get(t["destination"], t["destination"]), t["next_train_no"], "LINE1"))
        for st in rd(f"{d}/stop_times.csv"):
            cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                        ("L1#" + st["trip_id"], int(st["stop_seq"]),
                         lm.get(st["stop_id"], st["stop_id"]),
                         int(st["arr_sec"]) if st["arr_sec"] else None,
                         int(st["dep_sec"]) if st["dep_sec"] else None, st["stop_type"]))
    cur.executemany("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)", [
        ("평일", 1, 1, 1, 1, 1, 0, 0),
        ("휴일", 0, 0, 0, 0, 0, 1, 1),   # 공휴일은 calendar_dates로 예외 처리 필요
    ])

    # --- 경인급행 (1호선 소속 — 원본 1호선 파일보다 최신 개정판으로 교체) ---
    # parse_line1.py의 SKIP_SHEETS에서 이미 옛 경인급행_*/시트를 뺐다. 여기서
    # LINE_OF["LINE1"]로 등록해 기존 1호선 역(구로 등)과 stop_id를 공유시킨다.
    gxm = {r["stop_id"]: add(r["name_ko"], LINE_OF["LINE1"])
           for r in rd(f"{OUT_GYEONGIN_EXPRESS}/stops.csv")}
    for t in rd(f"{OUT_GYEONGIN_EXPRESS}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("L1X#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], gxm.get(t["origin"], t["origin"]),
                     gxm.get(t["destination"], t["destination"]), t["next_train_no"], "LINE1_GYEONGIN_EXPRESS"))
    for st in rd(f"{OUT_GYEONGIN_EXPRESS}/stop_times.csv"):
        cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                    ("L1X#" + st["trip_id"], int(st["stop_seq"]),
                     gxm.get(st["stop_id"], st["stop_id"]),
                     int(st["arr_sec"]) if st["arr_sec"] else None,
                     int(st["dep_sec"]) if st["dep_sec"] else None, st["stop_type"]))
    for r in rd(f"{OUT_GYEONGIN_EXPRESS}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 수인분당선 (평일/휴일 한 파일에 같이 있음) ---
    sm = {r["stop_id"]: add(r["name_ko"], LINE_OF["SUIN_BUNDANG"])
          for r in rd(f"{OUT_SUIN_BUNDANG}/stops.csv")}
    for t in rd(f"{OUT_SUIN_BUNDANG}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("SB#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], sm.get(t["origin"], t["origin"]),
                     sm.get(t["destination"], t["destination"]), t["next_train_no"], "SUIN_BUNDANG"))
    for st in rd(f"{OUT_SUIN_BUNDANG}/stop_times.csv"):
        cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                    ("SB#" + st["trip_id"], int(st["stop_seq"]),
                     sm.get(st["stop_id"], st["stop_id"]),
                     int(st["arr_sec"]) if st["arr_sec"] else None,
                     int(st["dep_sec"]) if st["dep_sec"] else None, st["stop_type"]))
    for r in rd(f"{OUT_SUIN_BUNDANG}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 안산과천선 (평일/휴일 한 파일에 같이 있음) ---
    cur.execute("INSERT INTO junctions VALUES(?,?)", ("@시흥기지", "시흥기지"))
    agm = {r["stop_id"]: add(r["name_ko"], LINE_OF["ANSAN_GWACHEON"])
           for r in rd(f"{OUT_ANSAN_GWACHEON}/stops.csv")}
    for t in rd(f"{OUT_ANSAN_GWACHEON}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("AG#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], agm.get(t["origin"], t["origin"]),
                     agm.get(t["destination"], t["destination"]), t["next_train_no"], "ANSAN_GWACHEON"))
    for st in rd(f"{OUT_ANSAN_GWACHEON}/stop_times.csv"):
        cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                    ("AG#" + st["trip_id"], int(st["stop_seq"]),
                     agm.get(st["stop_id"], st["stop_id"]),
                     int(st["arr_sec"]) if st["arr_sec"] else None,
                     int(st["dep_sec"]) if st["dep_sec"] else None, st["stop_type"]))
    for r in rd(f"{OUT_ANSAN_GWACHEON}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 경의중앙선 (평일/휴일 한 파일에 같이 있음) ---
    gjm = {r["stop_id"]: add(r["name_ko"], LINE_OF["GYEONGUI_JUNGANG"])
           for r in rd(f"{OUT_GYEONGUI_JUNGANG}/stops.csv")}
    for t in rd(f"{OUT_GYEONGUI_JUNGANG}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("GJ#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], gjm.get(t["origin"], t["origin"]),
                     gjm.get(t["destination"], t["destination"]), t["next_train_no"], "GYEONGUI_JUNGANG"))
    for st in rd(f"{OUT_GYEONGUI_JUNGANG}/stop_times.csv"):
        cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                    ("GJ#" + st["trip_id"], int(st["stop_seq"]),
                     gjm.get(st["stop_id"], st["stop_id"]),
                     int(st["arr_sec"]) if st["arr_sec"] else None,
                     int(st["dep_sec"]) if st["dep_sec"] else None, st["stop_type"]))
    for r in rd(f"{OUT_GYEONGUI_JUNGANG}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 경의선 (도라산~서울, 경의중앙선과 가좌~문산 구간 선로 공유) ---
    gem = {r["stop_id"]: add(r["name_ko"], LINE_OF["GYEONGUI"])
           for r in rd(f"{OUT_GYEONGUI}/stops.csv")}
    for t in rd(f"{OUT_GYEONGUI}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("GE#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], gem.get(t["origin"], t["origin"]),
                     gem.get(t["destination"], t["destination"]), t["next_train_no"], "GYEONGUI"))
    for st in rd(f"{OUT_GYEONGUI}/stop_times.csv"):
        cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                    ("GE#" + st["trip_id"], int(st["stop_seq"]),
                     gem.get(st["stop_id"], st["stop_id"]),
                     int(st["arr_sec"]) if st["arr_sec"] else None,
                     int(st["dep_sec"]) if st["dep_sec"] else None, st["stop_type"]))
    for r in rd(f"{OUT_GYEONGUI}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 경춘선 (평일/휴일 한 파일에 같이 있음, 광운대시종착 포함) ---
    gcm = {r["stop_id"]: add(r["name_ko"], LINE_OF["GYEONGCHUN"])
           for r in rd(f"{OUT_GYEONGCHUN}/stops.csv")}
    for t in rd(f"{OUT_GYEONGCHUN}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("GC#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], gcm.get(t["origin"], t["origin"]),
                     gcm.get(t["destination"], t["destination"]), t["next_train_no"], "GYEONGCHUN"))
    for st in rd(f"{OUT_GYEONGCHUN}/stop_times.csv"):
        cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                    ("GC#" + st["trip_id"], int(st["stop_seq"]),
                     gcm.get(st["stop_id"], st["stop_id"]),
                     int(st["arr_sec"]) if st["arr_sec"] else None,
                     int(st["dep_sec"]) if st["dep_sec"] else None, st["stop_type"]))
    for r in rd(f"{OUT_GYEONGCHUN}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 경강선 (평일/휴일 한 파일에 같이 있음) ---
    ggm = {r["stop_id"]: add(r["name_ko"], LINE_OF["GYEONGGANG"])
           for r in rd(f"{OUT_GYEONGGANG}/stops.csv")}
    for t in rd(f"{OUT_GYEONGGANG}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("GG#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], ggm.get(t["origin"], t["origin"]),
                     ggm.get(t["destination"], t["destination"]), t["next_train_no"], "GYEONGGANG"))
    for st in rd(f"{OUT_GYEONGGANG}/stop_times.csv"):
        cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                    ("GG#" + st["trip_id"], int(st["stop_seq"]),
                     ggm.get(st["stop_id"], st["stop_id"]),
                     int(st["arr_sec"]) if st["arr_sec"] else None,
                     int(st["dep_sec"]) if st["dep_sec"] else None, st["stop_type"]))
    for r in rd(f"{OUT_GYEONGGANG}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 동해선(전동) — KTX/일반열차 파일에도 각각 다른 실체의 '동해선'이 있어
    #     line_name에 계열 구분자(전동)를 붙인다 (노선명 충돌 방지) ---
    dhm = {r["stop_id"]: add(r["name_ko"], LINE_OF["DONGHAE"],
                             merge_key=r.get("merge_key") or None)
           for r in rd(f"{OUT_DONGHAE}/stops.csv")}
    for t in rd(f"{OUT_DONGHAE}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("DH#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], dhm.get(t["origin"], t["origin"]),
                     dhm.get(t["destination"], t["destination"]), t["next_train_no"], "DONGHAE"))
    for st in rd(f"{OUT_DONGHAE}/stop_times.csv"):
        cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                    ("DH#" + st["trip_id"], int(st["stop_seq"]),
                     dhm.get(st["stop_id"], st["stop_id"]),
                     int(st["arr_sec"]) if st["arr_sec"] else None,
                     int(st["dep_sec"]) if st["dep_sec"] else None, st["stop_type"]))
    for r in rd(f"{OUT_DONGHAE}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 대경선 (평일/휴일 한 파일에 같이 있음) ---
    dgm = {r["stop_id"]: add(r["name_ko"], LINE_OF["DAEGYEONG"])
           for r in rd(f"{OUT_DAEGYEONG}/stops.csv")}
    for t in rd(f"{OUT_DAEGYEONG}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("DG#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], dgm.get(t["origin"], t["origin"]),
                     dgm.get(t["destination"], t["destination"]), t["next_train_no"], "DAEGYEONG"))
    for st in rd(f"{OUT_DAEGYEONG}/stop_times.csv"):
        cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                    ("DG#" + st["trip_id"], int(st["stop_seq"]),
                     dgm.get(st["stop_id"], st["stop_id"]),
                     int(st["arr_sec"]) if st["arr_sec"] else None,
                     int(st["dep_sec"]) if st["dep_sec"] else None, st["stop_type"]))
    for r in rd(f"{OUT_DAEGYEONG}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 서울교통공사 3·5·6·8·9호선(공식 CSV, 2026-06-16) — 3종 다이어라
    #     대구·부산·광주1호선과 같은 SUN_ONLY_LABEL 처리 필요 ---
    for line_key, out_dir in OUT_SEOUL_OFFICIAL.items():
        pfx = SEOUL_OFFICIAL_PREFIX[line_key]
        som = {r["stop_id"]: add(r["name_ko"], LINE_OF[line_key])
               for r in rd(f"{out_dir}/stops.csv")}
        for t in rd(f"{out_dir}/trips.csv"):
            cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (f"{pfx}#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                         t["direction"], SUN_ONLY_LABEL(t["service_id"]), som[t["origin"]],
                         som[t["destination"]], t["next_train_no"], line_key))
        for st in rd(f"{out_dir}/stop_times.csv"):
            cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                        (f"{pfx}#" + st["trip_id"], int(st["stop_seq"]),
                         som[st["stop_id"]],
                         int(st["arr_sec"]) if st["arr_sec"] else None,
                         int(st["dep_sec"]) if st["dep_sec"] else None, st["stop_type"]))
        for r in rd(f"{out_dir}/calendar.csv"):
            cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                        (SUN_ONLY_LABEL(r["service_id"]), r["mon"], r["tue"], r["wed"],
                         r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 2호선 지선(성수지선·신정지선, 같은 공식 CSV) — 본선은 기존 데이터
    #     유지, 지선 6개 역만 여기서 추가. LINE_OF["SEOUL2"]로 등록해 본선과
    #     같은 '2호선' station_groups에 자동 병합된다 ---
    s2bm = {r["stop_id"]: add(r["name_ko"], LINE_OF["SEOUL2"])
            for r in rd(f"{OUT_SEOUL2_BRANCH}/stops.csv")}
    for t in rd(f"{OUT_SEOUL2_BRANCH}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("S2BR#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], SUN_ONLY_LABEL(t["service_id"]), s2bm[t["origin"]],
                     s2bm[t["destination"]], t["next_train_no"], "SEOUL2_BRANCH"))
    for st in rd(f"{OUT_SEOUL2_BRANCH}/stop_times.csv"):
        cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                    ("S2BR#" + st["trip_id"], int(st["stop_seq"]),
                     s2bm[st["stop_id"]],
                     int(st["arr_sec"]) if st["arr_sec"] else None,
                     int(st["dep_sec"]) if st["dep_sec"] else None, st["stop_type"]))
    for r in rd(f"{OUT_SEOUL2_BRANCH}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (SUN_ONLY_LABEL(r["service_id"]), r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- ITX-청춘 (여객열차 — 용산~춘천, 경의중앙선·경춘선과 선로 공유) ---
    icm = {r["stop_id"]: add(r["name_ko"], LINE_OF["ITX_CHUNCHEON"])
           for r in rd(f"{OUT_ITX_CHUNCHEON}/stops.csv")}
    for t in rd(f"{OUT_ITX_CHUNCHEON}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("IC#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], icm.get(t["origin"], t["origin"]),
                     icm.get(t["destination"], t["destination"]), t["next_train_no"], "ITX_CHUNCHEON"))
    for st in rd(f"{OUT_ITX_CHUNCHEON}/stop_times.csv"):
        cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                    ("IC#" + st["trip_id"], int(st["stop_seq"]),
                     icm.get(st["stop_id"], st["stop_id"]),
                     int(st["arr_sec"]) if st["arr_sec"] else None,
                     int(st["dep_sec"]) if st["dep_sec"] else None, st["stop_type"]))
    for r in rd(f"{OUT_ITX_CHUNCHEON}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 서해선(전동, 대곡~일산 직결, 원시행) — 일반열차 파일에도 서화성~홍성 구간의
    #     별개 실체 '서해선(일반, ITX-마음)'이 이미 있어 line_name에 (전동) 접미사 ---
    shm = {r["stop_id"]: add(r["name_ko"], LINE_OF["SEOHAE"])
           for r in rd(f"{OUT_SEOHAE}/stops.csv")}
    for t in rd(f"{OUT_SEOHAE}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("SH#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], shm.get(t["origin"], t["origin"]),
                     shm.get(t["destination"], t["destination"]), t["next_train_no"], "SEOHAE"))
    for st in rd(f"{OUT_SEOHAE}/stop_times.csv"):
        cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                    ("SH#" + st["trip_id"], int(st["stop_seq"]),
                     shm.get(st["stop_id"], st["stop_id"]),
                     int(st["arr_sec"]) if st["arr_sec"] else None,
                     int(st["dep_sec"]) if st["dep_sec"] else None, st["stop_type"]))
    for r in rd(f"{OUT_SEOHAE}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 대구 1/2/3호선(대구교통공사, 비코레일) — 물리적 환승역(대구역·동대구역·
    #     서대구역)만 대경선과 자동 병합, 나머지는 완전 별도 station_groups.
    #     평일/토요일/휴일 3종 다이어의 '휴일'은 일요일 전용인데, 국철·1호선 등
    #     2종 다이어(평일/휴일=토+일)의 '휴일'과 문자열이 같아 그대로 두면
    #     먼저 INSERT된 쪽(토+일)에 덮여 일요일 전용 트립이 토요일에도 잘못
    #     노출된다 — 3종 다이어 계열(대구·부산·광주1호선)에서만 SUN_ONLY_LABEL로
    #     구분해 별도 calendar 행으로 분리한다 ---
    for i, out_dir in enumerate(OUT_DAEGU, start=1):
        line_key = f"DAEGU{i}"
        dgm = {r["stop_id"]: add(r["name_ko"], LINE_OF[line_key],
                                 merge_key=r.get("merge_key") or None)
               for r in rd(f"{out_dir}/stops.csv")}
        for t in rd(f"{out_dir}/trips.csv"):
            cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (f"DG{i}#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                         t["direction"], SUN_ONLY_LABEL(t["service_id"]), dgm.get(t["origin"], t["origin"]),
                         dgm.get(t["destination"], t["destination"]), t["next_train_no"], line_key))
        for st in rd(f"{out_dir}/stop_times.csv"):
            cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                        (f"DG{i}#" + st["trip_id"], int(st["stop_seq"]),
                         dgm.get(st["stop_id"], st["stop_id"]),
                         int(st["arr_sec"]) if st["arr_sec"] else None,
                         int(st["dep_sec"]) if st["dep_sec"] else None, st["stop_type"]))
        for r in rd(f"{out_dir}/calendar.csv"):
            cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                        (SUN_ONLY_LABEL(r["service_id"]), r["mon"], r["tue"], r["wed"],
                         r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 대전 1호선(대전교통공사, 비코레일) — "출발역 기준 배차표" 원본이라
    #     역당 시각 1개(KTX와 같은 해석 규칙: 종착역만 도착시각) ---
    djm = {r["stop_id"]: add(r["name_ko"], LINE_OF["DAEJEON1"],
                             merge_key=r.get("merge_key") or None)
           for r in rd(f"{OUT_DAEJEON1}/stops.csv")}
    for t in rd(f"{OUT_DAEJEON1}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("DJ1#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], djm[t["origin"]], djm[t["destination"]],
                     "", "DAEJEON1"))
    rows = sorted(rd(f"{OUT_DAEJEON1}/stop_times.csv"),
                  key=lambda r: (r["trip_id"], int(r["stop_seq"])))
    for tid, grp in itertools.groupby(rows, key=lambda r: r["trip_id"]):
        g = list(grp)
        for i, s in enumerate(g):
            kind = "origin" if i == 0 else ("destination" if i == len(g) - 1 else "stop")
            sec = int(s["dep_sec"])
            cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                        ("DJ1#" + tid, int(s["stop_seq"]), djm[s["stop_id"]],
                         sec if kind == "destination" else None,
                         None if kind == "destination" else sec, kind))
    for r in rd(f"{OUT_DAEJEON1}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 부산 1/2/3/4호선(부산교통공사, 비코레일) — 노선 내부 환승(서면·동래·연산·
    #     덕천·수영·미남)은 자동 병합, 동해선(전동)과 실제 환승인 '교대'는 두 파서가
    #     같은 merge_key("부산교대")를 써서 병합(표시명은 서로 그냥 '교대') ---
    for i, out_dir in enumerate(OUT_BUSAN, start=1):
        line_key = f"BUSAN{i}"
        bsm = {r["stop_id"]: add(r["name_ko"], LINE_OF[line_key],
                                 merge_key=r.get("merge_key") or None)
               for r in rd(f"{out_dir}/stops.csv")}
        for t in rd(f"{out_dir}/trips.csv"):
            cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (f"BS{i}#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                         t["direction"], SUN_ONLY_LABEL(t["service_id"]), bsm.get(t["origin"], t["origin"]),
                         bsm.get(t["destination"], t["destination"]), t["next_train_no"], line_key))
        for st in rd(f"{out_dir}/stop_times.csv"):
            cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                        (f"BS{i}#" + st["trip_id"], int(st["stop_seq"]),
                         bsm.get(st["stop_id"], st["stop_id"]),
                         int(st["arr_sec"]) if st["arr_sec"] else None,
                         int(st["dep_sec"]) if st["dep_sec"] else None, st["stop_type"]))
        for r in rd(f"{out_dir}/calendar.csv"):
            cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                        (SUN_ONLY_LABEL(r["service_id"]), r["mon"], r["tue"], r["wed"],
                         r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 부산김해경전철(비코레일) — 사상(부산2호선)·대저(부산3호선) 실제 환승역만
    #     자동 병합, 나머지는 완전 별도 station_groups. "공항"은 광주1호선의 무관한
    #     동명역과 섞이지 않게 merge_key로 분리 ---
    bgm = {r["stop_id"]: add(r["name_ko"], LINE_OF["BUSAN_GIMHAE"],
                             merge_key=r.get("merge_key") or None)
           for r in rd(f"{OUT_BUSAN_GIMHAE}/stops.csv")}
    for t in rd(f"{OUT_BUSAN_GIMHAE}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("BG#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], bgm.get(t["origin"], t["origin"]),
                     bgm.get(t["destination"], t["destination"]), t["next_train_no"], "BUSAN_GIMHAE"))
    for st in rd(f"{OUT_BUSAN_GIMHAE}/stop_times.csv"):
        cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                    ("BG#" + st["trip_id"], int(st["stop_seq"]),
                     bgm.get(st["stop_id"], st["stop_id"]),
                     int(st["arr_sec"]) if st["arr_sec"] else None,
                     int(st["dep_sec"]) if st["dep_sec"] else None, st["stop_type"]))
    for r in rd(f"{OUT_BUSAN_GIMHAE}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 서울교통공사 2·7호선(비코레일, 기존 RAW 엑셀 유지) — 2호선은
    #     순환선(외선/내선), 7호선은 상행/하행. 각 노선 내부 환승은 이름 기반
    #     자동 병합에 맡김. 나머지 서울교통공사 노선(3·5·6·8·9호선)은 위에서
    #     공식 CSV로 별도 처리 ---
    for line_key, dirs in OUT_SEOUL.items():
        pfx = SEOUL_PREFIX[line_key]
        for out_dir in dirs:
            sm = {r["stop_id"]: add(r["name_ko"], LINE_OF[line_key],
                                     merge_key=r.get("merge_key") or None)
                  for r in rd(f"{out_dir}/stops.csv")}
            for t in rd(f"{out_dir}/trips.csv"):
                cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                            (f"{pfx}#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                             t["direction"], t["service_id"], sm.get(t["origin"], t["origin"]),
                             sm.get(t["destination"], t["destination"]), t["next_train_no"], line_key))
            for st in rd(f"{out_dir}/stop_times.csv"):
                cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                            (f"{pfx}#" + st["trip_id"], int(st["stop_seq"]),
                             sm.get(st["stop_id"], st["stop_id"]),
                             int(st["arr_sec"]) if st["arr_sec"] else None,
                             int(st["dep_sec"]) if st["dep_sec"] else None, st["stop_type"]))
            for r in rd(f"{out_dir}/calendar.csv"):
                cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                            (r["service_id"], r["mon"], r["tue"], r["wed"],
                             r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 인천 도시철도 1호선(인천교통공사, 비코레일) — "역당 시각 1개" 구조라
    #     KTX와 같은 해석 규칙(종착역만 도착시각). 부평(1호선)·부평구청(7호선)·
    #     계양(공항철도)에서 실제 환승역으로 자동 병합 ---
    icm = {r["stop_id"]: add(r["name_ko"], LINE_OF["INCHEON1"])
           for r in rd(f"{OUT_INCHEON1}/stops.csv")}
    for t in rd(f"{OUT_INCHEON1}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("IC1#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], icm[t["origin"]], icm[t["destination"]],
                     "", "INCHEON1"))
    rows = sorted(rd(f"{OUT_INCHEON1}/stop_times.csv"),
                  key=lambda r: (r["trip_id"], int(r["stop_seq"])))
    for tid, grp in itertools.groupby(rows, key=lambda r: r["trip_id"]):
        g = list(grp)
        for i, s in enumerate(g):
            kind = "origin" if i == 0 else ("destination" if i == len(g) - 1 else "stop")
            sec = int(s["dep_sec"])
            cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                        ("IC1#" + tid, int(s["stop_seq"]), icm[s["stop_id"]],
                         sec if kind == "destination" else None,
                         None if kind == "destination" else sec, kind))
    for r in rd(f"{OUT_INCHEON1}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 공항철도(AREX, 비코레일) — 서울·공덕·홍대입구·디지털미디어시티·
    #     김포공항·계양에서 기존 노선과 실제 환승역으로 자동 병합. 수색직결선은
    #     실제 정차역이 아니라 선로 연결 지점이라 junctions로 분리 ---
    cur.execute("INSERT INTO junctions VALUES(?,?)", ("@수색직결선", "수색직결선"))
    arm = {r["stop_id"]: add(r["name_ko"], LINE_OF["AREX"])
           for r in rd(f"{OUT_AIRPORT_RAILROAD}/stops.csv")}
    for t in rd(f"{OUT_AIRPORT_RAILROAD}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("AR#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], arm.get(t["origin"], t["origin"]),
                     arm.get(t["destination"], t["destination"]), t["next_train_no"], "AREX"))
    for st in rd(f"{OUT_AIRPORT_RAILROAD}/stop_times.csv"):
        cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                    ("AR#" + st["trip_id"], int(st["stop_seq"]),
                     arm.get(st["stop_id"], st["stop_id"]),
                     int(st["arr_sec"]) if st["arr_sec"] else None,
                     int(st["dep_sec"]) if st["dep_sec"] else None, st["stop_type"]))
    for r in rd(f"{OUT_AIRPORT_RAILROAD}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 김포골드라인(비코레일, 웹크롤링 소스) — "역당 시각 1개" 구조라 KTX와
    #     같은 해석 규칙. 김포공항에서 공항철도·5·9호선·서해선(전동)과 실제
    #     환승역으로 자동 병합 ---
    ggm = {r["stop_id"]: add(r["name_ko"], LINE_OF["GIMPO_GOLDLINE"],
                             merge_key=r.get("merge_key") or None)
           for r in rd(f"{OUT_GIMPO_GOLDLINE}/stops.csv")}
    for t in rd(f"{OUT_GIMPO_GOLDLINE}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("GGL#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], ggm[t["origin"]], ggm[t["destination"]],
                     "", "GIMPO_GOLDLINE"))
    rows = sorted(rd(f"{OUT_GIMPO_GOLDLINE}/stop_times.csv"),
                  key=lambda r: (r["trip_id"], int(r["stop_seq"])))
    for tid, grp in itertools.groupby(rows, key=lambda r: r["trip_id"]):
        g = list(grp)
        for i, s in enumerate(g):
            kind = "origin" if i == 0 else ("destination" if i == len(g) - 1 else "stop")
            sec = int(s["dep_sec"])
            cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                        ("GGL#" + tid, int(s["stop_seq"]), ggm[s["stop_id"]],
                         sec if kind == "destination" else None,
                         None if kind == "destination" else sec, kind))
    for r in rd(f"{OUT_GIMPO_GOLDLINE}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 신림선(남서울경전철, 비코레일, 웹크롤링 소스) — "역당 시각 1개" 구조라
    #     김포골드라인과 같은 해석 규칙. 신림(2호선)·보라매(7호선)·샛강(9호선)에서
    #     실제 환승역으로 자동 병합, 대방(성애병원)은 1호선 '대방'과 merge_key로 병합 ---
    slm = {r["stop_id"]: add(r["name_ko"], LINE_OF["SILLIM"],
                             merge_key=r.get("merge_key") or None)
           for r in rd(f"{OUT_SILLIM}/stops.csv")}
    for t in rd(f"{OUT_SILLIM}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("SL#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], slm[t["origin"]], slm[t["destination"]],
                     "", "SILLIM"))
    rows = sorted(rd(f"{OUT_SILLIM}/stop_times.csv"),
                  key=lambda r: (r["trip_id"], int(r["stop_seq"])))
    for tid, grp in itertools.groupby(rows, key=lambda r: r["trip_id"]):
        g = list(grp)
        for i, s in enumerate(g):
            kind = "origin" if i == 0 else ("destination" if i == len(g) - 1 else "stop")
            sec = int(s["dep_sec"])
            cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                        ("SL#" + tid, int(s["stop_seq"]), slm[s["stop_id"]],
                         sec if kind == "destination" else None,
                         None if kind == "destination" else sec, kind))
    for r in rd(f"{OUT_SILLIM}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 우이신설선(우이신설경전철, 비코레일, 웹크롤링 소스) — "역당 시각 1개"
    #     구조라 신림선과 같은 해석 규칙. 성신여대입구(안산과천선)·보문(6호선)·
    #     신설동(1호선)에서 실제 환승역으로 자동 병합 ---
    uim = {r["stop_id"]: add(r["name_ko"], LINE_OF["UI_SINSEOL"],
                             merge_key=r.get("merge_key") or None)
           for r in rd(f"{OUT_UI_SINSEOL}/stops.csv")}
    for t in rd(f"{OUT_UI_SINSEOL}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("UI#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], uim[t["origin"]], uim[t["destination"]],
                     "", "UI_SINSEOL"))
    rows = sorted(rd(f"{OUT_UI_SINSEOL}/stop_times.csv"),
                  key=lambda r: (r["trip_id"], int(r["stop_seq"])))
    for tid, grp in itertools.groupby(rows, key=lambda r: r["trip_id"]):
        g = list(grp)
        for i, s in enumerate(g):
            kind = "origin" if i == 0 else ("destination" if i == len(g) - 1 else "stop")
            sec = int(s["dep_sec"])
            cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                        ("UI#" + tid, int(s["stop_seq"]), uim[s["stop_id"]],
                         sec if kind == "destination" else None,
                         None if kind == "destination" else sec, kind))
    for r in rd(f"{OUT_UI_SINSEOL}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- GTX-A(에스지레일, 비코레일, 웹크롤링 소스) — 운정중앙~서울역(L08)·
    #     수서~동탄(L09) 두 구간이 물리적으로 분리 운행이라 별개 line_name으로
    #     등록. "역당 시각 1개" 구조라 김포골드라인과 같은 해석 규칙. 대곡·연신내·
    #     수서·성남·구성·동탄은 기존 노선과 실제 환승역으로 자동 병합, 서울역은
    #     표기가 달라 merge_key로 기존 '서울'과 명시적 병합. 평일만 반영(휴일
    #     dayTypeCode 조회 결과 빈 리스트 — 아직 미공개) ---
    for out_dir, line_key, tag in [(OUT_GTXA_L08, "GTXA_L08", "GTXA_L08"),
                                     (OUT_GTXA_L09, "GTXA_L09", "GTXA_L09")]:
        gam = {r["stop_id"]: add(r["name_ko"], LINE_OF[line_key],
                                  merge_key=r.get("merge_key") or None)
               for r in rd(f"{out_dir}/stops.csv")}
        for t in rd(f"{out_dir}/trips.csv"):
            cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (f"{tag}#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                         t["direction"], t["service_id"], gam[t["origin"]], gam[t["destination"]],
                         "", tag))
        rows = sorted(rd(f"{out_dir}/stop_times.csv"),
                      key=lambda r: (r["trip_id"], int(r["stop_seq"])))
        for tid, grp in itertools.groupby(rows, key=lambda r: r["trip_id"]):
            g = list(grp)
            for i, s in enumerate(g):
                kind = "origin" if i == 0 else ("destination" if i == len(g) - 1 else "stop")
                sec = int(s["dep_sec"])
                cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                            (f"{tag}#" + tid, int(s["stop_seq"]), gam[s["stop_id"]],
                             sec if kind == "destination" else None,
                             None if kind == "destination" else sec, kind))
        for r in rd(f"{out_dir}/calendar.csv"):
            cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                        (r["service_id"], r["mon"], r["tue"], r["wed"],
                         r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 광주 도시철도 1호선(광주교통공사, 비코레일, 웹크롤링 소스) — "역당 시각
    #     1개" 구조라 김포골드라인과 같은 해석 규칙. 광주송정역은 KTX·일반열차
    #     '광주송정'과 실제 환승역이라 merge_key로 병합, 화정·운천은 수도권
    #     노선(일산선·경의선)의 동명역과 무관해 merge_key로 분리. 평일/토요일/
    #     휴일/명절 4종 다이어 중 명절은 날짜기반이라 calendar에 요일 매핑 없음
    #     (calendar_dates류 예외 처리 필요, 다른 노선 캐비어트와 동일) ---
    gjm = {r["stop_id"]: add(r["name_ko"], LINE_OF["GWANGJU1"],
                             merge_key=r.get("merge_key") or None)
           for r in rd(f"{OUT_GWANGJU1}/stops.csv")}
    for t in rd(f"{OUT_GWANGJU1}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("GJ1#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], SUN_ONLY_LABEL(t["service_id"]), gjm[t["origin"]], gjm[t["destination"]],
                     "", "GWANGJU1"))
    rows = sorted(rd(f"{OUT_GWANGJU1}/stop_times.csv"),
                  key=lambda r: (r["trip_id"], int(r["stop_seq"])))
    for tid, grp in itertools.groupby(rows, key=lambda r: r["trip_id"]):
        g = list(grp)
        for i, s in enumerate(g):
            kind = "origin" if i == 0 else ("destination" if i == len(g) - 1 else "stop")
            sec = int(s["dep_sec"])
            cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                        ("GJ1#" + tid, int(s["stop_seq"]), gjm[s["stop_id"]],
                         sec if kind == "destination" else None,
                         None if kind == "destination" else sec, kind))
    for r in rd(f"{OUT_GWANGJU1}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (SUN_ONLY_LABEL(r["service_id"]), r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 인천 도시철도 2호선(인천교통공사, 비코레일, 추정치 기반) — 공식 시각표
    #     미공개, 배차간격+역별 첫차/막차만으로 근사 생성(scripts/parse_incheon2.py,
    #     README "추정치 기반" 캐비어트 참조). 인천시청·검암·계양·석남에서 기존
    #     노선(인천1호선·공항철도·서울7호선)과 실제 환승역으로 자동 병합 ---
    ic2m = {r["stop_id"]: add(r["name_ko"], LINE_OF["INCHEON2"],
                              merge_key=r.get("merge_key") or None)
            for r in rd(f"{OUT_INCHEON2}/stops.csv")}
    for t in rd(f"{OUT_INCHEON2}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("IC2#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], ic2m[t["origin"]], ic2m[t["destination"]],
                     "", "INCHEON2"))
    rows = sorted(rd(f"{OUT_INCHEON2}/stop_times.csv"),
                  key=lambda r: (r["trip_id"], int(r["stop_seq"])))
    for tid, grp in itertools.groupby(rows, key=lambda r: r["trip_id"]):
        g = list(grp)
        for i, s in enumerate(g):
            kind = "origin" if i == 0 else ("destination" if i == len(g) - 1 else "stop")
            sec = int(s["dep_sec"])
            cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                        ("IC2#" + tid, int(s["stop_seq"]), ic2m[s["stop_id"]],
                         sec if kind == "destination" else None,
                         None if kind == "destination" else sec, kind))
    for r in rd(f"{OUT_INCHEON2}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 용인경전철(용인에버라인, 비코레일, 추정치 기반) — 인천2호선과 같은
    #     방식(배차간격+역별 첫차/막차 근사). 기흥은 수인분당선과 실제 환승역,
    #     동백은 부산2호선 동명역과 무관해 merge_key로 분리 ---
    yim = {r["stop_id"]: add(r["name_ko"], LINE_OF["YONGIN"],
                             merge_key=r.get("merge_key") or None)
           for r in rd(f"{OUT_YONGIN}/stops.csv")}
    for t in rd(f"{OUT_YONGIN}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("YI#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], yim[t["origin"]], yim[t["destination"]],
                     "", "YONGIN"))
    rows = sorted(rd(f"{OUT_YONGIN}/stop_times.csv"),
                  key=lambda r: (r["trip_id"], int(r["stop_seq"])))
    for tid, grp in itertools.groupby(rows, key=lambda r: r["trip_id"]):
        g = list(grp)
        for i, s in enumerate(g):
            kind = "origin" if i == 0 else ("destination" if i == len(g) - 1 else "stop")
            sec = int(s["dep_sec"])
            cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                        ("YI#" + tid, int(s["stop_seq"]), yim[s["stop_id"]],
                         sec if kind == "destination" else None,
                         None if kind == "destination" else sec, kind))
    for r in rd(f"{OUT_YONGIN}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 의정부경전철(비코레일) — 운영사 홈페이지 역별 시각표 이미지를 직접
    #     전사한 실측 데이터(인천2호선·용인경전철과 달리 배차간격 추정이
    #     아님). 경전철의정부는 표기가 달라 기존 '의정부'(일반열차·1호선)와
    #     merge_key로 명시적 병합, 회룡은 1호선과 이름이 같아 자동 병합 ---
    ujm = {r["stop_id"]: add(r["name_ko"], LINE_OF["UIJEONGBU"],
                             merge_key=r.get("merge_key") or None)
           for r in rd(f"{OUT_UIJEONGBU}/stops.csv")}
    for t in rd(f"{OUT_UIJEONGBU}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("UJ#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], ujm[t["origin"]], ujm[t["destination"]],
                     "", "UIJEONGBU"))
    rows = sorted(rd(f"{OUT_UIJEONGBU}/stop_times.csv"),
                  key=lambda r: (r["trip_id"], int(r["stop_seq"])))
    for tid, grp in itertools.groupby(rows, key=lambda r: r["trip_id"]):
        g = list(grp)
        for i, s in enumerate(g):
            kind = "origin" if i == 0 else ("destination" if i == len(g) - 1 else "stop")
            sec = int(s["dep_sec"])
            cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                        ("UJ#" + tid, int(s["stop_seq"]), ujm[s["stop_id"]],
                         sec if kind == "destination" else None,
                         None if kind == "destination" else sec, kind))
    for r in rd(f"{OUT_UIJEONGBU}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 신분당선(네오트랜스) — 평일은 PDF 역별 시각표, 휴일은 PNG(스크린샷)를
    #     Claude가 직접 읽어 전사. 강남·양재(3호선 계통)·신사(3호선)·판교(국철·
    #     경강선)·정자·미금(수인분당선)은 실제 환승역으로 이름 그대로 자동
    #     병합, 동천은 대구3호선 동명역과 무관해 merge_key로 분리 ---
    sinbm = {r["stop_id"]: add(r["name_ko"], LINE_OF["SINBUNDANG"],
                               merge_key=r.get("merge_key") or None)
             for r in rd(f"{OUT_SINBUNDANG}/stops.csv")}
    for t in rd(f"{OUT_SINBUNDANG}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("SBD#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], sinbm[t["origin"]], sinbm[t["destination"]],
                     "", "SINBUNDANG"))
    rows = sorted(rd(f"{OUT_SINBUNDANG}/stop_times.csv"),
                  key=lambda r: (r["trip_id"], int(r["stop_seq"])))
    for tid, grp in itertools.groupby(rows, key=lambda r: r["trip_id"]):
        g = list(grp)
        for i, s in enumerate(g):
            kind = "origin" if i == 0 else ("destination" if i == len(g) - 1 else "stop")
            sec = int(s["dep_sec"])
            cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                        ("SBD#" + tid, int(s["stop_seq"]), sinbm[s["stop_id"]],
                         sec if kind == "destination" else None,
                         None if kind == "destination" else sec, kind))
    for r in rd(f"{OUT_SINBUNDANG}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
                     r["thu"], r["fri"], r["sat"], r["sun"]))

    cur.executescript("""
    CREATE INDEX idx_st ON stop_times(stop_id, dep_sec);
    CREATE INDEX idx_tr ON stop_times(trip_id, stop_seq);
    CREATE INDEX idx_grp ON stops(group_id);
    """)
    cur.executemany("INSERT INTO meta VALUES(?,?)", [
        ("source_ktx", "한국철도공사 KTX 시각표"),
        ("source_line1", "수도권 전철 1호선 시각표 (평일/휴일, 경인급행 제외 — 아래 별도 소스로 대체)"),
        ("source_line1_gyeongin_express", "1호선 경인급행 시각표 (2026.5.26.부터, 1호선 원본보다 최신 개정판)"),
        ("source_suin_bundang", "수도권 전철 수인·분당선 시각표 (평일/휴일)"),
        ("source_ansan_gwacheon", "수도권 전철 4호선(안산과천선, 진접~오이도 전 구간 직결) 시각표 (평일/휴일)"),
        ("source_gyeongui_jungang", "수도권 전철 경의·중앙선 시각표 (문산~지평, 용산선 경유, 평일/휴일)"),
        ("source_gyeongui", "수도권 전철 경의선 시각표 (도라산~서울, 신촌 경유, 평일/휴일)"),
        ("source_gyeongchun", "수도권 전철 경춘선 시각표 (청량리~춘천, 광운대 연장편 포함, 평일/휴일)"),
        ("source_gyeonggang", "수도권 전철 경강선 시각표 (판교~여주, 평일/휴일)"),
        ("source_donghae", "동해선 광역전철 시각표 (부전~태화강, 부산·울산, 평일/휴일). "
                            "KTX·일반열차 파일에도 별개 실체의 동해선이 있어 line_name을 "
                            "'동해선(전동)'으로 구분함"),
        ("source_daegyeong", "대경선 시각표 (구미~경산, 대구권, 평일/휴일). "
                              "역 14개 중 6개(가천·고모·지천·신동·연화·약목)는 실재하는 "
                              "역이지만 대경선 열차가 통과만 함(공식 정차역은 8개)"),
        ("source_seoul3", "서울 지하철 3호선(오금~대화 전 구간 직결) 시각표 — 공식 CSV 소스(아래 "
                          "source_seoul_official 참조). 예전엔 '일산선'이라는 내부 이름으로만 "
                          "등록돼 있던 걸 이번에 '3호선'으로 정식 재정리함(같은 노선 범위)"),
        ("source_itx_chuncheon", "ITX-청춘 시각표 (용산~춘천, 여객열차, 평일/휴일). "
                                  "경의중앙선(용산~청량리)·경춘선(청량리~춘천)과 선로 공유"),
        ("source_seohae", "수도권 전철 서해선 시각표 (대곡~원시, 일산 연장편 포함, 평일/휴일). "
                           "일반열차 파일에도 서화성~홍성 구간의 별개 실체 '서해선'이 있어 "
                           "line_name을 '서해선(전동)'으로 구분함. 원본에 문산 방면(탄현~판문) "
                           "빈 꼬리 행이 붙어있었는데 시각 데이터가 전혀 없어 등록하지 않음"),
        ("source_ilban", "일반열차(무궁화·ITX-새마을·ITX-마음) 시각표, 15개 노선(경부선·호남선· "
                          "전라선·장항선·중앙선·경전선·충북선·목포보성선·동해선·대구선·영동선· "
                          "태백선·경북선·교외선·서해선). line_name에 '(일반)' 접미사로 KTX 동명 "
                          "시트와 구분. 원본 자체의 종착역 라벨 오류 등 데이터 이상치 소수 확인됨"),
        ("source_gwangwang", "관광열차(동해산타열차·백두대간협곡열차·남도해양열차 2계통· "
                              "서해금빛열차·정선아리랑열차) 시각표, 14개 편성. KTX·일반열차와 "
                              "같은 국철 선로라 '국철'로 등록. 운행요일은 요일구간(~)만 "
                              "calendar에 반영, 날짜기반 임시증편(장날 등)은 미반영"),
        ("source_daegu", "대구 도시철도 1/2/3호선(대구교통공사, 비코레일) 시각표 (평일/토요일/휴일, "
                         "2024.10.7 시행). 대구·동대구·서대구역에서만 대경선과 물리적 환승으로 자동 "
                         "병합, 나머지는 완전 별도 station_groups. 토요일 다이어가 평일/휴일과 별도로 "
                         "존재하는 첫 사례. 다른 호선과 동명인 역(반월당·청라언덕·명덕)은 원본에 자기 "
                         "호선 번호가 접미사로 붙어있어 벗겨서 정규화함"),
        ("source_daejeon1", "대전 도시철도 1호선(대전교통공사, 비코레일) 시각표 (평일/휴일, "
                            "2026.3.30 기준). 원본이 '출발역 기준 배차표'(열차 단위 컬럼 없음)라 "
                            "역간 시각 근접도로 열차 단위 trip을 복원함 — 정상 구간은 실제 관측 "
                            "시각 그대로지만, 종착역(판암/반석) 자체는 원본에 시각이 없어 직전 역 "
                            "관측시각 + 통상 역간격(2분) 근사치로 보정함. 대전역은 코레일 대전역과 "
                            "지하로 연결된 실제 환승역이라 자동 병합됨"),
        ("source_busan", "부산 도시철도 1/2/3/4호선(부산교통공사, 비코레일) 시각표 "
                         "(평일/토요일/휴일, 2026.8.24 이후 시행). 노선 내부 환승역(서면·동래· "
                         "연산·덕천·수영·미남)은 자동 병합. 동해선(전동)의 '교대'와 부산1호선 "
                         "'교대'가 실제 환승역이라 내부 merge_key를 공유해 병합됨(표시명은 "
                         "둘 다 그냥 '교대') — 이 발견으로 기존 동해선(전동) 등록이 서울 "
                         "일산선 '교대'와 잘못 섞여있던 것도 함께 고침. 중앙·시청·양정· "
                         "금곡·남산·중동은 수도권/대구 동명역과 무관해 내부 merge_key로만 "
                         "분리(화면 표시명은 그대로 '중앙' 등)"),
        ("source_busan_gimhae", "부산김해경전철(비코레일, 사상~가야대) 시각표 (평일/휴일, "
                                "2022.11.21 기준 — 부산 1~4호선보다 오래된 원본, 재확보 여지 "
                                "있음). 원본 역명에 전부 '역' 접미사가 붙어있어 벗겨서 등록 — "
                                "사상(부산2호선)·대저(부산3호선)에서 실제 환승역으로 자동 병합됨"),
        ("source_seoul_metro", "서울교통공사 2·7호선(비코레일 RAW 엑셀, 기존 유지) 시각표. "
                               "2호선은 순환선이라 direction이 상행/하행이 아니라 outer(외선)/ "
                               "inner(내선)이고 본선 43개 역만 포함(성수지선·신정지선은 "
                               "source_seoul_official 쪽에서 별도 반영). 평일/휴일이 완전히 "
                               "별개 파일로 배포되고 기준일 격차가 있다: 평일 2026.8.21 vs "
                               "휴일 2022.4/6(4년+ 차이) — 재확보 전까지 이 상태로 진행(사용자 "
                               "확인된 정책, 2호선·7호선은 새 공식 CSV보다 이 RAW가 더 최신이라 "
                               "판단해 안 바꿈, 2026-08-28). 원본마다 절삭·구역명 표기가 섞여있어 "
                               "(가산디지털→가산디지털단지, 총신대입구/이수→총신대입구(이수), "
                               "뚝섬유원지/자양→자양(뚝섬한강공원) 등) 최신 공식 표기로 통일함"),
        ("source_seoul_official", "서울교통공사 3·5·6·8·9호선 + 2호선 지선(성수지선·신정지선) "
                                  "시각표 — 공공데이터포털 '서울교통공사_서울 도시철도 "
                                  "열차운행시각표_20260616' CSV(433,996행, scripts/"
                                  "parse_seoul_official.py + parse_seoul2_branch.py). 기존 "
                                  "RAW 엑셀(열차=행/역=열)과 달리 '역 하나당 그 역을 지나는 "
                                  "모든 열차' 구조라 (호선,주중주말,방향,열차코드)로 묶어 트립을 "
                                  "역추적함 — 급행 통과역은 행 자체가 없어(빈 시각 칸이 아니라) "
                                  "stop_type이 전부 origin/destination/stop뿐. 주중주말이 "
                                  "DAY/SAT/END(평일/토요일/휴일) 3종이라 대구·부산·광주1호선과 "
                                  "같은 SUN_ONLY_LABEL 처리 적용. 1·2(본선)·4·7호선은 기존 데이터가 "
                                  "더 최신이라 판단해 이 CSV로 안 바꿈(사용자 확인, 2026-08-28). "
                                  "9호선 완행(C계열)은 old(2024-03-30 RAW)와 대조해 247/260 트립 "
                                  "완전 동일·13건만 초 단위 미세 조정으로 검증됨. 9호선 급행(E계열) "
                                  "은 232건 전부 정차 패턴 자체가 달라졌는데(예: 정차역 26→12개) "
                                  "일부만이 아니라 급행 전체가 깨끗하게 갈려 실제 다이어 개정으로 "
                                  "판단, 최신 데이터 그대로 채택함"),
        ("source_incheon1", "인천 도시철도 1호선(인천교통공사, 비코레일) 시각표. 원본이 `.xls`(구버전 "
                            "바이너리)라 openpyxl이 못 열어 xlrd로 읽음(프로젝트 최초 xlrd 의존성). "
                            "평일/토휴일 2종 — 토요일과 휴일을 하나로 묶은 다이어라 대구·부산과 달리 "
                            "별도 토요일 다이어가 없음. 부평(1호선)·부평구청(7호선)·계양(공항철도)에서 "
                            "실제 환승역으로 자동 병합"),
        ("source_airport_railroad", "공항철도(AREX, 비코레일) 시각표. 서울·공덕·홍대입구· "
                                    "디지털미디어시티·김포공항·계양에서 기존 노선과 실제 환승역으로 "
                                    "자동 병합. '수색직결선'은 원본에 '---'로 통과 표시된 선로 연결 "
                                    "지점이라 실제 정차역이 아니라 junctions로 분리. '지상서울'· "
                                    "'수색'은 원본에 자리는 있지만 평일·휴일·양방향 전부 실제 정차 "
                                    "기록 0건(경의선 '도라산'과 같은 부류 — 운행 미사용 구간으로 추정)"),
        ("source_sillim", "신림선(남서울경전철, 비코레일) 시각표. 운영사가 엑셀을 배포하지 "
                          "않아 공식 홈페이지(sillimlrt.com, https 인증서 깨져있어 http로만 "
                          "접속됨)의 역별 페이지 11개를 크롤링. 원본이 '역별 발차시각' "
                          "구조라 김포골드라인과 같은 해석 규칙(역당 시각 1개, 종착역만 "
                          "도착시각). 분(分) 단위 정밀도만 제공(초 단위 없음). 신림(2호선)· "
                          "보라매(7호선)·샛강(9호선)에서 실제 환승역으로 자동 병합, "
                          "대방(성애병원)은 1호선 '대방'과 merge_key로 병합(부제만 다름). "
                          "괄호 등 목적지 분기 표기 없음(전 역 확인, 단일 종점 노선)"),
        ("source_ui_sinseol", "우이신설선(우이신설경전철, 비코레일) 시각표. 운영사가 엑셀을 "
                              "배포하지 않아 공식 홈페이지(ui-line.com)의 역별 페이지 13개를 "
                              "크롤링. 역 링크가 `javascript:f_route()` 형태였지만 실제로는 "
                              "단순 페이지 이동이라 curl 정적 GET으로 확보(브라우저 자동화 "
                              "불필요). 원본이 '역당 시각 1개' 구조라 신림선과 같은 해석 규칙, "
                              "분(分) 단위 정밀도만 제공. daytype이 평일/주말 2종뿐(토요일 "
                              "별도 없음). 성신여대입구(안산과천선)·보문(6호선)·신설동(1호선)"
                              "에서 실제 환승역으로 자동 병합. 목적지 분기 표기 없음(전 역 확인)"),
        ("source_gtxa", "GTX-A(에스지레일, 비코레일) 시각표. 공식 홈페이지(gtx-a.com)는 "
                        "curl 등 자동화 도구 User-Agent를 차단하지만, 시각표를 채우는 내부 "
                        "API(`/trainTimeTable.do`)는 일반 User-Agent+Referer만으로 curl "
                        "응답이 그대로 와서 브라우저 자동화 없이 9개 역 데이터 확보(정찰 "
                        "단계에서만 브라우저로 API 경로를 확인함). 운정중앙~서울역(L08, "
                        "5개 역)·수서~동탄(L09, 4개 역) 두 구간이 물리적으로 분리 운행 "
                        "중이라 line_name을 구분해 등록. dayTypeCode=2(휴일) 조회 결과가 "
                        "빈 리스트라 휴일 시각표는 아직 미공개로 판단, 평일만 반영. 대곡· "
                        "연신내·수서·성남·구성·동탄은 기존 노선과 실제 환승역으로 자동 "
                        "병합, 서울역은 표기가 달라 merge_key로 기존 '서울'과 명시적 병합"),
        ("source_gwangju1", "광주 도시철도 1호선(광주교통공사, 비코레일) 시각표. 공식 "
                            "사이버스테이션(grtc.co.kr/cyber)에서 역별 '열차시각표' 탭의 "
                            "DOM(class=pd/nd, 평일/토요일/휴일/명절 4종 다이어)을 직접 읽어 "
                            "20개 역 전부 확보. 원본이 '역당 시각 1개' 구조라 김포골드라인과 "
                            "같은 해석 규칙, 분(分) 단위 정밀도만 제공. 대부분 열차는 소태에서 "
                            "종착하고 일부만 녹동까지 연장 운행 — 사이버스테이션이 이 분기를 "
                            "이미 CSS class로 표시해 둬(색상 정보를 따로 파싱할 필요 없이) "
                            "재구성 시 그대로 반영했다. 광주송정역은 KTX·일반열차 '광주송정'과 "
                            "실제 환승역이라 merge_key로 병합, 화정·운천은 수도권 노선(일산선· "
                            "경의선)의 동명역과 무관해 merge_key로 분리. 명절 다이어는 요일이 "
                            "아니라 날짜 기반이라 calendar에 매핑 못 함(calendar_dates류 예외 "
                            "처리 필요, 다른 노선 캐비어트와 동일)"),
        ("caveat_sun_only_calendar", "평일/토요일/휴일 3종 다이어 노선(대구·부산·광주1호선)의 "
                                     "'휴일'은 일요일 전용인데, 국철·1호선 등 2종 다이어(평일/ "
                                     "휴일=토+일) 노선의 '휴일'과 이름이 같아 그대로 두면 먼저 "
                                     "INSERT된 쪽에 덮여써 실제로는 항상 토+일 취급되고 있었다 "
                                     "(2026-08-26, 광주1호선 반영 중 발견) — build_db.py의 "
                                     "SUN_ONLY_LABEL()로 이 3개 노선의 '휴일'만 '휴일(일요일)'로 "
                                     "분리해 고쳤다. 대구·부산도 이 커밋부터 정상화됨(기존 "
                                     "trips 데이터 자체는 안 바뀌었고 calendar 매핑만 정정됨)"),
        ("source_incheon2", "인천 도시철도 2호선(인천교통공사) 시각표 — **추정치 기반**. "
                            "공식 사이트가 분 단위 상세 시각표를 공개하지 않아(배차간격표+ "
                            "역별 첫차/막차만 공개), `scripts/_headway_estimate.py`로 배차 "
                            "간격 기반 근사 시각표를 생성했다(막차 기준 오프셋으로 평행이동, "
                            "첫차는 그 역의 실제 값으로 스냅). 인천시청·검암·계양·석남에서 "
                            "기존 노선(인천1호선·공항철도·서울7호선)과 실제 환승역으로 자동 "
                            "병합. 노선 중간에 단축운행 시발역이 여러 곳 있다는 걸 확인했으나 "
                            "그 역들의 추가 배차까지는 복원하지 못함(추정치 근본 한계)"),
        ("source_yongin", "용인경전철(용인에버라인㈜) 시각표 — **추정치 기반**, 인천2호선과 "
                          "같은 방법론(배차간격+역별 첫차/막차 근사, 요일별 첫차/막차 값은 "
                          "공개 안 돼 있어 하나만 사용, 배차간격만 평일/휴일 구분). 기흥은 "
                          "수인분당선과 실제 환승역으로 자동 병합, 동백은 부산2호선 동명역과 "
                          "무관해 merge_key로 분리"),
        ("caveat_estimation", "인천2호선·용인경전철은 실제 관측 시각표가 아니라 배차간격+ "
                              "첫차/막차만으로 재구성한 근사치다. 실제 열차 도착시각과 몇 분 "
                              "단위로 어긋날 수 있고, 노선 중간의 단축운행(구간운행) 열차는 "
                              "반영되지 않는다 — 진행바 등 정밀 UI에는 부적합, '대략적인 배차 "
                              "안내' 용도로만 사용할 것"),
        ("source_uijeongbu", "의정부경전철(비코레일) 시각표 — 운영사(ulrt.co.kr)가 엑셀을 "
                            "배포하지 않아 역별 시각표 이미지(jpg) 29장을 직접 육안 전사(분 "
                            "단위 정밀도, 인천2호선·용인경전철과 달리 배차간격 추정이 아니라 "
                            "실측 시각표). 광주1호선의 소태/녹동 분기와 같은 구조(대부분 열차는 "
                            "탑석에서 종착하고 일부만 차량기지임시승강장까지 연장) — 원본 "
                            "이미지에 이 연장 열차가 다른 색으로 표시돼 있었으나 재구성에는 "
                            "색상 대신 광주1호선과 동일한 이중 FIFO 재매칭 방식을 그대로 "
                            "재사용했다(색상 플래그는 참고용으로만 원본 텍스트에 보존). "
                            "경전철의정부는 표기가 달라 기존 '의정부'(일반열차·1호선)와 "
                            "merge_key로 명시적 병합, 회룡은 1호선과 이름이 같아 자동 병합. "
                            "평일/휴일(토+일) 2종 다이어만 존재"),
        ("source_sinbundang", "신분당선(네오트랜스) 시각표 — 계획 문서 8단계(마지막), RAW에 "
                              "xlsx가 없다. 평일은 PDF(16개 역, 역당 1페이지, pdfplumber로 "
                              "직접 파싱)이고 휴일은 PNG(843x9537 세로 스크린샷)라 Claude가 "
                              "직접 8등분해 읽어 전사했다 — 평일/휴일 기준일이 2.5년 이상 "
                              "차이난다(2025-01 vs 2022-05). 역간 간격이 균일하지 않아(청계산"
                              "입구~판교만 6~7분, 나머지는 1~4분, 최소 배차간격 4분) 공유 "
                              "link_trips()의 단일 max_hop 대신 이 노선 전용으로 구간별 다른 "
                              "max_hop을 쓰는 재구성 로직을 별도로 작성했다. 정자 단축종착 "
                              "분기(하행 전용, 원본에 '(정자)' 표시)는 판교까지는 정상 재구성한 "
                              "뒤 표시된 것만 정자에서 확정 종착시키는 방식으로 처리. 정자역은 "
                              "일부 열차의 실제 중간 시발점(정자 자체 하행 기록이 판교보다도 "
                              "이른 시각을 포함)임을 데이터에서 확인. 강남·양재(3호선 계통)·"
                              "신사(3호선)·판교(국철·경강선)·정자·미금(수인분당선)은 실제 "
                              "환승역으로 자동 병합, 동천은 대구3호선 동명역과 무관해 "
                              "merge_key로 분리"),
        ("station_model", "stops=노선별 승강장(수원(1호선) 등) / station_groups=역사(수원). 계통은 분리하지 않음."),
        ("station_merge_key", "여러 운영기관을 섞기 시작하면서(대구·대전·부산 등) 서로 무관한 "
                              "지역에 우연히 같은 역명이 존재하는 경우(예: 충남 논산 '연산' vs "
                              "부산 '연산', 서울 vs 대구 vs 부산의 '교대')가 실제로 나타났다. "
                              "이 경우 station_groups.name_ko/stops.name_ko는 항상 깨끗한 "
                              "역명 그대로 두고(사용자 화면에 지역 접두사가 노출되지 않음), "
                              "병합 여부만 파서 내부의 merge_key로 결정한다(예: '부산교대' — "
                              "이 값은 DB에 저장되지 않고 build_db.py 빌드 시에만 쓰이는 내부 "
                              "키). 같은 이름이지만 다른 역인 경우 서로 다른 merge_key를 줘서 "
                              "분리하고, 실제 환승역인 경우 두 파서가 같은 merge_key를 공유해 "
                              "병합한다. 노선 추가할 때마다 빌드 후 '복수 노선 역사' 목록을 "
                              "전수 점검해 확정한다."),
        ("caveat", "KTX 원본은 역당 시각 1개 — 중간역 arr_sec 없음"),
        ("caveat_holiday", "휴일 다이어는 토·일에만 자동 적용. 공휴일은 calendar_dates 예외 필요."),
    ])
    con.commit()

    n = lambda t: cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"stops {n('stops')} / groups {n('station_groups')} / "
          f"trips {n('trips')} / stop_times {n('stop_times')}")
    print("복수 노선 역사:")
    for r in cur.execute("""SELECT g.name_ko, GROUP_CONCAT(s.display_name)
                            FROM station_groups g JOIN stops s ON s.group_id=g.group_id
                            GROUP BY g.group_id HAVING COUNT(*)>1"""):
        print(f"   {r[0]:8s} = {r[1]}")
    con.close()


if __name__ == "__main__":
    main()
