import base64

import httpx

from app.core.config import settings


async def describe_image(image_bytes: bytes) -> str:
    b64 = base64.b64encode(image_bytes).decode()
    data_url = f"data:image/jpeg;base64,{b64}"

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Опиши подробно что изображено на этой картинке. Ответ дай на русском языке.",
                },
                {
                    "type": "image_url",
                    "image_url": {"url": data_url},
                },
            ],
        }
    ]

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.openai_base_url}/v1/chat/completions",
            headers=settings.openai_headers,
            json={
                "model": settings.VISION_MODEL,
                "messages": messages,
                "max_completion_tokens": 1000,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    return (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )
