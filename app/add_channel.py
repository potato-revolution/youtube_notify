"""監視チャンネル追加のエントリポイント: python -m app.add_channel <@handle または URL>"""

import argparse
import sys

from app.adapters.channel_resolver import ChannelResolveError, ChannelResolver
from app.adapters.config_store import ConfigStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.add_channel",
        description="@handle / URL を channel_id に解決して監視リストへ追記する",
    )
    parser.add_argument(
        "handle_or_url",
        help="例: @handlename / https://www.youtube.com/@handlename"
        " / https://www.youtube.com/channel/UC...",
    )
    args = parser.parse_args(argv)

    try:
        channel = ChannelResolver().resolve(args.handle_or_url)
    except ChannelResolveError as e:
        print(f"エラー: {e}", file=sys.stderr)
        print(
            "形式例: @handlename / https://www.youtube.com/@handlename"
            " / https://www.youtube.com/channel/UC...",
            file=sys.stderr,
        )
        return 1

    if ConfigStore().add_channel(channel):
        label = channel.title or channel.handle or channel.channel_id
        print(f"追加しました: {label} (channel_id={channel.channel_id})")
    else:
        print(f"既に登録済みです: channel_id={channel.channel_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
