"""
전체 자동 실행 (Claude API 사용 모드)
단계별 실행은 run.py 사용 권장

  python main.py              # 당일 자동 실행
  python main.py --date 20250610
"""
import argparse
import sys

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()

    sys.argv = ["run.py", "--stage", "all"]
    if args.date:
        sys.argv += ["--date", args.date]

    from run import main
    main()
