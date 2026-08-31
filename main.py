"""<프로젝트명> 진입점.

팀 표준: 이 파일은 얇게 유지한다 — 인자 파싱 + src 호출만, 5~30줄.
비즈니스 로직은 전부 src/ 패키지에 둔다. (근거: ../프로젝트_표준_가이드.md §3)
"""
import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="<프로젝트 한 줄 설명>")
    # parser.add_argument("--example", help="예시 인자")
    args = parser.parse_args()

    # TODO: src의 실제 진입 함수로 교체
    # from src import core
    # core.run(args)
    raise NotImplementedError("src/ 에 로직을 작성한 뒤 이 줄을 교체하세요.")


if __name__ == "__main__":
    main()
