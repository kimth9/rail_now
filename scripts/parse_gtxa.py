#!/usr/bin/env python3
"""GTX-A(에스지레일, 비코레일) 시각표 -> 정규화 테이블

RAW 원본 파일이 없다(운영사가 엑셀을 배포하지 않음) — 공식 홈페이지
(gtx-a.com)는 curl 등 자동화 도구의 User-Agent를 감지해 홈페이지
자체는 차단하지만("PAGE BLOCK"), 실제 시각표를 채우는 내부 API
(`/trainTimeTable.do?stNo=X101&lineCd=L08&dayTypeCode=1`)는 일반
User-Agent + Referer만 실어 보내면 curl로도 그대로 응답한다 — 브라우저
자동화는 이 API 엔드포인트를 찾는 정찰(역 목록·JS 로직 확인) 단계에서만
썼고, 실제 9개 역 데이터 수집은 curl로 끝났다. 응답 JSON을
`RAW/web_크롤링/GTX-A/L08_X1xx.json` / `L09_X1xx.json`으로 저장해둔 걸
읽는다.

GTX-A는 운정중앙~서울역(L08)과 수서~동탄(L09) 두 구간이 물리적으로
분리 운행(중간 구간 미개통)이라 line_name을 구분해 등록한다(동해선
(전동)과 같은 접미사 관행). dayTypeCode는 1(평일)만 실제 데이터가 있고
2(휴일)는 빈 리스트만 반환됨을 확인 — 아직 휴일 시각표가 공개되지
않은 것으로 보고 평일만 반영, 휴일 캐비어트를 남긴다.

원본이 김포골드라인·신림선·우이신설선과 같은 "역별 발차 시각 목록"
구조(역마다 UP_TIME_N/DN_TIME_N 분 목록만 있고 열차 단위 컬럼이 없음)
라 `_station_list_reconstruct.link_trips()`로 열차 단위 trip을 복원한다.
목적지 분기 표기(괄호 등)는 전 역에서 관찰되지 않았다.
"""
import csv
import json
import os
import sys
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(__file__))
from _station_list_reconstruct import link_trips

SRC_DIR = sys.argv[1] if len(sys.argv) > 1 else "RAW/web_크롤링/GTX-A"
OUT_L08 = sys.argv[2] if len(sys.argv) > 2 else "tmp/out_gtxa_l08"
OUT_L09 = sys.argv[3] if len(sys.argv) > 3 else "tmp/out_gtxa_l09"

# (stNo, 역명) — L08: 운정중앙~서울역, L09: 수서~동탄 (물리적으로 분리 운행)
L08_STATIONS = [("X101", "운정중앙"), ("X102", "킨텍스"), ("X103", "대곡"),
                 ("X105", "연신내"), ("X106", "서울역")]
L09_STATIONS = [("X108", "수서"), ("X109", "성남"), ("X110", "구성"),
                 ("X111", "동탄")]

MAX_HOP_MIN = 8
ESTIMATED_LAST_HOP_MIN = 3

# 서울역(GTX-A 공식 역명)은 기존 "서울"(1호선·경의선·공항철도 등, 실제 같은 역사)과
# 표기가 달라 자동 병합되지 않으므로 merge_key로 명시 병합. 나머지는 이름이 그대로
# 같아 자동 병합(대곡·연신내·수서·성남·구성·동탄) 또는 신규 단독역(운정중앙·킨텍스).
MERGE_KEY = {"서울역": "서울"}


def load(stno, line_cd):
    with open(f"{SRC_DIR}/{line_cd}_{stno}.json", encoding="utf-8-sig") as f:
        data = json.load(f)
    up, dn = [], []
    for row in data["list"]:
        hour = int(row["HH_SORT"])
        for k, bucket in (("UP_TIME_N", up), ("DN_TIME_N", dn)):
            txt = (row.get(k) or "").strip()
            if txt:
                bucket += [hour * 60 + int(m) for m in txt.split()]
    return sorted(up), sorted(dn)


def build(stations, line_cd, line_id, line_name, out_dir):
    per_station = {name: load(stno, line_cd) for stno, name in stations}

    stops = OrderedDict()
    for _stno, name in stations:
        stops[name] = f"{line_cd}{len(stops) + 1:04d}"

    trips, stop_times = [], []

    def process(direction, terminus, names, col, daytype_label):
        blocks = [(name, per_station[name][col]) for name in names]
        blocks = [(name, times) for name, times in blocks if times]
        if len(blocks) < 2:
            return
        chains = link_trips(blocks, MAX_HOP_MIN)
        for ci, chain in enumerate(chains):
            if len(chain) < 2:
                continue
            full_run = chain[-1][0] == len(blocks) - 1
            trip_id = f"{direction}#{daytype_label}#{ci}"
            for seq, (block_idx, t) in enumerate(chain, start=1):
                stop_times.append({
                    "trip_id": trip_id, "stop_seq": seq,
                    "stop_id": stops[blocks[block_idx][0]],
                    "dep_sec": t * 60,
                })
            dest_name = blocks[chain[-1][0]][0]
            if full_run:
                stop_times.append({
                    "trip_id": trip_id, "stop_seq": len(chain) + 1,
                    "stop_id": stops[terminus],
                    "dep_sec": (chain[-1][1] + ESTIMATED_LAST_HOP_MIN) * 60,
                })
                dest_name = terminus
            trips.append({
                "trip_id": trip_id, "train_no": trip_id,
                "line_id": line_id, "line_name": line_name,
                "formation": "GTX", "direction": direction,
                "service_id": daytype_label,
                "origin": stops[blocks[chain[0][0]][0]],
                "destination": stops[dest_name],
                "next_train_no": "",
            })

    names = [n for _stno, n in stations]
    down_terminus = names[-1]
    up_terminus = names[0]
    process("down", down_terminus, names, 1, "평일")
    process("up", up_terminus, list(reversed(names)), 0, "평일")

    os.makedirs(out_dir, exist_ok=True)

    with open(f"{out_dir}/stops.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["stop_id", "name_ko", "merge_key"])
        for name, sid in stops.items():
            w.writerow([sid, name, MERGE_KEY.get(name, "")])

    with open(f"{out_dir}/trips.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(trips[0].keys()))
        w.writeheader()
        w.writerows(trips)

    with open(f"{out_dir}/stop_times.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["trip_id", "stop_seq", "stop_id", "dep_sec"])
        w.writeheader()
        w.writerows(stop_times)

    with open(f"{out_dir}/calendar.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["service_id", "mon", "tue", "wed", "thu", "fri", "sat", "sun"])
        w.writerow(["평일", 1, 1, 1, 1, 1, 0, 0])

    from collections import Counter
    print(f"[{line_name}] stops {len(stops)} / trips {len(trips)} "
          f"{dict(Counter((t['direction'], t['service_id']) for t in trips))} "
          f"/ stop_times {len(stop_times)}")


def main():
    build(L08_STATIONS, "L08", "GTXA_L08", "GTX-A(운정~서울)", OUT_L08)
    build(L09_STATIONS, "L09", "GTXA_L09", "GTX-A(수서~동탄)", OUT_L09)


if __name__ == "__main__":
    main()
