import pytest

from app.adapters.channel_resolver import (
    ChannelResolveError,
    ChannelResolver,
    extract_channel_id_from_url,
    extract_handle,
)

CHANNEL_ID = "UC" + "x" * 22


def test_extract_channel_id_from_channel_url():
    url = f"https://www.youtube.com/channel/{CHANNEL_ID}"
    assert extract_channel_id_from_url(url) == CHANNEL_ID


def test_extract_channel_id_from_handle_url_returns_none():
    assert extract_channel_id_from_url("https://www.youtube.com/@handlename") is None


def test_extract_handle_from_bare_handle():
    assert extract_handle("@handlename") == "@handlename"


def test_extract_handle_from_handle_url():
    assert extract_handle("https://www.youtube.com/@handle.name-1") == "@handle.name-1"


def test_extract_handle_invalid_returns_none():
    assert extract_handle("handlename") is None
    assert extract_handle("https://example.com/foo") is None


def test_resolve_invalid_input_raises_without_network():
    with pytest.raises(ChannelResolveError):
        ChannelResolver().resolve("not-a-handle-or-url")


def test_resolve_empty_input_raises():
    with pytest.raises(ChannelResolveError):
        ChannelResolver().resolve("   ")
