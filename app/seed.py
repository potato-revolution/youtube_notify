"""一度きりの初期シードのエントリポイント: python -m app.seed --recent 2

各チャンネル直近 N 本のみ要約して送信し、現在の新着全 ID を既読化する。
登録直後のバックログ一括要約を避けるために一度だけ使う。以降は app.run。
"""

import argparse
import logging
import sys

from app.pipeline import seed_pipeline

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(
        prog="python -m app.seed",
        description="初期シード: 各チャンネル直近 N 本のみ要約し、残りは既読登録する",
    )
    parser.add_argument(
        "--recent",
        type=int,
        default=2,
        help="各チャンネルで要約する直近本数(既定: 2)",
    )
    args = parser.parse_args(argv)

    try:
        seed_pipeline(recent_per_channel=args.recent)
    except Exception as e:
        logger.error("シード失敗: %s", type(e).__name__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
