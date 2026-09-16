from pathlib import Path
import mimetypes
import httpx
from .config import settings


def normalize_phone(value: str) -> str:
    v = (value or "").strip()
    if "@" in v:
        v = v.split("@", 1)[0]
    v = "".join(ch for ch in v if ch.isdigit())
    if v.startswith("0"):
        v = "62" + v[1:]
    return v


def _auth():
    return httpx.BasicAuth(settings.gowa_basic_auth_user, settings.gowa_basic_auth_password)


def _headers():
    return {"X-Device-Id": settings.gowa_device_id}


async def send_text(phone: str, message: str):
    if not phone or not message:
        return
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{settings.gowa_url.rstrip('/')}/send/message",
            json={"phone": normalize_phone(phone), "message": message[: settings.max_message_length]},
            headers=_headers(),
            auth=_auth(),
        )
        response.raise_for_status()


async def send_image(phone: str, path: str, caption: str = "") -> bool:
    p = Path(path)
    if not p.is_file():
        return False
    mime = mimetypes.guess_type(p.name)[0] or "image/jpeg"
    async with httpx.AsyncClient(timeout=60) as client:
        with p.open("rb") as fh:
            response = await client.post(
                f"{settings.gowa_url.rstrip('/')}/send/image",
                data={
                    "phone": normalize_phone(phone),
                    "caption": caption[:1000],
                    "view_once": "false",
                    "compress": "true",
                },
                files={"image": (p.name, fh, mime)},
                headers=_headers(),
                auth=_auth(),
            )
            response.raise_for_status()
    return True


async def send_file(phone: str, path: str, caption: str = "") -> bool:
    p = Path(path)
    if not p.is_file():
        return False
    mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    async with httpx.AsyncClient(timeout=60) as client:
        with p.open("rb") as fh:
            response = await client.post(
                f"{settings.gowa_url.rstrip('/')}/send/file",
                data={"phone": normalize_phone(phone), "caption": caption[:1000]},
                files={"file": (p.name, fh, mime)},
                headers=_headers(),
                auth=_auth(),
            )
            response.raise_for_status()
    return True


async def send_location(phone: str, lat: float, lon: float, name: str = "Lokasi customer", address: str = ""):
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{settings.gowa_url.rstrip('/')}/send/location",
            json={
                "phone": normalize_phone(phone),
                "latitude": lat,
                "longitude": lon,
                "name": name,
                "address": address,
            },
            headers=_headers(),
            auth=_auth(),
        )
        # GOWA versions have changed the location payload field names in the past.
        # A text fallback is used by callers if this endpoint returns an error.
        response.raise_for_status()
