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
OUT_ILSAN = "tmp/out_ilsan"
OUT_ITX_CHUNCHEON = "tmp/out_itx_chuncheon"
OUT_SEOHAE = "tmp/out_seohae"
OUT_ILBAN = "tmp/out_ilban"
OUT_GWANGWANG = "tmp/out_gwangwang"
OUT_DAEGU = ["tmp/out_daegu1", "tmp/out_daegu2", "tmp/out_daegu3"]
OUT_DAEJEON1 = "tmp/out_daejeon"
DB = sys.argv[1] if len(sys.argv) > 1 else "output/kr_rail_timetable.sqlite"

# 노선 단위로 승강장을 나눈다. 계통(경인/경부장항 등)은 나누지 않는다.
LINE_OF = {"KTX": "국철", "LINE1": "1호선", "SUIN_BUNDANG": "수인분당선",
           "ANSAN_GWACHEON": "안산과천선", "GYEONGUI_JUNGANG": "경의중앙선",
           "GYEONGUI": "경의선", "GYEONGCHUN": "경춘선", "GYEONGGANG": "경강선",
           "DONGHAE": "동해선(전동)", "DAEGYEONG": "대경선", "ILSAN": "일산선",
           "ITX_CHUNCHEON": "ITX-청춘", "SEOHAE": "서해선(전동)",
           "DAEGU1": "대구1호선", "DAEGU2": "대구2호선", "DAEGU3": "대구3호선",
           "DAEJEON1": "대전1호선"}
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

    def gid(gname):
        if gname not in groups:
            groups[gname] = f"G{len(groups)+1:04d}"
            cur.execute("INSERT INTO station_groups VALUES(?,?)", (groups[gname], gname))
        return groups[gname]

    def add(raw_name, line, hanja="", eng=""):
        """노선별로 별개 승강장을 만들고, 같은 역명은 하나의 역사 그룹으로 묶는다."""
        base = UNSPLIT.get(raw_name, raw_name)
        key = (base, line)
        if key in name2id:
            return name2id[key]
        sid = f"KR{len(name2id)+1:04d}"
        name2id[key] = sid
        cur.execute("INSERT INTO stops VALUES(?,?,?,?,?,?)",
                    (sid, f"{base}({line})", base, line, hanja or "", gid(base)))
        return sid

    def rd(path):
        return csv.DictReader(open(path, encoding="utf-8-sig"))

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
    ibm = {r["stop_id"]: add(r["name_ko"], LINE_OF["KTX"], r["name_hanja"])
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
    dhm = {r["stop_id"]: add(r["name_ko"], LINE_OF["DONGHAE"])
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

    # --- 일산선(3호선 오금~대화 전 구간 직결, 평일/휴일 한 파일에 같이 있음) ---
    ism = {r["stop_id"]: add(r["name_ko"], LINE_OF["ILSAN"])
           for r in rd(f"{OUT_ILSAN}/stops.csv")}
    for t in rd(f"{OUT_ILSAN}/trips.csv"):
        cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("IS#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                     t["direction"], t["service_id"], ism.get(t["origin"], t["origin"]),
                     ism.get(t["destination"], t["destination"]), t["next_train_no"], "ILSAN"))
    for st in rd(f"{OUT_ILSAN}/stop_times.csv"):
        cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                    ("IS#" + st["trip_id"], int(st["stop_seq"]),
                     ism.get(st["stop_id"], st["stop_id"]),
                     int(st["arr_sec"]) if st["arr_sec"] else None,
                     int(st["dep_sec"]) if st["dep_sec"] else None, st["stop_type"]))
    for r in rd(f"{OUT_ILSAN}/calendar.csv"):
        cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                    (r["service_id"], r["mon"], r["tue"], r["wed"],
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
    #     서대구역)만 대경선과 자동 병합, 나머지는 완전 별도 station_groups ---
    for i, out_dir in enumerate(OUT_DAEGU, start=1):
        line_key = f"DAEGU{i}"
        dgm = {r["stop_id"]: add(r["name_ko"], LINE_OF[line_key])
               for r in rd(f"{out_dir}/stops.csv")}
        for t in rd(f"{out_dir}/trips.csv"):
            cur.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (f"DG{i}#" + t["trip_id"], t["train_no"], t["line_name"], t["formation"],
                         t["direction"], t["service_id"], dgm.get(t["origin"], t["origin"]),
                         dgm.get(t["destination"], t["destination"]), t["next_train_no"], line_key))
        for st in rd(f"{out_dir}/stop_times.csv"):
            cur.execute("INSERT INTO stop_times VALUES(?,?,?,?,?,?)",
                        (f"DG{i}#" + st["trip_id"], int(st["stop_seq"]),
                         dgm.get(st["stop_id"], st["stop_id"]),
                         int(st["arr_sec"]) if st["arr_sec"] else None,
                         int(st["dep_sec"]) if st["dep_sec"] else None, st["stop_type"]))
        for r in rd(f"{out_dir}/calendar.csv"):
            cur.execute("INSERT OR IGNORE INTO calendar VALUES(?,?,?,?,?,?,?,?)",
                        (r["service_id"], r["mon"], r["tue"], r["wed"],
                         r["thu"], r["fri"], r["sat"], r["sun"]))

    # --- 대전 1호선(대전교통공사, 비코레일) — "출발역 기준 배차표" 원본이라
    #     역당 시각 1개(KTX와 같은 해석 규칙: 종착역만 도착시각) ---
    djm = {r["stop_id"]: add(r["name_ko"], LINE_OF["DAEJEON1"])
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
        ("source_ilsan", "일산선(서울 지하철 3호선 오금~대화 전 구간 직결) 시각표 (평일/휴일, "
                          "2022.8.1.부터 원본 — 게시판에서 확인 가능한 최신본이나 다른 노선보다 오래됨)"),
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
        ("station_model", "stops=노선별 승강장(수원(1호선) 등) / station_groups=역사(수원). 계통은 분리하지 않음."),
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
