"""여러 파서가 공유하는 유틸리티 — "출발역 기준 배차표"류 원본(열차 단위 컬럼이
없고 역마다 그 역을 지나는 모든 열차의 시각 목록만 있는 형식) 공통 처리.

대전1호선(`parse_daejeon.py`)에서 처음 만든 FIFO 그리디 매칭 재구성 알고리즘을
웹크롤링 노선(신림선·우이신설선·김포골드라인·GTX-A·광주1호선 등, 전부 같은
"역별 발차 시각(시-분 목록)" 형식)에서도 그대로 쓰기 위해 공유 함수로 뽑았다
(2026-08-26 — 노선 파서는 분리하되 이 재구성 로직만 예외적으로 공유, Rule of Three).
"""


def link_trips(blocks, max_hop_min):
    """역 블록별 발차시각(분) 목록을 FIFO 그리디 매칭으로 이어 붙여 열차 단위
    trip을 복원한다.

    blocks: [(역명, [발차시각(분, 자정 기준 누적)]), ...] — 노선 순서 그대로,
            각 역의 시각 리스트는 오름차순 정렬돼 있어야 한다.
    max_hop_min: 정상적인 역간 간격의 상한(분) — 이보다 크게 벌어지면 그 열차는
                 다음 역에서 종착(또는 그 역이 시종착)한 것으로 본다.

    반환: [[(block_idx, 시각), ...], ...] — 열차(체인) 단위 리스트. 각 체인의
          길이가 곧 그 열차가 실제로 정차한 역 개수(짧으면 단축운행/시종착 지점이
          중간이라는 뜻 — 별도 처리 불요, 그대로 destination이 됨).
    """
    active = [[(0, t)] for t in blocks[0][1]]
    finished = []
    for block_idx in range(1, len(blocks)):
        times = blocks[block_idx][1]
        new_active = []
        ai = 0
        for t in times:
            matched = False
            while ai < len(active):
                last_t = active[ai][-1][1]
                if t - last_t > max_hop_min:
                    finished.append(active[ai])
                    ai += 1
                    continue
                if t >= last_t:
                    active[ai].append((block_idx, t))
                    new_active.append(active[ai])
                    ai += 1
                    matched = True
                break
            if not matched:
                new_active.append([(block_idx, t)])
        finished.extend(active[ai:])
        active = new_active
    finished.extend(active)
    return finished
