from dataclasses import dataclass
from typing import Any


@dataclass
class IncomingMessage:
    message_id: str
    phone: str
    sender_name: str
    text: str
    location: dict[str, Any] | None = None
    image: Any | None = None
    video: Any | None = None
    document: Any | None = None
    media_type: str | None = None
    media_path: str | None = None
    raw_payload: dict[str, Any] | None = None

    @property
    def has_image(self) -> bool:
        return self.image is not None or self.media_type == "image"

    @property
    def has_video(self) -> bool:
        return self.video is not None or self.media_type in {"video", "video_note"}
