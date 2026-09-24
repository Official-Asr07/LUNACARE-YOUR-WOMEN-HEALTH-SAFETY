"""
One place that ever touches the NVIDIA API key. index.html used to call
the AI provider directly from the browser with the key exposed in the page
source — every call in this file replaces one of those fetch() calls,
now running server-side where the key is safe.
"""
import httpx
from fastapi import HTTPException

from .config import get_settings

_settings = get_settings()


def _is_model_unavailable(status_code: int, body: str) -> bool:
    """True when NVIDIA is saying 'this model/function isn't provisioned for
    your account' rather than a real failure. This is the specific case we
    fall through to the next model on — everything else (401 bad key, 429
    rate limit, 5xx) should surface as-is, not be silently retried."""
    if status_code == 404:
        return True
    if status_code in (400, 422) and "not found for account" in body.lower():
        return True
    return False


async def nvidia_chat(messages: list[dict], temperature: float = 0.7, max_tokens: int = 900) -> str:
    if not _settings.NVIDIA_API_KEY:
        raise RuntimeError("NVIDIA_API_KEY is not configured on the server.")
    if not _settings.NVIDIA_MODELS:
        raise RuntimeError("NVIDIA_MODEL is not configured on the server.")

    url = f"{_settings.NVIDIA_BASE_URL.rstrip('/')}/chat/completions"
    last_error: HTTPException | None = None

    async with httpx.AsyncClient(timeout=30) as client:
        for model in _settings.NVIDIA_MODELS:
            res = await client.post(
                url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {_settings.NVIDIA_API_KEY}",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )

            if res.status_code >= 400:
                body = res.text
                print(f"NVIDIA API error: model={model} status={res.status_code} body={body[:1000]}")

                if _is_model_unavailable(res.status_code, body) and model != _settings.NVIDIA_MODELS[-1]:
                    # This model isn't available on this key's account — try the next one.
                    last_error = HTTPException(
                        status_code=502,
                        detail=f"Model '{model}' is not available for this API key: {body[:300]}",
                    )
                    continue

                # A real failure (bad key, rate limit, server error, or the
                # last model in the list also unavailable) — stop and report it.
                raise HTTPException(
                    status_code=502,
                    detail=f"The AI service is temporarily unavailable. NVIDIA rejected the request (model={model}): {body[:500]}",
                )

            try:
                data = res.json()
            except ValueError:
                print(f"NVIDIA returned non-JSON response: {res.text[:1000]}")
                raise HTTPException(
                    status_code=502,
                    detail="The AI service returned a non-JSON response.",
                )
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")

    # Should be unreachable (loop always returns or raises), but keep mypy/py happy.
    raise last_error or HTTPException(status_code=502, detail="No NVIDIA model succeeded.")
