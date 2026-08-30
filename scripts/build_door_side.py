#!/usr/bin/env python3
"""stop_times의 각 정차(trip_id, stop_seq)마다 실제로 어느 쪽 문이 열리는지
stop_door_side 테이블로 계산해 얹는다. door_directions 다음 단계(3번째 레이어).

판정 방식(Tier A만 자동 계산):
  같은 물리역(group_id)에서, 이 열차를 추월할 수 있다고 확인된 노선(EVAC_SOURCE_LINES)의
  다른 열차가 stop_type='pass'로 통과하는 시각이 이 열차의 정차 시간(arr_sec~dep_sec) 안에
  들어오면 대피(evac_side) 상황으로 본다. 그 외(door_directions에 evac_side가 없거나,
  추월 열차가 애초에 통과역 기록을 안 남기는 노선 — KTX/무궁화/ITX-마음 등 Tier B)는
  평시(normal_side)로 고정한다.

door_directions에서 같은 (line_sheet, group_id, 방향)에 행이 1개뿐이면 그대로 쓴다(1단계).
방향까지 같은데 행이 2개 이상인 "진짜 다중행"(노선 분기·급행완행·종착 여부로 문방향이
갈리는 경우, 2026-08-30 확인 결과 31개 조합)은 MULTI_ROW_RULES에 등록된 조합만 trips/
stop_times의 기존 정보(종착 여부·목적지역·출발역·train_no 접두사·line_name)로 판정한다.
신호가 불충분한 조합(광운대 하행 종착 — 원본 자체가 '확인필요'/빈 값)만 잘못 채우는
것보다 비워두는 게 낫다는 원칙대로 계속 스킵한다.

이번 버전부터 stop_type='destination'(종착)도 판정 대상에 포함한다(기존엔 'stop'만 처리해
전 노선 통틀어 종착역 문방향이 한 번도 계산된 적이 없었음 — 의정부·광운대·온수·수락산 등
종착 여부로 갈리는 조합을 풀려면 필요해서 범위를 넓혔다). 종착역은 dep_sec가 원래 없으므로
arr_sec만 있으면 유효한 행으로 보고, 대피(Tier A) 판정 대상에서는 제외한다(정의상 대피는
'정차 중 추월'이라 종착 이후 상황과는 무관).
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


VALID_SIDES = {"왼쪽", "오른쪽"}

# 규칙 함수가 반환할 수 있는 특수값: "이 방향 키는 확실히 신뢰 불가라 최종 스킵" —
# 일반 None(= "이 키에선 판단 안 함, 다음 방향 키로 폴백해봐라")과 구분하기 위한 것.
# 예: 동두천 상행 종착은 원본 자체가 '확인필요'라 폴백 없이 그냥 비워야 하는데, 단순
# None을 쓰면 같은 역의 방향-무관 기본행(왼쪽/일반)으로 잘못 새서 이 sentinel이 필요했다
# (2026-08-31 실제로 이렇게 새고 있던 걸 발견).
SKIP = object()


def norm_direction(raw):
    """door_directions.direction(자유 텍스트) -> trips.direction('up'/'down') 정규화.
    괄호 설명이 붙은 값(예: '상행(중앙보훈병원 방면)')도 접두어만 보고 매칭한다.
    매칭 안 되는 값(외선순환 등 순환선 표기)은 원문 그대로 둔다 — 이번 세션 범위 밖."""
    if raw is None:
        return None
    if raw.startswith("상행"):
        return "up"
    if raw.startswith("하행"):
        return "down"
    return raw


# ---- MULTI_ROW_RULES: 방향까지 같은데 행이 2개 이상인 조합 판정 ----
# key: (line_sheet, group_id, norm_direction) — 방향 구분이 아예 없는 역은 direction=None.
# value: function(ctx) -> (normal_side, evac_side) | None (None이면 스킵)
# ctx = {"line_name", "train_no", "origin_name", "destination_name", "is_destination", "direction"}

def _by_line_name(mapping, default=None):
    def fn(ctx):
        return mapping.get(ctx["line_name"], default)
    return fn


def _by_train_no_prefix(mapping, default=None):
    def fn(ctx):
        return mapping.get(ctx["train_no"][:1], default)
    return fn


def _by_train_no_in(names, if_in, if_not):
    def fn(ctx):
        return if_in if ctx["train_no"] in names else if_not
    return fn


def _by_destination(names, if_in, if_not):
    def fn(ctx):
        return if_in if ctx["destination_name"] in names else if_not
    return fn


def _by_origin(names, if_in, if_not):
    def fn(ctx):
        return if_in if ctx["origin_name"] in names else if_not
    return fn


def _by_is_destination(if_dest, if_not):
    def fn(ctx):
        return if_dest if ctx["is_destination"] else if_not
    return fn


def _by_direction(if_up, if_down):
    def fn(ctx):
        return if_up if ctx["direction"] == "up" else if_down
    return fn


def _const(side):
    def fn(ctx):
        return side
    return fn


# 1호선 경인선 9역(동인천/제물포/주안/동암/부평/송내/부천/역곡/개봉) — 공통 패턴:
# 경인급행이면 왼쪽(급행), 아니면 오른쪽(일반).
_GYEONGIN_EXPRESS_RULE = _by_line_name({"1호선/경인급행": ("왼쪽", None)}, ("오른쪽", None))
_GYEONGIN_STATIONS = ["G0330", "G0332", "G0334", "G0336", "G0338", "G0340", "G0342", "G0344", "G0347"]

# 9호선 완행(C)/급행(E) — 급행은 대피 대상 아님(evac_side 없음), 완행은 추월당할 수 있음.
_LINE9_RULE = _by_train_no_prefix({"E": ("오른쪽", None), "C": ("오른쪽", "왼쪽")})

MULTI_ROW_RULES = {
    # 병점: 서동탄 지선 계통(line_name)이면 서동탄발/종착 쪽, 경부장항 계통이면 천안·신창행 쪽.
    ("1호선", "G0274", "up"): _by_line_name(
        {"1호선/서동탄-의정부": ("오른쪽", None)}, ("왼쪽", None)),
    ("1호선", "G0274", "down"): _by_line_name(
        {"1호선/서동탄-의정부": ("오른쪽", None)}, ("왼쪽", None)),

    # 구로: 경인/경인급행 계통이 한쪽, 나머지(경부장항·서동탄-의정부·광명셔틀)가 반대쪽
    # (상행/하행에서 좌우가 뒤바뀜 — 원본 4행 그대로 확인).
    ("1호선", "G0288", "up"): _by_line_name(
        {"1호선/경인": ("오른쪽", None), "1호선/경인급행": ("오른쪽", None)}, ("왼쪽", None)),
    ("1호선", "G0288", "down"): _by_line_name(
        {"1호선/경인": ("왼쪽", None), "1호선/경인급행": ("왼쪽", None)}, ("오른쪽", None)),

    # 신도림 상행: 경인급행만 오른쪽, 나머지 전부 왼쪽(일반/경부급행A).
    ("1호선", "G0289", "up"): _by_line_name(
        {"1호선/경인급행": ("오른쪽", None)}, ("왼쪽", None)),

    # 의정부 상행: 종착이면 오른쪽(원본 evac_side 칸에 '종착'이라는 상태값이 잘못 들어가
    # 있어 무시 — 방향값이 아님), 아니면 왼쪽(일반).
    ("1호선", "G0250", "up"): _by_is_destination(("오른쪽", None), ("왼쪽", None)),

    # 광운대 상행: 종착이면 오른쪽, 아니면 왼쪽(일반).
    ("1호선", "G0306", "up"): _by_is_destination(("오른쪽", None), ("왼쪽", None)),
    # 광운대 하행: '일반'(비종착)은 오른쪽(2026-08-31 사용자 확인). 종착 쪽은 원본 정상측
    # 값이 '확인필요'라는 상태 문자열이라 여전히 스킵(None).
    ("1호선", "G0306", "down"): _by_is_destination(SKIP, ("오른쪽", None)),

    # 5호선 강동 상행: 마천지선 출발(origin)이면 왼쪽, 그 외(본선/하남선)는 오른쪽.
    ("5호선", "G0617", "up"): _by_origin({"마천"}, ("왼쪽", None), ("오른쪽", None)),

    # 6호선 새절: door_directions엔 방향 구분이 없지만(direction=None) 실제로는 상행=응암행,
    # 하행=봉화산행으로 trips.direction과 정확히 대응돼 그걸로 판정.
    ("6호선", "G0638", None): _by_direction(("오른쪽", None), ("왼쪽", None)),

    # 7호선 온수/수락산: 종착이면 오른쪽, 아니면 왼쪽(일반).
    ("7호선", "G0345", None): _by_is_destination(("오른쪽", None), ("왼쪽", None)),
    ("7호선", "G1020", None): _by_is_destination(("오른쪽", None), ("왼쪽", None)),

    # 9호선 동작/마곡나루/가양: 완행(C)/급행(E) — 급행은 절대 대피 대상 아님.
    ("9호선", "G0429", None): _LINE9_RULE,
    ("9호선", "G0683", None): _LINE9_RULE,
    ("9호선", "G0685", None): _LINE9_RULE,
    # 9호선 신논현 상행(중앙보훈병원 방면) — 완행/급행으로 좌우가 갈림(대피 없음).
    ("9호선", "G0699", "up"): _by_train_no_prefix(
        {"E": ("오른쪽", None), "C": ("왼쪽", None)}),
}
for _gid in _GYEONGIN_STATIONS:
    MULTI_ROW_RULES[("1호선", _gid, None)] = _GYEONGIN_EXPRESS_RULE

# 2호선 신도림·성수: door_directions는 방향을 순환 방향 텍스트(외선순환/내선순환)나
# 지선 종점명(까치산발/신설동발)으로 적어놔 trips.direction('outer'/'inner'/'up'/'down')과
# 형식이 안 맞아 지금까지 전혀 매칭이 안 되고 있었다. 실측 대조 결과 지선 계통(신도림의
# up/down, 성수의 up/down)은 전부 "일반"과 같은 문방향을 쓰고, 본선 순환(outer/inner)의
# '종착'(stop_type='destination')일 때만 다르다는 게 확인돼(2026-08-31 사용자 확인) 아래처럼
# 정리된다. 지선의 시발역(stop_type='origin') 쪽은 원래 이 프로젝트 전체에서 어느 노선도
# 시발역 문방향을 계산하지 않으므로(이번 세션에서 새로 다룬 건 종착뿐) 범위 밖으로 둔다.
_SINDORIM_2 = _by_is_destination(("오른쪽", None), ("왼쪽", None))
MULTI_ROW_RULES[("2호선", "G0289", "outer")] = _SINDORIM_2
MULTI_ROW_RULES[("2호선", "G0289", "inner")] = _SINDORIM_2
MULTI_ROW_RULES[("2호선", "G0289", "down")] = _const(("왼쪽", None))  # 까치산지선 종점(신도림)

_SEONGSU_2 = _by_is_destination(("왼쪽", None), ("오른쪽", None))
MULTI_ROW_RULES[("2호선", "G0713", "outer")] = _SEONGSU_2
MULTI_ROW_RULES[("2호선", "G0713", "inner")] = _const(("오른쪽", None))
MULTI_ROW_RULES[("2호선", "G0713", "up")] = _const(("오른쪽", None))  # 성수지선 종점(성수, 신설동발)

# 경의중앙선/경의선 행신·강매: "서울역행"(destination=서울, 경의선 계통) 열차만
# "서울역 착발" 문방향을 쓰고, 나머지(경의중앙선 전체 + 서울역행이 아닌 경의선)는
# "용산/청량리/용문 방면" 문방향을 쓴다(2026-08-31 사용자 확인).
_HAENGSHIN_GANGMAE_RULE = _by_destination({"서울"}, ("왼쪽", None), ("오른쪽", None))
MULTI_ROW_RULES[("경의중앙선", "G0001", None)] = _HAENGSHIN_GANGMAE_RULE  # 행신
MULTI_ROW_RULES[("경의중앙선", "G0478", None)] = _HAENGSHIN_GANGMAE_RULE  # 강매

# 아래는 41개 "다중행" 조합 집계엔 안 잡혔지만(방향별로 나누면 이미 count=1), 그 방향
# 텍스트가 trips.direction과 형식이 안 맞거나(대구/중앙로/공항철도 — "구미행"/"판암행"
# 등 종점명, 검암 — "인천공항 방면" 등 문구), 방향 무관 기본행(direction=None)과
# 서비스 한정 예외행이 공존해 예외행이 그 방향 전체를 잘못 덮어쓰던(노량진·동두천·안산,
# 2026-08-31 발견) 조합이다. 같은 MULTI_ROW_RULES로 해소한다.

# 노량진: 경인급행만 오른쪽, 나머지(경부장항 등 전부)는 왼쪽 — 방향 무관.
_NORYANGJIN_RULE = _by_line_name({"1호선/경인급행": ("오른쪽", None)}, ("왼쪽", None))
MULTI_ROW_RULES[("1호선", "G0292", "up")] = _NORYANGJIN_RULE
MULTI_ROW_RULES[("1호선", "G0292", "down")] = _NORYANGJIN_RULE

# 동두천 상행: 종착이면 원본 정상측 값이 '확인필요'라 스킵, 아니면 일반(왼쪽)으로 폴백.
MULTI_ROW_RULES[("1호선", "G0323", "up")] = _by_is_destination(SKIP, ("왼쪽", None))

# 안양·의왕·군포·금천구청 "경부급행B(지상서울~천안)": [[project_line1_gyeongbu_ab_express]]
# 메모리로 2026-08-31 해소 — B급행은 지상 서울역~천안/신창을 잇는 별개 계통으로 실제로는
# K1902·K1904·K1945 딱 3편뿐(서울급행 시트 소속, 평일 출퇴근 하루 3회). 나머지 전부(A급행
# 포함) "1호선/경부장항" line_name으로 뭉뚱그려져 있어 line_name으론 구분이 안 되고
# train_no로만 구분 가능. "지상서울" 역 경유 여부로 구분하려 했던 최초 가설은 그 역이
# 실제 정차 기록 0건이라 폐기.
_GYEONGBU_B_EXPRESS_RULE = _by_train_no_in({"K1902", "K1904", "K1945"}, ("왼쪽", None), ("오른쪽", None))
for _gid in ("G0089", "G0278", "G0280", "G0285"):  # 안양·의왕·군포·금천구청
    MULTI_ROW_RULES[("1호선", _gid, None)] = _GYEONGBU_B_EXPRESS_RULE

# 안산과천선 안산 하행: 종착이면 오른쪽(대피 없음), 아니면 일반행(왼쪽, 대피 시 오른쪽)으로 폴백.
MULTI_ROW_RULES[("4호선_안산과천선", "G0368", "down")] = _by_is_destination(("오른쪽", None), None)

# 인천1호선 박촌: 종착이면 오른쪽, 아니면 왼쪽(원래 '박촌종착'이라는 방향 텍스트가
# trips.direction과 안 맞아 지금까지 아예 반영이 안 되던 조합).
MULTI_ROW_RULES[("인천1호선", "G1046", None)] = _by_is_destination(("오른쪽", None), ("왼쪽", None))

# 대경선 대구: 구미 방면(up)이면 왼쪽, 경산·동대구 방면(down)이면 오른쪽.
MULTI_ROW_RULES[("대경선", "G0112", "up")] = _const(("왼쪽", None))
MULTI_ROW_RULES[("대경선", "G0112", "down")] = _const(("오른쪽", None))

# 대전1호선 중앙로: 반석 방면(up)이면 왼쪽, 판암 방면(down)이면 오른쪽.
MULTI_ROW_RULES[("대전1호선", "G0835", "up")] = _const(("왼쪽", None))
MULTI_ROW_RULES[("대전1호선", "G0835", "down")] = _const(("오른쪽", None))

# 공항철도 김포공항: 서울역 방면(up)이면 왼쪽, 인천공항 방면(down)이면 오른쪽.
MULTI_ROW_RULES[("공항철도", "G0587", "up")] = _const(("왼쪽", None))
MULTI_ROW_RULES[("공항철도", "G0587", "down")] = _const(("오른쪽", None))

# 인천1호선 국제업무지구: 송도달빛축제공원 방면(up)이면 왼쪽, 검단호수공원 방면(down)이면
# 오른쪽 — 행선(목적지)별로 문방향이 갈리는 역(사용자 확인, 2026-08-31).
MULTI_ROW_RULES[("인천1호선", "G1023", "up")] = _const(("왼쪽", None))
MULTI_ROW_RULES[("인천1호선", "G1023", "down")] = _const(("오른쪽", None))

# 공항철도 검암: 종착이면 왼쪽. 아니면(인천공항/서울역 방면 공통 오른쪽) 오른쪽 —
# 원본의 '양방향 대피/경합'(왼쪽) 행은 방향 무관 대피 상황을 가리키는 것으로 보여
# evac_side로 흡수(공항철도는 이미 EVAC_SOURCE_LINES에 등록돼 대피 판정 대상).
_GEOMAM_RULE = _by_is_destination(("왼쪽", None), ("오른쪽", "왼쪽"))
MULTI_ROW_RULES[("공항철도", "G1053", "up")] = _GEOMAM_RULE
MULTI_ROW_RULES[("공항철도", "G1053", "down")] = _GEOMAM_RULE


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

    # 2) door_directions: (line_sheet, group_id, 정규화된 방향) 단위로 묶어 단일행/다중행 분리
    # normal_side가 '왼쪽'/'오른쪽'이 아닌 행('확인필요'·'미판정'·'미개통'·'승강장없음' 등
    # 원본이 아직 못 채운 placeholder, 2026-08-31 12개 역에서 발견)은 아예 제외한다 —
    # 안 그러면 그 문자열이 실제 문방향인 것처럼 stop_door_side에 그대로 새어 들어간다.
    # evac_side도 마찬가지로 방향값이 아니면(예: 의정부의 '종착') None으로 무시한다.
    cur.execute("SELECT line_sheet, group_id, direction, normal_side, evac_side FROM door_directions")
    grouped = defaultdict(list)
    for r in cur.fetchall():
        if r["normal_side"] not in VALID_SIDES:
            continue
        evac = r["evac_side"] if r["evac_side"] in VALID_SIDES else None
        key = (r["line_sheet"], r["group_id"], norm_direction(r["direction"]))
        grouped[key].append((r["normal_side"], evac))

    single_door = {}
    multi_keys_total = 0
    multi_keys_resolved = 0
    for key, rows in grouped.items():
        if len(rows) == 1:
            single_door[key] = rows[0]
        else:
            multi_keys_total += 1
            if key in MULTI_ROW_RULES:
                multi_keys_resolved += 1

    # 3) stop_id -> (group_id, sheet) — door_directions에 매칭 정보가 있는 stop_id만
    cur.execute("SELECT stop_id, line, group_id FROM stops")
    door_stop = {}
    known_keys_prefix = {(k[0], k[1]) for k in grouped}
    for r in cur.fetchall():
        sheet = line_to_sheet.get(r["line"], r["line"])
        if (sheet, r["group_id"]) in known_keys_prefix:
            door_stop[r["stop_id"]] = (r["group_id"], sheet)

    def resolve_door(sheet, group_id, ctx):
        # MULTI_ROW_RULES를 single_door보다 먼저 본다 — 노량진·동두천·안산처럼 같은
        # (line_sheet, group_id)에 방향 무관 기본행(direction=None)과 서비스/종착
        # 한정 예외행이 공존하는 경우, 예외행이 그 방향 전부를 덮어써 버리면 안 되기
        # 때문(2026-08-31 발견 — 예외행을 무조건 방향 키로만 잡으면 일반 열차까지
        # 잘못된 값을 받는다). MULTI_ROW_RULES에 등록된 키는 항상 규칙 함수가 최종
        # 판단하고, None을 반환하면(조건 불충족/확신 없음) 다음 방향 키로 넘어간다.
        for dkey in (ctx["direction"], None):
            key = (sheet, group_id, dkey)
            rule = MULTI_ROW_RULES.get(key)
            if rule:
                result = rule(ctx)
                if result is SKIP:
                    return None
                if result:
                    return result
                continue
            if key in single_door:
                return single_door[key]
        return None

    # 4) Tier A 통과(pass) 이벤트: (group_id, service_id)별로 모아 dict
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

    # 4-1) trip_id -> (origin_name, destination_name) — 강동/병점류 규칙에 필요
    cur.execute("""
    SELECT t.trip_id AS trip_id, sgo.name_ko AS origin_name, sgd.name_ko AS destination_name
    FROM trips t
    LEFT JOIN stops so ON t.origin = so.stop_id
    LEFT JOIN station_groups sgo ON so.group_id = sgo.group_id
    LEFT JOIN stops sd ON t.destination = sd.stop_id
    LEFT JOIN station_groups sgd ON sd.group_id = sgd.group_id
    """)
    trip_od = {r["trip_id"]: (r["origin_name"], r["destination_name"]) for r in cur.fetchall()}

    # 1호선은 stops.line='1호선' 한 값이지만 trips.line_name은 '1호선/경부장항' 등으로
    # 세분화돼 있어 별도로 모은다(Tier A 대피 판정용).
    cur.execute("SELECT DISTINCT line_name FROM trips WHERE line_name LIKE ?", (LINE1_PREFIX + "%",))
    line1_variants = [r[0] for r in cur.fetchall()]

    # 5) 대상 정차(stop_type IN ('stop','destination'), door 정보 있는 stop_id)만 훑는다.
    cur.execute("""
    SELECT st.trip_id AS trip_id, st.stop_seq AS stop_seq, st.stop_id AS stop_id,
           st.arr_sec AS arr_sec, st.dep_sec AS dep_sec, st.stop_type AS stop_type,
           t.line_name AS line_name, t.service_id AS service_id, t.train_no AS train_no,
           t.direction AS direction
    FROM stop_times st
    JOIN trips t ON st.trip_id = t.trip_id
    WHERE st.stop_type IN ('stop', 'destination')
    """)

    rows_out = []
    n_evac = 0
    for r in cur.fetchall():
        info = door_stop.get(r["stop_id"])
        if info is None:
            continue
        group_id, sheet = info
        is_destination = r["stop_type"] == "destination"
        if is_destination:
            if r["arr_sec"] is None:
                continue
        else:
            # 36개 노선(KTX·일반열차 계열 + 인천1호선·대전1호선 등 다수 전동열차)은 원본이
            # "역당 시각 1개"(출발역 기준 배차표 등) 구조라 arr_sec가 원천적으로 없다
            # (2026-08-31 확인, 파서 버그 아닌 원본 데이터 한계). 문방향(normal_side)은
            # 시각 구간이 필요 없는 고정값이라 dep_sec 하나만 있어도 판정 가능 — 대피(Tier A)
            # 판정에만 arr_sec~dep_sec 구간이 필요하므로 그쪽은 아래에서 따로 가드한다.
            if r["arr_sec"] is None and r["dep_sec"] is None:
                continue

        origin_name, destination_name = trip_od.get(r["trip_id"], (None, None))
        ctx = {
            "line_name": r["line_name"], "train_no": r["train_no"],
            "origin_name": origin_name, "destination_name": destination_name,
            "is_destination": is_destination, "direction": r["direction"],
        }
        resolved = resolve_door(sheet, group_id, ctx)
        if resolved is None:
            continue
        normal_side, evac_side = resolved

        door_side, is_evac, overtaken_by = normal_side, 0, None
        # 대피(Tier A) 판정은 '정차 중 추월' 개념이라 종착역에는 적용하지 않는다.
        # arr_sec·dep_sec 둘 다 있어야 대피 구간(도착~출발) 비교가 가능하므로, 위에서
        # dep_sec만으로 통과한 행(arr_sec 없음)은 여기서 자동으로 평시값만 쓰게 된다.
        if evac_side and not is_destination and r["arr_sec"] is not None and r["dep_sec"] is not None:
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
    print(f"다중행 조합 {multi_keys_total}개 중 {multi_keys_resolved}개 규칙 등록"
          f"(나머지 {multi_keys_total - multi_keys_resolved}개는 신호 불충분으로 스킵)")
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
