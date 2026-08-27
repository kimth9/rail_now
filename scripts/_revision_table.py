"""2026.9.1 개정부터 코레일 배포 xlsx가 공통으로 쓰는 '조정안(신규)+현행(개정전)'
대조표 레이아웃을 읽는 공용 헬퍼.

기존 각 파서에 복붙돼 있던 헤더 탐지/역행 수집 로직을 컬럼 인자화만 해서 그대로
옮긴 것 — 로직 자체는 바뀌지 않았다(parse_line1.py가 예전부터 `서울급행` 시트
하나를 이 레이아웃으로 스킵해온 전례가 있고, 이번 개정부터 전 시트에 적용됨).
역명 별칭·분기점·line_id 같은 노선별 로직은 그대로 각 파서에 남는다.
"""


def clean(v):
    return str(v).strip() if v is not None else ""


def find_header_row(ws, col, label="열차번호", max_search=8):
    return next(r for r in range(1, max_search + 1) if clean(ws.cell(r, col).value) == label)


def find_boundary_row(ws, header_row, marker_col=1, marker="현행"):
    """'현행'(개정 전 대조 블록) 행을 찾는다. 없으면 시트 끝까지가 전부 조정안 블록.

    '현행'/'조정안' 타이틀은 역명 컬럼(station_col)이 아니라 항상 1열에 찍혀있다
    (역명·헤더 라벨은 station_col, 타이틀만 1열 — 실측으로 확인됨). 그래서 이
    marker_col은 station_col과 별개로 항상 1이 기본값이다.
    """
    return next((r for r in range(header_row + 1, ws.max_row + 1)
                 if clean(ws.cell(r, marker_col).value) == marker), ws.max_row + 1)


def collect_station_rows(ws, col, header_row, boundary_row, not_a_station, junctions):
    """조정안 블록 안의 역행만 수집. 반환: [(row, station_or_junction_label), ...]"""
    st_rows = []
    for r in range(header_row + 1, boundary_row):
        label = clean(ws.cell(r, col).value)
        if not label or label in not_a_station:
            continue
        if label in junctions:
            st_rows.append((r, "@" + junctions[label]))
        else:
            st_rows.append((r, label))
    return st_rows


def find_link_row(ws, col, header_row, boundary_row, marker="연계"):
    return next((r for r in range(header_row + 1, boundary_row)
                 if marker in clean(ws.cell(r, col).value)), None)
