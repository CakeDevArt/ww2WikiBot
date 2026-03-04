import httpx

from app.core.config import settings


async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.mp3") -> str:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.openai_base_url}/v1/audio/transcriptions",
            headers=settings.openai_headers,
            files={"file": (filename, audio_bytes, "audio/mpeg")},
            data={
                "model": settings.STT_MODEL,
                "language": "ru",
                "response_format": "json",
            },
        )
        resp.raise_for_status()
        payload = resp.json()
        return payload.get("text", "").strip()
