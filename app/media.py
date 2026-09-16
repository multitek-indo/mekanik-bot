from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4
import mimetypes
import httpx
from .config import settings


def media_reference(value):
    if value is None:
        return None
    if isinstance(value, str):
        return {"path": value}
    if isinstance(value, dict):
        return value
    return None


def extract_media(payload: dict) -> tuple[str | None, dict | None]:
    for kind in ("image", "video", "document", "audio", "video_note"):
        if payload.get(kind) is not None:
            return kind, media_reference(payload.get(kind))
    return None, None


def _extension(kind: str, ref: dict) -> str:
    source = str(ref.get("path") or ref.get("url") or "")
    suffix = Path(urlparse(source).path).suffix
    if suffix:
        return suffix[:10]
    defaults = {"image": ".jpg", "video": ".mp4", "video_note": ".mp4", "audio": ".ogg", "document": ".bin"}
    return defaults.get(kind, ".bin")


async def persist_incoming_media(kind: str, ref: dict | None, phone: str, purpose: str) -> str | None:
    if not ref:
        return None
    source = str(ref.get("path") or ref.get("url") or "").strip()
    if not source:
        return None

    media_dir = Path(settings.data_dir) / "media" / purpose.lower()
    media_dir.mkdir(parents=True, exist_ok=True)
    target = media_dir / f"{phone}-{uuid4().hex}{_extension(kind, ref)}"

    auth = httpx.BasicAuth(settings.gowa_basic_auth_user, settings.gowa_basic_auth_password)
    headers = {"X-Device-Id": settings.gowa_device_id}

    try:
        if source.startswith("http://") or source.startswith("https://"):
            url = source
            request_auth = None
            request_headers = {}
        else:
            url = f"{settings.gowa_url.rstrip('/')}/{source.lstrip('/')}"
            request_auth = auth
            request_headers = headers
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            response = await client.get(url, headers=request_headers, auth=request_auth)
            response.raise_for_status()
            target.write_bytes(response.content)
        return str(target)
    except Exception:
        # Keep the original GOWA reference in a small marker file so the evidence is not silently lost.
        marker = target.with_suffix(target.suffix + ".ref.txt")
        marker.write_text(source, encoding="utf-8")
        return str(marker)


def is_real_media_file(path: str | None) -> bool:
    if not path:
        return False
    p = Path(path)
    return p.is_file() and not p.name.endswith(".ref.txt")
