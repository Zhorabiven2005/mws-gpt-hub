"""
Транскрипция через POST /v1/audio/transcriptions (при MWS_ASR_MODEL в .env).
"""
import io
import os
import httpx


async def try_transcribe_bytes(
    audio_bytes: bytes,
    filename: str,
    api_base: str,
    headers: dict,
) -> str | None:
    model = os.getenv("MWS_ASR_MODEL", "").strip()
    if not model or not audio_bytes:
        return None
    h = {k: v for k, v in headers.items() if k.lower() != "content-type"}
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            files = {
                "file": (
                    filename or "audio.webm",
                    io.BytesIO(audio_bytes),
                    "application/octet-stream",
                )
            }
            data = {"model": model}
            r = await client.post(
                f"{api_base.rstrip('/')}/audio/transcriptions",
                files=files,
                data=data,
                headers=h,
            )
            if r.status_code != 200:
                return None
            out = r.json()
            text = out.get("text")
            return text if isinstance(text, str) and text.strip() else None
    except Exception:
        return None
    return None
