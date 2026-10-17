"""The port's messages: text, or parts that may hold images, audio and video."""

from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from app.llm.llm_client import AudioPart, ChatMessage, ImagePart, Media, TextPart, VideoPart

MESSAGES = TypeAdapter(list[ChatMessage])


def test_parts_are_told_apart_by_their_type() -> None:
    [message] = MESSAGES.validate_python(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe these."},
                    {"type": "image_url", "image_url": {"url": "https://example.com/a.png"}},
                    {"type": "input_audio", "input_audio": {"data": "UklGRg==", "format": "wav"}},
                    {"type": "input_video", "input_video": {"url": "https://example.com/a.mp4"}},
                ],
            }
        ]
    )

    assert isinstance(message.content, list)
    assert [type(part) for part in message.content] == [
        TextPart,
        ImagePart,
        AudioPart,
        VideoPart,
    ]


@pytest.mark.parametrize(
    "message",
    [
        {"role": "user", "content": ""},
        {"role": "user", "content": []},
        {"role": "tool", "content": "x"},
        {"role": "user", "content": [{"type": "text", "text": ""}]},
        {"role": "user", "content": [{"type": "file", "file": {"file_id": "f"}}]},
        {"role": "user", "content": [{"type": "input_audio", "input_audio": {}}]},
    ],
)
def test_invalid_messages_are_refused(message: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        MESSAGES.validate_python([message])


def test_media_takes_data_or_a_url_but_not_both() -> None:
    assert Media(data="AAAA").data == "AAAA"
    assert Media(url="https://example.com/a.mp4").url == "https://example.com/a.mp4"
    with pytest.raises(ValidationError, match="either data or url"):
        Media(data="AAAA", url="https://example.com/a.mp4")
