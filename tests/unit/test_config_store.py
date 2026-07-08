from app.adapters.config_store import ConfigStore
from app.models import Channel


def make_store(tmp_path, max_seen: int = 100) -> ConfigStore:
    return ConfigStore(
        channels_path=tmp_path / "channels.json",
        seen_path=tmp_path / "seen.json",
        max_seen=max_seen,
    )


def make_channel(channel_id: str) -> Channel:
    return Channel(
        channel_id=channel_id,
        handle="@sample",
        title="サンプル",
        added_at="2026-07-08T22:00:00+09:00",
    )


def test_load_channels_missing_file_returns_empty(tmp_path):
    assert make_store(tmp_path).load_channels() == []


def test_add_channel_new_returns_true_and_persists(tmp_path):
    store = make_store(tmp_path)
    assert store.add_channel(make_channel("UC1")) is True
    loaded = store.load_channels()
    assert len(loaded) == 1
    assert loaded[0].channel_id == "UC1"
    assert loaded[0].handle == "@sample"


def test_add_channel_duplicate_returns_false_and_not_appended(tmp_path):
    store = make_store(tmp_path)
    assert store.add_channel(make_channel("UC1")) is True
    assert store.add_channel(make_channel("UC1")) is False
    assert len(store.load_channels()) == 1


def test_load_seen_missing_file_returns_empty(tmp_path):
    assert make_store(tmp_path).load_seen() == set()


def test_save_seen_appends_without_duplicates(tmp_path):
    store = make_store(tmp_path)
    store.save_seen(["a", "b"])
    store.save_seen(["b", "c"])
    assert store.load_seen() == {"a", "b", "c"}


def test_save_seen_trims_oldest_beyond_max(tmp_path):
    store = make_store(tmp_path, max_seen=3)
    store.save_seen(["a", "b", "c"])
    store.save_seen(["d"])
    # 上限3件: 最も古い "a" が切り詰められる
    assert store.load_seen() == {"b", "c", "d"}
