"""공식 시각표를 배포하지 않고 배차간격(운행시격)표 + 역별 첫차/막차만
공개하는 노선(인천2호선, 용인경전철)의 시각표를 근사 생성하는 공유 헬퍼.

각 방면의 기준역(그 방면의 시발역) 첫차~막차를 시간대별 배차간격으로
채워 넣어 기준역의 발차 시각 목록을 만들고, 나머지 역은 그 역의 실제
공개된 첫차 시각과 기준역 첫차의 차이(=역간 소요시간)만큼 목록 전체를
평행이동해 근사한다. 막차 한 건만은 그 역에 실제 공개된 막차 시각으로
스냅해 근사 오차가 누적되지 않게 한다.

실제 관측 시각표가 아니라 배차간격 기반 근사치이므로, 이 헬퍼로 만든
노선은 전부 README에 "추정치 기반" 캐비어트를 명시해야 한다.
"""


def hm_to_min(hh, mm, rollover_hour=5):
    """시:분 -> 절대분(그날 00:00=0). rollover_hour 미만 시는 다음날로 간주해 +1440."""
    if hh < rollover_hour:
        hh += 24
    return hh * 60 + mm


def parse_hm(text, rollover_hour=5):
    """'HH:MM' / 'HH : MM' 문자열 -> 절대분."""
    hh, mm = text.replace(" ", "").split(":")
    return hm_to_min(int(hh), int(mm), rollover_hour)


def generate_schedule(first_min, last_min, bands):
    """bands: [(band_start_min, headway_min), ...] (시작 시각 오름차순).
    first_min에서 출발해 각 시점이 속한 band의 배차간격만큼 다음 발차를
    생성, last_min에 도달하거나 넘으면 last_min으로 스냅하고 종료."""
    times = [first_min]
    if last_min <= first_min:
        return times
    t = first_min
    while t < last_min:
        headway = bands[0][1]
        for start, hw in bands:
            if t >= start:
                headway = hw
        nt = round(t + headway)
        if nt >= last_min:
            times.append(last_min)
            break
        times.append(nt)
        t = nt
    return times


def shift_schedule(origin_schedule, offset_min, real_last_min, real_first_min=None):
    """기준역 발차 목록을 offset_min만큼 평행이동해 다른 역의 근사 발차
    목록을 만든다. offset_min은 막차 기준(그 역 막차 - 기준역 막차)으로
    계산해야 한다 — 실제 관측 결과 노선 중간에 단축운행(구간운행) 열차의
    시발역이 섞여 있어 첫차 기준 오프셋은 신뢰할 수 없다(중간역의 첫차가
    기준역보다 오히려 이른 경우가 실제로 있음).

    마지막 값은 그 역에 실제 공개된 막차로 항상 스냅한다. real_first_min이
    주어지고 평행이동한 첫 값보다 이르면(=그 역이 실제로는 중간 시발역이라
    더 이른 별도 열차가 있다는 뜻) 첫 값도 그 실제 첫차로 스냅한다 — 다만
    그 중간 시발역 자체의 나머지 배차까지 복원하지는 못한다(추정치 한계,
    캐비어트로 명시)."""
    shifted = [t + offset_min for t in origin_schedule]
    if not shifted:
        return shifted
    shifted[-1] = real_last_min
    if real_first_min is not None and real_first_min < shifted[0]:
        shifted[0] = real_first_min
    return shifted
