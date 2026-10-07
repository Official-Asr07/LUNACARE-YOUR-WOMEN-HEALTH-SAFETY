"""
Replaces: aviroSend() (~line 5912), searchLegalAI() (~line 5553),
findNearbyExperts() (~line 5460), _analyzeWithGemini() (~line 5076) in index.html.

All four used to call the AI provider directly from the browser with the API key
exposed in page source. Now the frontend calls these endpoints, and this
server calls NVIDIA using a key that lives only in the backend's environment.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from ..nvidia_client import nvidia_chat

router = APIRouter(prefix="/api/aviro", tags=["aviro"])


# ── Main chat ────────────────────────────────────────────────────────────
class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    system_prompt: str
    history: list[ChatMessage]  # last ~30 turns, same as aviroHistory in the JS


class ChatResponse(BaseModel):
    reply: str


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    messages = [{"role": "system", "content": req.system_prompt}] + [
        {"role": m.role, "content": m.content} for m in req.history
    ]
    reply = await nvidia_chat(messages, temperature=0.75, max_tokens=450)
    return ChatResponse(reply=reply or "Something unexpected happened. Please try again. 🌸")


# ── Legal AI search ──────────────────────────────────────────────────────
class LegalSearchRequest(BaseModel):
    query: str


@router.post("/legal-search")
async def legal_search(req: LegalSearchRequest):
    prompt = f"""You are AViro, a legal AI embedded in LunaCare, a women's safety app in India.
The user searched for: "{req.query}"
Respond ONLY with a JSON object (no preamble, no markdown):
{{"found":true,"laws":[{{"name":"Full law name","section":"Section number(s)","covers":"What this section covers","punishment":"Exact punishment","fir_steps":["Step 1","Step 2","Step 3"],"helplines":["100 — Police","1091 — Women Helpline"],"tip":"One practical tip"}}]}}
If no law: {{"found":false,"message":"Brief explanation in Hinglish"}}
Prefer BNS 2023 over IPC. Return ONLY valid JSON."""
    raw = await nvidia_chat([{"role": "user", "content": prompt}], temperature=0.2, max_tokens=1000)
    return {"raw": raw.replace("```json", "").replace("```", "").strip()}


# ── Expert locator ───────────────────────────────────────────────────────
class ExpertSearchRequest(BaseModel):
    city: str


@router.post("/expert-locator")
async def expert_locator(req: ExpertSearchRequest):
    prompt = f"""You are AViro, a women's health AI. The user is in "{req.city}", India.
Find the TOP 3 of EACH: 1. Gynecologists/OB-GYN 2. Therapists/Counselors (women-focused) 3. Physiotherapists (pelvic health preferred)
Respond ONLY with a JSON array (no preamble, no markdown):
[{{"type":"Gynecologist","name":"Dr. Name","clinic":"Clinic Name","area":"Locality, City","rating":"4.8 ⭐","contact":"contact info","note":"specialty note"}}]
If no real data for {req.city}, return best-known hospitals/clinics. Always return valid JSON only."""
    raw = await nvidia_chat([{"role": "user", "content": prompt}], temperature=0.3, max_tokens=1200)
    return {"raw": raw.replace("```json", "").replace("```", "").strip()}


# ── Situational (SOS ambient audio) analysis ────────────────────────────
class SituationalRequest(BaseModel):
    transcript: str


@router.post("/situational-analysis")
async def situational_analysis(req: SituationalRequest):
    prompt = f"""You are a safety AI assistant embedded in a women's emergency SOS app in India.

TRANSCRIPT from victim's environment (10-second ambient audio):
"{req.transcript}"

Analyze this transcript for signs of:
- Physical struggle (sounds of hitting, falling, pain)
- Shouting or screaming
- Verbal threats or abuse
- Distress words (help, bachao, chodo, mat maaro, etc.)
- Calm vs agitated tone indicators

Provide EXACTLY 1 sentence situational report starting with a threat level indicator:
[CRITICAL] / [HIGH] / [MODERATE] / [LOW] / [UNCLEAR]

Respond with ONLY the 1-sentence report. No explanations. No preamble."""
    report = await nvidia_chat([{"role": "user", "content": prompt}], temperature=0.1, max_tokens=120)
    return {"report": report.strip() or "[UNCLEAR] AI could not determine threat level from transcript."}
