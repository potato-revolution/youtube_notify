"""日次パイプラインのエントリポイント: python -m app.run"""

import logging
import sys

from app.pipeline import run_pipeline

logger = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        run_pipeline()
    except Exception as e:
        # 送信失敗等。seen.json は未更新のため翌日リカバリされる。
        logger.error("パイプライン失敗: %s", type(e).__name__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
